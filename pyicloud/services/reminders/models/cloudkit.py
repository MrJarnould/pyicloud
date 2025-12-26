"""
CloudKit “wire” models for /records/query requests & responses.
Adapted from Notes service for Reminders isolated usage.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import (
    Base64Bytes,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    PlainSerializer,
    RootModel,
    TypeAdapter,
    WithJsonSchema,
    field_validator,
    model_validator,
)


def _env_extra_mode(default: str = "forbid") -> str:
    """
    Determine the extra-mode from environment vars.
    """
    raw = (os.getenv("PYICLOUD_EXTRA") or default).strip().lower()

    if raw in {"allow", "forbid", "ignore"}:
        return raw

    if raw in {"1", "true", "yes", "on", "strict"}:
        return "forbid"
    if raw in {"0", "false", "no", "off", "lenient"}:
        return "allow"

    return default


_EXTRA = _env_extra_mode()


class CKModel(BaseModel):
    """
    Project-wide base model.
    """

    model_config = ConfigDict(
        extra=_EXTRA,
        arbitrary_types_allowed=True,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

CANONICAL_MIN_MS = -62135596800000  # 0001-01-01T00:00:00Z
SENTINEL_ZERO_MS: set[int] = {
    CANONICAL_MIN_MS,
    -62135769600000,
}


def _from_millis_or_none(v):
    if isinstance(v, (int, float)):
        iv = int(v)
    elif isinstance(v, str) and v.isdigit():
        iv = int(v)
    elif isinstance(v, str) and v.startswith("0001-01-01"):
        return None
    else:
        raise TypeError("Expected milliseconds since epoch as int or digit string")
    if iv in SENTINEL_ZERO_MS or iv <= CANONICAL_MIN_MS:
        return None
    return datetime.fromtimestamp(iv / 1000.0, tz=timezone.utc)


def _to_millis(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


MillisDateTime = Annotated[
    datetime,
    BeforeValidator(_from_millis_or_none),
    PlainSerializer(_to_millis, return_type=int, when_used="json"),
    WithJsonSchema({"type": "integer", "description": "milliseconds since Unix epoch"}),
]

MillisDateTimeOrNone = Annotated[
    Optional[datetime],
    BeforeValidator(lambda v: None if v is None else _from_millis_or_none(v)),
    PlainSerializer(
        lambda v: None if v is None else _to_millis(v),
        return_type=int,
        when_used="json",
    ),
    WithJsonSchema(
        {
            "type": ["integer", "null"],
            "description": "milliseconds since Unix epoch or null sentinel",
        }
    ),
]


def _from_secs_or_millis(v):
    if isinstance(v, (int, float)):
        iv = int(v)
    elif isinstance(v, str) and v.isdigit():
        iv = int(v)
    else:
        raise TypeError("Expected seconds or milliseconds since epoch as int/str")
    if abs(iv) < 100_000_000_000:
        return datetime.fromtimestamp(iv, tz=timezone.utc)
    return datetime.fromtimestamp(iv / 1000.0, tz=timezone.utc)


def _to_secs(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


SecsOrMillisDateTime = Annotated[
    datetime,
    BeforeValidator(_from_secs_or_millis),
    PlainSerializer(_to_secs, return_type=int, when_used="json"),
    WithJsonSchema({"type": "integer", "description": "seconds since Unix epoch"}),
]


class CKZoneID(CKModel):
    zoneName: str
    ownerRecordName: Optional[str] = None
    zoneType: Optional[str] = None


class CKAuditInfo(CKModel):
    timestamp: MillisDateTime
    userRecordName: Optional[str] = None
    deviceID: Optional[str] = None


class CKParent(CKModel):
    recordName: str


class CKStableUrl(CKModel):
    routingKey: Optional[str] = None
    shortTokenHash: Optional[str] = None
    protectedFullToken: Optional[str] = None
    encryptedPublicSharingKey: Optional[str] = None
    displayedHostname: Optional[str] = None


class CKChainProtectionInfo(CKModel):
    bytes: Optional[Base64Bytes] = None
    pcsChangeTag: Optional[str] = None


class CKShare(CKModel):
    recordName: Optional[str] = None
    zoneID: Optional[CKZoneID] = None


class CKReference(CKModel):
    recordName: str
    action: Optional[str] = None
    zoneID: Optional[CKZoneID] = None


class _CKFieldBase(CKModel):
    type: str


class CKTimestampField(_CKFieldBase):
    type: Literal["TIMESTAMP"]
    value: MillisDateTimeOrNone


class CKInt64Field(_CKFieldBase):
    type: Literal["INT64"]
    value: int


class CKEncryptedBytesField(_CKFieldBase):
    type: Literal["ENCRYPTED_BYTES"]
    value: Base64Bytes


class CKReferenceField(_CKFieldBase):
    type: Literal["REFERENCE"]
    value: CKReference


class CKReferenceListField(_CKFieldBase):
    type: Literal["REFERENCE_LIST"]
    value: List[CKReference]


class CKStringField(_CKFieldBase):
    type: Literal["STRING"]
    value: str
    isEncrypted: Optional[bool] = None


class CKAssetToken(CKModel):
    fileChecksum: Optional[str] = None
    referenceChecksum: Optional[str] = None
    wrappingKey: Optional[str] = None
    downloadURL: Optional[str] = None
    size: Optional[int] = None


class CKAssetIDField(_CKFieldBase):
    type: Literal["ASSETID"]
    value: CKAssetToken


class CKAssetField(_CKFieldBase):
    type: Literal["ASSET"]
    value: CKAssetToken


class CKDoubleField(_CKFieldBase):
    type: Literal["DOUBLE"]
    value: float


class CKBytesField(_CKFieldBase):
    type: Literal["BYTES"]
    value: Base64Bytes


class CKDoubleListField(_CKFieldBase):
    type: Literal["DOUBLE_LIST"]
    value: List[float]


class CKInt64ListField(_CKFieldBase):
    type: Literal["INT64_LIST"]
    value: List[int]


class CKAssetIDListField(_CKFieldBase):
    type: Literal["ASSETID_LIST"]
    value: List[CKAssetToken]


class CKUnknownListField(_CKFieldBase):
    type: Literal["UNKNOWN_LIST"]
    value: List[JsonValue]


class CKPassthroughField(_CKFieldBase):
    type: str
    value: JsonValue


KNOWN_TAGS: frozenset[str] = frozenset(
    {
        "TIMESTAMP",
        "INT64",
        "ENCRYPTED_BYTES",
        "REFERENCE",
        "REFERENCE_LIST",
        "STRING",
        "ASSETID",
        "ASSET",
        "DOUBLE",
        "BYTES",
        "DOUBLE_LIST",
        "INT64_LIST",
        "ASSETID_LIST",
        "UNKNOWN_LIST",
    }
)


KnownCKField = Annotated[
    Union[
        CKTimestampField,
        CKInt64Field,
        CKEncryptedBytesField,
        CKReferenceField,
        CKReferenceListField,
        CKStringField,
        CKAssetIDField,
        CKAssetField,
        CKDoubleField,
        CKBytesField,
        CKDoubleListField,
        CKInt64ListField,
        CKAssetIDListField,
        CKUnknownListField,
    ],
    Field(discriminator="type"),
]


class CKFieldOpen(RootModel[Union[KnownCKField, CKPassthroughField]]):
    root: Union[KnownCKField, CKPassthroughField]

    @property
    def value(self):
        return getattr(self.root, "value", None)

    @property
    def type_tag(self) -> Optional[str]:
        return getattr(self.root, "type", None)

    def unwrap(self):
        return self.root

    @model_validator(mode="before")
    @classmethod
    def _dispatch_before(cls, obj):
        t = obj.get("type") if isinstance(obj, dict) else None

        if t in KNOWN_TAGS:
            return TypeAdapter(KnownCKField).validate_python(obj)

        if isinstance(obj, _CKFieldBase):
            return obj

        if isinstance(obj, dict) and "type" in obj and "value" in obj:
            return CKPassthroughField(**obj)

        return CKPassthroughField(type=str(t) if t else "UNKNOWN", value=obj)


class CKFields(dict[str, CKFieldOpen]):
    def __getattr__(self, name: str) -> CKFieldOpen:
        try:
            return dict.__getitem__(self, name)
        except KeyError as e:
            raise AttributeError(name) from e

    def __dir__(self):
        base = set(super().__dir__())
        return sorted(base | set(self.keys()))

    def get_field(self, key: str):
        f = self.get(key)
        if f is None:
            return None
        return f.unwrap() if hasattr(f, "unwrap") else f

    def get_value(self, key: str):
        f = self.get_field(key)
        return None if f is None else getattr(f, "value", None)


class CKRecordType(str, Enum):
    Note = "Note"
    List = "List"
    Reminder = "Reminder"
    Folder = "Folder"
    PasswordProtectedNote = "PasswordProtectedNote"


class CKRecord(CKModel):
    recordName: str
    recordType: Union[CKRecordType, str]

    fields: CKFields = Field(default_factory=CKFields)

    @field_validator("fields", mode="before")
    @classmethod
    def _coerce_fields(cls, v):
        if isinstance(v, CKFields):
            return v
        if isinstance(v, dict):
            adapter = TypeAdapter(CKFieldOpen)
            return CKFields({k: adapter.validate_python(val) for k, val in v.items()})
        return v

    pluginFields: Dict[str, JsonValue] = Field(default_factory=dict)
    recordChangeTag: Optional[str] = None
    created: Optional[CKAuditInfo] = None
    modified: Optional[CKAuditInfo] = None
    deleted: Optional[bool] = None
    zoneID: Optional[CKZoneID] = None
    parent: Optional[CKParent] = None
    displayedHostname: Optional[str] = None
    stableUrl: Optional[CKStableUrl] = None
    shortGUID: Optional[str] = None
    share: Optional[CKShare] = None
    publicPermission: Optional[str] = None
    participants: Optional[List[Dict[str, JsonValue]]] = None
    requesters: Optional[List[Dict[str, JsonValue]]] = None
    blocked: Optional[List[Dict[str, JsonValue]]] = None
    denyAccessRequests: Optional[bool] = None
    owner: Optional[Dict[str, JsonValue]] = None
    currentUserParticipant: Optional[Dict[str, JsonValue]] = None
    invitedPCS: Optional[Dict[str, JsonValue]] = None
    selfAddedPCS: Optional[Dict[str, JsonValue]] = None
    shortTokenHash: Optional[str] = None
    chainProtectionInfo: Optional[CKChainProtectionInfo] = None
    chainParentKey: Optional[str] = None
    chainPrivateKey: Optional[str] = None
    expirationTime: Optional[SecsOrMillisDateTime] = None


class CKErrorItem(CKModel):
    serverErrorCode: str
    reason: Optional[str] = None
    recordName: Optional[str] = None


class CKTombstoneRecord(CKModel):
    recordName: str
    deleted: Literal[True]
    zoneID: Optional[CKZoneID] = None


class CKQueryResponse(CKModel):
    records: List[Union[CKRecord, CKTombstoneRecord, CKErrorItem]] = Field(
        default_factory=list
    )
    continuationMarker: Optional[str] = None
    syncToken: Optional[str] = None


class CKComparator(str, Enum):
    EQUALS = "EQUALS"
    IN_ = "IN"
    CONTAINS_ANY = "CONTAINS_ANY"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUALS = "LESS_THAN_OR_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUALS = "GREATER_THAN_OR_EQUALS"
    BEGINS_WITH = "BEGINS_WITH"


class _CKFilterValueBase(CKModel):
    type: str


class CKFVString(_CKFilterValueBase):
    type: Literal["STRING"]
    value: str


class CKFVInt64(_CKFilterValueBase):
    type: Literal["INT64"]
    value: int


class CKFVStringList(_CKFilterValueBase):
    type: Literal["STRING_LIST"]
    value: List[str]


class CKFVReference(_CKFilterValueBase):
    type: Literal["REFERENCE"]
    value: CKReference


class CKFVReferenceList(_CKFilterValueBase):
    type: Literal["REFERENCE_LIST"]
    value: List[CKReference]


CKFilterValue = Annotated[
    Union[
        CKFVString,
        CKFVInt64,
        CKFVStringList,
        CKFVReference,
        CKFVReferenceList,
    ],
    Field(discriminator="type"),
]


class CKQuerySortBy(CKModel):
    fieldName: str
    ascending: Optional[bool] = None


class CKQueryFilterBy(CKModel):
    comparator: Union[CKComparator, str]
    fieldName: str
    fieldValue: CKFilterValue


class CKQueryObject(CKModel):
    recordType: str
    filterBy: Optional[List[CKQueryFilterBy]] = None
    sortBy: Optional[List[CKQuerySortBy]] = None


class CKDesiredKey(str, Enum):
    TITLE_ENCRYPTED = "TitleEncrypted"
    SNIPPET_ENCRYPTED = "SnippetEncrypted"
    MODIFICATION_DATE = "ModificationDate"
    DELETED = "Deleted"
    FOLDERS = "Folders"
    FOLDER = "Folder"
    ATTACHMENTS = "Attachments"


class CKZoneIDReq(CKModel):
    zoneName: Literal["Notes", "Reminders"]
    ownerRecordName: Optional[str] = None
    zoneType: Optional[str] = None


class CKQueryRequest(CKModel):
    query: CKQueryObject
    zoneID: CKZoneIDReq
    desiredKeys: Optional[List[Union[CKDesiredKey, str]]] = None
    resultsLimit: Optional[int] = None
    continuationMarker: Optional[str] = None


class CKLookupDescriptor(CKModel):
    recordName: str


class CKLookupRequest(CKModel):
    records: List[CKLookupDescriptor]
    zoneID: CKZoneIDReq


class CKLookupResponse(CKModel):
    records: List[Union[CKRecord, CKTombstoneRecord, CKErrorItem]]
    syncToken: Optional[str] = None


class CKZoneChangesZone(CKModel):
    records: List[Union[CKRecord, CKTombstoneRecord, CKErrorItem]] = Field(
        default_factory=list
    )
    moreComing: Optional[bool] = None
    syncToken: str
    zoneID: CKZoneID


class CKZoneChangesResponse(CKModel):
    zones: List[CKZoneChangesZone] = Field(default_factory=list)
