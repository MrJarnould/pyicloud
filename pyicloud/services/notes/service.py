"""
High-level Notes service (DX-first).

Public API:
  - NotesService.recents(limit=50) -> Iterable[NoteSummary]
  - NotesService.iter_all(page_size=200, since=None) -> Iterable[NoteSummary]
  - NotesService.folders() -> Iterable[NoteFolder]
  - NotesService.recents_in_folder(folder_id, limit=20) -> Iterable[NoteSummary]
  - NotesService.in_folder(folder_id, limit=None) -> Iterable[NoteSummary]
  - NotesService.get(note_id, with_attachments=False) -> Note
  - NotesService.sync_cursor() -> str
  - NotesService.iter_changes(since=None, page_size=200) -> Iterable[ChangeEvent]
  - NotesService.raw -> CloudKitNotesClient (escape hatch)

This module exposes developer-friendly dataclasses and hides CloudKit details.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Iterator, List, Optional

from pyicloud.services.base import BaseService
from pyicloud.services.notes.decoding import BodyDecoder

from .client import (
    CloudKitNotesClient,
    NotesApiError,
    NotesAuthError,
    NotesRateLimited,
)
from .domain import AttachmentId, NoteBody
from .models import Attachment, Note, NoteSummary
from .models.cloudkit import (
    CKDesiredKey,
    CKErrorItem,
    CKFVString,
    CKLookupResponse,
    CKQueryFilterBy,
    CKQueryObject,
    CKQueryResponse,
    CKQuerySortBy,
    CKRecord,
    CKReference,
    CKTombstoneRecord,
    CKZoneChangesZoneReq,
    CKZoneID,
    CKZoneIDReq,
)
from .models.dto import ChangeEvent, NoteFolder

LOGGER = logging.getLogger(__name__)


# ----------------------------- Service Errors --------------------------------


class NotesError(Exception):
    """Base Notes service error."""


class NoteNotFound(NotesError):
    pass


class NoteLockedError(NotesError):
    pass


# ----------------------------- NotesService ----------------------------------


class NotesService(BaseService):
    """
    Developer-first Notes API. Uses the preconfigured CloudKit raw client under the hood.
    """

    _CONTAINER = "com.apple.notes"
    _ENV = "production"
    _SCOPE = "private"

    def __init__(self, service_root: str, session, params: Dict[str, str]):
        super().__init__(service_root=service_root, session=session, params=params)
        endpoint = f"{self.service_root}/database/1/{self._CONTAINER}/{self._ENV}/{self._SCOPE}"
        # Sensible defaults; lower-case booleans are applied in the raw client
        base_params = {
            "remapEnums": True,
            "getCurrentSyncToken": True,
            **(params or {}),
        }
        self._raw = CloudKitNotesClient(
            base_url=endpoint,
            session=session,
            base_params=base_params,
        )
        # In-memory caches
        self._folder_name_cache: Dict[str, Optional[str]] = {}
        self._attachment_meta_cache: Dict[str, Attachment] = {}

    # -------------------------- Public API methods ---------------------------

    def recents(self, *, limit: int = 50) -> Iterable[NoteSummary]:
        """
        Fast, feed-style listing of the newest notes (most-recent first).
        Cheap server query via SearchIndexes. Use for UI views.
        """
        if limit <= 0:
            return

        desired_keys = [
            CKDesiredKey.TITLE_ENCRYPTED,
            CKDesiredKey.SNIPPET_ENCRYPTED,
            CKDesiredKey.MODIFICATION_DATE,
            CKDesiredKey.DELETED,
            CKDesiredKey.FOLDER,
            CKDesiredKey.FIRST_ATTACHMENT_UTI_ENCRYPTED,
            CKDesiredKey.FIRST_ATTACHMENT_THUMBNAIL,
            CKDesiredKey.FIRST_ATTACHMENT_THUMBNAIL_ORIENTATION,
            CKDesiredKey.ATTACHMENTS,
        ]
        query = CKQueryObject(
            recordType="SearchIndexes",
            filterBy=[
                CKQueryFilterBy(
                    comparator="EQUALS",
                    fieldName="indexName",
                    fieldValue=CKFVString(type="STRING", value="recents"),
                )
            ],
            sortBy=[CKQuerySortBy(fieldName="modTime", ascending=False)],
        )
        yielded = 0
        cont: Optional[str] = None
        LOGGER.debug("Fetching recents: limit=%d", limit)
        while True:
            remaining = limit - yielded
            if remaining <= 0:
                return
            resp: CKQueryResponse = self._raw.query(
                query=query,
                zone_id=CKZoneIDReq(zoneName="Notes"),
                desired_keys=self._coerce_keys(desired_keys),
                results_limit=min(200, remaining),
                continuation=cont,
            )
            for rec in resp.records:
                if isinstance(rec, CKRecord):
                    summary = self._summary_from_record(rec)
                    yielded += 1
                    yield summary
                    if yielded >= limit:
                        LOGGER.debug(
                            "Recents: yielded %d notes (limit reached)", yielded
                        )
                        return
            cont = getattr(resp, "continuationMarker", None)
            if not cont:
                LOGGER.debug("Recents: no more continuation marker, done.")
                return

    def recents_in_folder(
        self, folder_id: str, *, limit: int = 20
    ) -> Iterable[NoteSummary]:
        """
        Fast helper: filter the global recents stream by folder.
        Returns up to `limit` most-recent notes in `folder_id`, without scanning
        the full /changes/zone history (which can be slow for old folders).
        """
        if limit <= 0:
            return
        emitted = 0
        # Pull a larger window than requested to increase the chance of finding matches fast.
        window = max(200, limit * 5)
        LOGGER.debug(
            "Fetching recents in folder: folder_id=%s limit=%d", folder_id, limit
        )
        for n in self.recents(limit=window):
            if n.folder_id == folder_id and not n.is_deleted:
                yield n
                emitted += 1
                if emitted >= limit:
                    LOGGER.debug(
                        "Recents in folder: yielded %d notes (limit reached)", emitted
                    )
                    return

    def iter_all(self, *, since: Optional[str] = None) -> Iterable[NoteSummary]:
        """
        Iterate every note via the CloudKit changes feed.
        Use for exports, indexing, or building local caches.
        If `since` is provided (sync token), yields only changes since that cursor.
        """
        LOGGER.debug("Iterating all notes%s", f" since={since}" if since else "")
        for zone in self._raw.changes(
            zone_req=CKZoneChangesZoneReq(
                zoneID=CKZoneID(zoneName="Notes", zoneType="REGULAR_CUSTOM_ZONE"),
                desiredRecordTypes=["Note"],
                desiredKeys=self._coerce_keys(
                    [
                        CKDesiredKey.TITLE_ENCRYPTED,
                        CKDesiredKey.SNIPPET_ENCRYPTED,
                        CKDesiredKey.MODIFICATION_DATE,
                        CKDesiredKey.DELETED,
                        CKDesiredKey.FOLDER,
                        CKDesiredKey.ATTACHMENTS,
                    ]
                ),
                syncToken=since,
                reverse=False,
            ),
            # CloudKit page sizing is implicit; we cap our own yield volume by iterating
        ):
            for rec in zone.records:
                if isinstance(rec, CKRecord):
                    yield self._summary_from_record(rec)

    def folders(self) -> Iterable[NoteFolder]:
        """
        Enumerate top-level Notes folders. Use to build navigation UIs or resolve folder IDs.
        """
        desired_keys = [
            CKDesiredKey.TITLE_ENCRYPTED,
            "TitleModificationDate",
            "HasSubfolder",
        ]
        query = CKQueryObject(
            recordType="SearchIndexes",
            filterBy=[
                CKQueryFilterBy(
                    comparator="EQUALS",
                    fieldName="indexName",
                    fieldValue=CKFVString(type="STRING", value="parentless"),
                )
            ],
        )
        cont: Optional[str] = None
        LOGGER.debug("Fetching folders")
        while True:
            resp: CKQueryResponse = self._raw.query(
                query=query,
                zone_id=CKZoneIDReq(zoneName="Notes"),
                desired_keys=self._coerce_keys(desired_keys),
                results_limit=200,
                continuation=cont,
            )
            for rec in resp.records:
                if isinstance(rec, CKRecord):
                    folder_id = rec.recordName
                    name = self._decode_encrypted(
                        rec.fields.get_value("TitleEncrypted")
                    )
                    has_sub = bool(
                        getattr(
                            rec.fields.get_field("HasSubfolder") or (), "value", False
                        )
                    )
                    yield NoteFolder(
                        id=folder_id, name=name, has_subfolders=has_sub, count=None
                    )
                    # cache for later
                    self._folder_name_cache.setdefault(folder_id, name)
            cont = getattr(resp, "continuationMarker", None)
            if not cont:
                LOGGER.debug("Folders: no more continuation marker, done.")
                return

    def in_folder(
        self, folder_id: str, *, limit: Optional[int] = None
    ) -> Iterable[NoteSummary]:
        """
        List notes that belong to a specific folder (newest first).
        Stops after `limit` if provided.
        """
        emitted = 0
        LOGGER.debug(
            "Fetching notes in folder: folder_id=%s limit=%s", folder_id, limit
        )
        for zone in self._raw.changes(
            zone_req=CKZoneChangesZoneReq(
                zoneID=CKZoneID(zoneName="Notes", zoneType="REGULAR_CUSTOM_ZONE"),
                desiredRecordTypes=["Note"],
                desiredKeys=self._coerce_keys(
                    [
                        CKDesiredKey.TITLE_ENCRYPTED,
                        CKDesiredKey.SNIPPET_ENCRYPTED,
                        CKDesiredKey.MODIFICATION_DATE,
                        CKDesiredKey.DELETED,
                        CKDesiredKey.FOLDER,
                        CKDesiredKey.FIRST_ATTACHMENT_UTI_ENCRYPTED,
                        CKDesiredKey.FIRST_ATTACHMENT_THUMBNAIL,
                        CKDesiredKey.FIRST_ATTACHMENT_THUMBNAIL_ORIENTATION,
                        CKDesiredKey.ATTACHMENTS,
                    ]
                ),
                reverse=True,  # newest first
            )
        ):
            for rec in zone.records:
                if not isinstance(rec, CKRecord):
                    continue
                rec_folder_id = self._extract_folder_id(rec)
                deleted = bool(rec.fields.get_value("Deleted") or False)
                if deleted or rec_folder_id != folder_id:
                    continue
                yield self._summary_from_record(rec)
                emitted += 1
                if limit and emitted >= limit:
                    LOGGER.debug(
                        "Notes in folder: yielded %d notes (limit reached)", emitted
                    )
                    return

    def get(self, note_id: str, *, with_attachments: bool = False) -> Note:
        """
        Fetch a single note with full body text if available.
        Raises NoteNotFound if the note doesn't exist.
        Raises NoteLockedError if the note is passphrase-locked and content is inaccessible.
        """
        LOGGER.debug(
            "Fetching note: note_id=%s with_attachments=%s", note_id, with_attachments
        )
        resp: CKLookupResponse = self._raw.lookup(
            record_names=[note_id],
            desired_keys=self._coerce_keys(
                [
                    CKDesiredKey.TITLE_ENCRYPTED,
                    CKDesiredKey.SNIPPET_ENCRYPTED,
                    CKDesiredKey.MODIFICATION_DATE,
                    CKDesiredKey.DELETED,
                    CKDesiredKey.FOLDER,
                    CKDesiredKey.ATTACHMENTS,
                    "TextDataEncrypted",  # may or may not be present
                ]
            ),
        )
        target: Optional[CKRecord] = None
        for rec in resp.records:
            if isinstance(rec, CKRecord) and rec.recordName == note_id:
                target = rec
                break
        if target is None:
            LOGGER.warning("Note not found: %s", note_id)
            raise NoteNotFound(f"Note not found: {note_id}")

        summary = self._summary_from_record(target)
        if summary.is_locked:
            LOGGER.warning("Note is locked and cannot be read: %s", note_id)
            raise NoteLockedError(
                f"Note '{summary.title or note_id}' is locked and cannot be read."
            )

        note_body = self._decode_note_body(target)
        # Minimal breadcrumbs for body decode outcome
        try:
            if note_body and note_body.text:
                LOGGER.info(
                    "notes.body.decoded ok id=%s len=%d",
                    summary.id,
                    len(note_body.text),
                )
            else:
                LOGGER.info("notes.body.decoded empty id=%s", summary.id)
        except Exception:
            LOGGER.info(
                "notes.body.decoded %s",
                "ok" if note_body and note_body.text else "empty",
            )
        attachments: Optional[List[Attachment]] = None
        html: Optional[str] = None

        text = note_body.text if note_body else None
        attachment_ids: List[AttachmentId] = []
        if note_body and note_body.attachment_ids:
            attachment_ids = note_body.attachment_ids

        if with_attachments:
            attachments = self._resolve_attachments_for_record(
                target, attachment_ids=attachment_ids
            )

        return Note(
            id=summary.id,
            title=summary.title,
            snippet=summary.snippet,
            modified_at=summary.modified_at,
            folder_id=summary.folder_id,
            folder_name=summary.folder_name,
            is_deleted=summary.is_deleted,
            is_locked=summary.is_locked,
            text=text,
            html=html,
            attachments=attachments,
        )

    def sync_cursor(self) -> str:
        """
        Return the current sync token for the Notes zone.
        """
        LOGGER.debug("Fetching sync cursor for Notes zone")
        return self._raw.current_sync_token(zone_name="Notes")

    def export_note(self, note_id: str, output_dir: str, **config_kwargs) -> str:
        """
        Export a note to HTML with assets saved to the output directory.

        Args:
            note_id: The UUID of the note to export.
            output_dir: Local directory to save the HTML and assets.
            **config_kwargs: Options for ExportConfig (e.g. embed_images, link_rel).

        Returns:
            Path to the generated HTML file.
        """
        resp = self._raw.lookup([note_id])
        target = None
        for rec in resp.records:
            if isinstance(rec, CKRecord) and rec.recordName == note_id:
                target = rec
                break
        if not target:
            raise NoteNotFound(f"Note not found: {note_id}")

        # Lazy import to avoid circular dependency
        from .rendering.exporter import NoteExporter
        from .rendering.options import ExportConfig

        config = ExportConfig(**config_kwargs)
        exporter = NoteExporter(self._raw, config=config)
        path = exporter.export(target, output_dir=output_dir)
        if not path:
            raise NotesError(f"Failed to export note: {note_id}")
        return path

    def render_note(self, note_id: str, **config_kwargs) -> str:
        """
        Render a note to an HTML fragment string (does not download assets).

        Args:
            note_id: The UUID of the note to render.
            **config_kwargs: Options for ExportConfig.
        """
        resp = self._raw.lookup([note_id])
        target = None
        for rec in resp.records:
            if isinstance(rec, CKRecord) and rec.recordName == note_id:
                target = rec
                break
        if not target:
            raise NoteNotFound(f"Note not found: {note_id}")

        from .rendering.exporter import build_datasource, decode_and_parse_note
        from .rendering.options import ExportConfig
        from .rendering.renderer import NoteRenderer

        config = ExportConfig(**config_kwargs)
        note = decode_and_parse_note(target)
        if not note:
            return ""

        ds, _ = build_datasource(self._raw, target, note, config)
        renderer = NoteRenderer(config)
        return renderer.render(note, ds)

    def iter_changes(self, *, since: Optional[str] = None) -> Iterable[ChangeEvent]:
        """
        Iterate change events since an optional sync token.
        Emits 'updated' for upserts and 'deleted' for tombstones.
        """
        LOGGER.debug("Iterating changes%s", f" since={since}" if since else "")
        for zone in self._raw.changes(
            zone_req=CKZoneChangesZoneReq(
                zoneID=CKZoneID(zoneName="Notes", zoneType="REGULAR_CUSTOM_ZONE"),
                desiredRecordTypes=["Note"],
                desiredKeys=self._coerce_keys(
                    [
                        CKDesiredKey.TITLE_ENCRYPTED,
                        CKDesiredKey.SNIPPET_ENCRYPTED,
                        CKDesiredKey.MODIFICATION_DATE,
                        CKDesiredKey.DELETED,
                        CKDesiredKey.FOLDER,
                        CKDesiredKey.ATTACHMENTS,
                    ]
                ),
                syncToken=since,
                reverse=False,
            )
        ):
            for rec in zone.records:
                if isinstance(rec, CKRecord):
                    deleted_flag = bool(rec.fields.get_value("Deleted") or False)
                    evt_type = "deleted" if deleted_flag else "updated"
                    yield ChangeEvent(evt_type, self._summary_from_record(rec))
                    continue

                if isinstance(rec, CKTombstoneRecord):
                    record_name = getattr(rec, "recordName", None)
                    if record_name:
                        yield ChangeEvent(
                            "deleted",
                            NoteSummary(
                                id=record_name,
                                title=None,
                                snippet=None,
                                modified_at=None,
                                folder_id=None,
                                folder_name=None,
                                is_deleted=True,
                                is_locked=False,
                            ),
                        )
                    continue

                if isinstance(rec, CKErrorItem):
                    details = {
                        "serverErrorCode": rec.serverErrorCode,
                        "reason": rec.reason,
                        "recordName": rec.recordName,
                    }
                    LOGGER.error(
                        "CloudKit error during change enumeration: %s (%s) record=%s",
                        rec.serverErrorCode or "UNKNOWN",
                        rec.reason,
                        rec.recordName,
                    )
                    raise NotesApiError(
                        (
                            "CloudKit error during change enumeration: "
                            f"{rec.serverErrorCode or 'UNKNOWN'}"
                        ),
                        payload=details,
                    )

                LOGGER.error("Unexpected record type in changes feed: %r", rec)
                raise NotesApiError(
                    "Unexpected record type in changes feed",
                    payload={"record_repr": repr(rec)},
                )

    @property
    def raw(self) -> CloudKitNotesClient:
        """
        Escape hatch: preconfigured, authenticated CloudKit client for Notes.
        """
        return self._raw

    # -------------------------- Internal helpers -----------------------------

    @staticmethod
    def _coerce_keys(keys: Optional[Iterable[object]]) -> Optional[List[str]]:
        if keys is None:
            return None
        out: List[str] = []
        for k in keys:
            if isinstance(k, CKDesiredKey):
                out.append(k.value)
            else:
                out.append(str(k))
        return out

    @staticmethod
    def _decode_encrypted(b: Optional[bytes]) -> Optional[str]:
        if b is None:
            return None
        try:
            return b.decode("utf-8", "replace")
        except Exception:
            return None

    def _extract_folder_id(self, rec: CKRecord) -> Optional[str]:
        f = rec.fields.get_field("Folder")
        if f and hasattr(f, "value") and getattr(f.value, "recordName", None):
            return f.value.recordName
        fl = rec.fields.get_field("Folders")
        if fl and hasattr(fl, "value"):
            vals = getattr(fl, "value", []) or []
            if vals:
                rn = getattr(vals[0], "recordName", None)
                if rn:
                    return rn
        return None

    def _folder_name(self, folder_id: Optional[str]) -> Optional[str]:
        if not folder_id:
            return None
        if folder_id in self._folder_name_cache:
            return self._folder_name_cache[folder_id]
        try:
            resp = self._raw.lookup([folder_id], desired_keys=["TitleEncrypted"])
            name: Optional[str] = None
            for rec in resp.records:
                if isinstance(rec, CKRecord) and rec.recordName == folder_id:
                    name = self._decode_encrypted(
                        rec.fields.get_value("TitleEncrypted")
                    )
                    break
            self._folder_name_cache[folder_id] = name
            LOGGER.debug("Folder name resolved: folder_id=%s name=%s", folder_id, name)
            return name
        except (NotesApiError, NotesAuthError, NotesRateLimited):
            self._folder_name_cache[folder_id] = None
            LOGGER.warning("Failed to resolve folder name: folder_id=%s", folder_id)
            return None

    def _summary_from_record(self, rec: CKRecord) -> NoteSummary:
        title = self._decode_encrypted(rec.fields.get_value("TitleEncrypted"))
        snippet = self._decode_encrypted(rec.fields.get_value("SnippetEncrypted"))
        modified = rec.fields.get_value(
            "ModificationDate"
        )  # already tz-aware datetime or None
        deleted = bool(rec.fields.get_value("Deleted") or False)
        folder_id = self._extract_folder_id(rec)
        folder_name = self._folder_name(folder_id)
        is_locked = (
            str(getattr(rec, "recordType", "")).lower() == "passwordprotectednote"
        )
        return NoteSummary(
            id=rec.recordName,
            title=title,
            snippet=snippet,
            modified_at=modified,
            folder_id=folder_id,
            folder_name=folder_name,
            is_deleted=deleted,
            is_locked=is_locked,
        )

    def _decode_note_body(self, rec: CKRecord) -> Optional[NoteBody]:
        """Decode TextDataEncrypted into a NoteBody (text + attachment IDs)."""

        raw = rec.fields.get_value("TextDataEncrypted")
        if not raw:
            LOGGER.debug("notes.body.missing TextDataEncrypted id=%s", rec.recordName)
            return None
        try:
            nb = BodyDecoder().decode(raw)
            if nb and isinstance(nb, NoteBody):
                return nb
            LOGGER.debug(
                "notes.body.no_text id=%s bytes=%s",
                rec.recordName,
                (
                    len(getattr(nb, "bytes", b""))
                    if nb and getattr(nb, "bytes", None)
                    else "0"
                ),
            )
            return None
        except Exception as e:
            LOGGER.warning("notes.body.decode_failed id=%s err=%s", rec.recordName, e)
            return None

    def _resolve_attachments_for_record(
        self,
        rec: CKRecord,
        *,
        attachment_ids: Optional[List[AttachmentId]] = None,
    ) -> List[Attachment]:
        """Hydrate attachment metadata for a note.

        Combines attachment identifiers from CloudKit references and the decoded
        protobuf body. Missing records are skipped gracefully.
        """

        out: List[Attachment] = []

        alias_ids: List[str] = []
        lookup_candidates: List[str] = []

        if attachment_ids:
            for aid in attachment_ids:
                ident = getattr(aid, "identifier", None)
                if ident:
                    alias_ids.append(ident)

        fld = rec.fields.get_field("Attachments")
        if fld and hasattr(fld, "value"):
            refs: List[CKReference] = getattr(fld, "value", []) or []
            for ref in refs:
                rn = getattr(ref, "recordName", None)
                if rn:
                    lookup_candidates.append(rn)
                    alias_ids.append(rn)

        # Deduplicate alias list while preserving order
        seen_alias: set[str] = set()
        ids: List[str] = []
        for cid in alias_ids:
            if cid not in seen_alias:
                seen_alias.add(cid)
                ids.append(cid)

        LOGGER.debug(
            "notes.attachments.candidates alias=%s lookup=%s",
            ids,
            lookup_candidates,
        )

        if not ids and not lookup_candidates:
            return out

        # Fetch metadata for uncached attachments
        seen_lookup: set[str] = set()
        lookup_ids: List[str] = []
        for cid in lookup_candidates + ids:
            if cid not in seen_lookup:
                seen_lookup.add(cid)
                lookup_ids.append(cid)

        missing = [aid for aid in lookup_ids if aid not in self._attachment_meta_cache]
        if missing:
            desired_keys = [
                "Filename",
                "AttachmentUTI",
                "UTI",
                "Size",
                "Thumbnail",
                "FirstAttachmentThumbnail",
                "PrimaryAsset",
                "PreviewImages",
                "PreviewAppearances",
                "FallbackImage",
                "FallbackPDF",
                "PaperAssets",
                "AttachmentIdentifier",
                "attachmentIdentifier",
                "Identifier",
            ]
            try:
                resp = self._raw.lookup(missing, desired_keys=desired_keys)
            except NotesApiError as err:
                LOGGER.debug(
                    "notes.attachments.lookup_failed ids=%s err=%s",
                    missing,
                    err,
                )
                resp = CKLookupResponse(records=[])

            for rec_a in getattr(resp, "records", []):
                if not isinstance(rec_a, CKRecord):
                    continue

                attachment = self._build_attachment_from_record(rec_a)
                if not attachment:
                    LOGGER.debug(
                        "notes.attachments.unhandled record=%s fields=%s",
                        getattr(rec_a, "recordName", None),
                        list(rec_a.fields.keys())
                        if getattr(rec_a, "fields", None)
                        else None,
                    )
                    continue

                base_id = attachment.id
                aliases = self._attachment_aliases(rec_a, base_id)
                for alias in aliases:
                    if alias == base_id:
                        att_obj = attachment
                    else:
                        att_obj = Attachment(
                            id=alias,
                            filename=attachment.filename,
                            uti=attachment.uti,
                            size=attachment.size,
                            download_url=attachment.download_url,
                            preview_url=attachment.preview_url,
                            thumbnail_url=attachment.thumbnail_url,
                        )
                    self._attachment_meta_cache[alias] = att_obj
                    LOGGER.debug(
                        "notes.attachments.cached base=%s alias=%s",
                        base_id,
                        alias,
                    )

        for aid in ids or lookup_ids:
            att = self._attachment_meta_cache.get(aid)
            if att and att not in out:
                out.append(att)

        LOGGER.debug(
            "Resolved %d attachments for note %s",
            len(out),
            getattr(rec, "recordName", None),
        )
        return out

    @staticmethod
    def _coerce_string(rec: CKRecord, names: List[str]) -> Optional[str]:
        for n in names:
            v = rec.fields.get_value(n)
            if v is None:
                continue
            if isinstance(v, bytes):
                try:
                    return v.decode("utf-8", "replace")
                except Exception:
                    continue
            if isinstance(v, str):
                return v
        return None

    @staticmethod
    def _attachment_aliases(rec: CKRecord, record_name: str) -> List[str]:
        aliases = [record_name]
        identifier = NotesService._coerce_string(
            rec, ["AttachmentIdentifier", "attachmentIdentifier", "Identifier"]
        )
        if identifier and identifier not in aliases:
            aliases.append(identifier)
        return aliases

    def _build_attachment_from_record(self, rec: CKRecord) -> Optional[Attachment]:
        aid = getattr(rec, "recordName", None)
        if not aid:
            return None

        filename = self._coerce_string(rec, ["Filename", "Name", "FileName"])
        uti = self._coerce_string(rec, ["AttachmentUTI", "UTI"])
        size = self._coerce_int(rec, ["Size", "FileSize"])

        download_url = None
        preview_url = None
        thumbnail_url = None

        download_url = download_url or self._coerce_asset_url(rec, ["PrimaryAsset"])
        download_url = download_url or self._coerce_asset_url(rec, ["FallbackPDF"])
        download_url = download_url or self._coerce_asset_url_from_list(
            rec, "FallbackPDF"
        )
        download_url = download_url or self._coerce_asset_url_from_list(
            rec, "PaperAssets"
        )

        preview_url = preview_url or self._coerce_asset_url_from_list(
            rec, "PreviewImages"
        )
        preview_url = preview_url or self._coerce_asset_url(rec, ["FallbackImage"])

        thumbnail_url = thumbnail_url or self._coerce_asset_url(
            rec, ["Thumbnail", "FirstAttachmentThumbnail"]
        )
        thumbnail_url = thumbnail_url or preview_url

        return Attachment(
            id=aid,
            filename=filename,
            uti=uti,
            size=size,
            download_url=download_url,
            preview_url=preview_url,
            thumbnail_url=thumbnail_url,
        )

    @staticmethod
    def _coerce_int(rec: CKRecord, names: List[str]) -> Optional[int]:
        for n in names:
            v = rec.fields.get_value(n)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, str) and v.isdigit():
                return int(v)
        return None

    @staticmethod
    def _coerce_asset_url(rec: CKRecord, names: List[str]) -> Optional[str]:
        for n in names:
            fld = rec.fields.get_field(n)
            if not fld:
                continue
            # ASSET/ASSETID wrapper -> value.downloadURL if present
            val = getattr(fld, "value", None)
            url = getattr(val, "downloadURL", None)
            if isinstance(url, str):
                return url
        return None

    @staticmethod
    def _coerce_asset_url_from_list(rec: CKRecord, name: str) -> Optional[str]:
        fld = rec.fields.get_field(name)
        if not fld:
            return None
        val = getattr(fld, "value", None)
        if isinstance(val, (list, tuple)):
            for token in val:
                url = None
                if isinstance(token, dict):
                    url = token.get("downloadURL")
                else:
                    url = getattr(token, "downloadURL", None)
                if isinstance(url, str) and url:
                    return url
        return None

    def _download_attachment_to(self, att: Attachment, directory: str) -> str:
        url = att.download_url or att.preview_url or att.thumbnail_url
        if not url:
            raise NotesApiError("Attachment does not expose a download URL.")
        LOGGER.debug("Downloading attachment %s to %s", att.id, directory)
        return self._raw.download_asset_to(url, directory)

    def _stream_attachment(
        self, att: Attachment, *, chunk_size: int = 65536
    ) -> Iterator[bytes]:
        url = att.download_url or att.preview_url or att.thumbnail_url
        if not url:
            raise NotesApiError("Attachment does not expose a download URL.")
        LOGGER.debug("Streaming attachment %s chunk_size=%d", att.id, chunk_size)
        yield from self._raw.download_asset_stream(url, chunk_size=chunk_size)
