"""Explore Notes: print HTML for most recent notes.

Run: uv run explore_notes.py --username you@example.com [--password ...]

Focus: fetch the first 20 most recent notes and try to print an HTML
rendering of each note's body (inline styles; attachments shown as placeholders).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from typing import Any, List, Optional

from rich.console import Console
from rich.logging import RichHandler

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudServiceUnavailable

# CloudKit model helpers for the raw escape hatch demo
from pyicloud.services.notes.models.cloudkit import CKRecord
from pyicloud.services.notes.rendering.exporter import (
    decode_and_parse_note,
)
from pyicloud.services.notes.rendering.options import ExportConfig
from pyicloud.utils import get_password

console = Console()

logger = logging.getLogger("notes.explore")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Explore Notes service")
    p.add_argument("--username", dest="username", required=True, help="Apple ID")
    p.add_argument(
        "--password",
        dest="password",
        default="",
        help="Apple ID password (optional; keyring if omitted)",
    )
    p.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable verbose logs and detailed output",
    )
    p.add_argument(
        "--cookie-dir",
        dest="cookie_dir",
        default="",
        help="Directory to store session cookies",
    )
    p.add_argument(
        "--china-mainland",
        action="store_true",
        dest="china_mainland",
        default=False,
        help="Set if Apple ID region is China mainland",
    )
    p.add_argument(
        "--max",
        dest="max_items",
        type=int,
        default=20,
        help="How many most recent notes to render (default: 20)",
    )
    p.add_argument(
        "--title",
        dest="title",
        default="",
        help="Only render notes whose title exactly matches this string",
    )
    p.add_argument(
        "--title-contains",
        dest="title_contains",
        default="",
        help="Only render notes whose title contains this substring (case-insensitive)",
    )
    p.add_argument(
        "--output-dir",
        dest="output_dir",
        default=os.path.join("workspace", "notes_html"),
        help="Directory to write rendered HTML files (default: workspace/notes_html)",
    )
    p.add_argument(
        "--full-page",
        dest="full_page",
        action="store_true",
        default=False,
        help="Wrap output in a full HTML page (title, base styles)",
    )
    p.add_argument(
        "--dump-runs",
        dest="dump_runs",
        action="store_true",
        default=False,
        help="Dump attribute runs and write an annotated HTML mapping",
    )
    p.add_argument(
        "--download-assets",
        dest="download_assets",
        action="store_true",
        default=False,
        help="Download embeddable assets (e.g., PDFs) and rewrite HTML to reference local files",
    )
    p.add_argument(
        "--assets-dir",
        dest="assets_dir",
        default=os.path.join("exports", "assets"),
        help="Directory to store downloaded assets when --download-assets is set (default: exports/assets)",
    )
    p.add_argument(
        "--export-mode",
        dest="export_mode",
        choices=["archival", "lightweight"],
        default="archival",
        help="Export intent: 'archival' downloads assets for stable, offline HTML (default); 'lightweight' skips downloads for quick previews",
    )
    # HTML export/render configuration flags
    p.add_argument(
        "--notes-debug",
        dest="notes_debug",
        action="store_true",
        default=False,
        help="Enable detailed Notes export debug (datasource/attachments)",
    )
    p.add_argument(
        "--preview-appearance",
        dest="preview_appearance",
        choices=["light", "dark"],
        default="light",
        help="Select which preview appearance to prefer for image previews (light/dark)",
    )
    p.add_argument(
        "--pdf-height",
        dest="pdf_height",
        type=int,
        default=600,
        help="Height in pixels for embedded PDF objects (default: 600)",
    )
    return p.parse_args()


def ensure_auth(api: PyiCloudService) -> None:
    if api.requires_2fa:
        logger.info("Two-factor authentication required.")
        code = input("Enter the 2FA code: ")
        if not api.validate_2fa_code(code):
            raise RuntimeError("Failed to verify 2FA code")
        if not api.is_trusted_session:
            api.trust_session()
    elif api.requires_2sa:
        logger.info("Two-step authentication required.")
        devices: List[dict[str, Any]] = api.trusted_devices
        if not devices:
            raise RuntimeError("No trusted devices available for 2SA")
        for i, d in enumerate(devices):
            name = d.get("deviceName", f"SMS to {d.get('phoneNumber', 'unknown')}")
            logger.info(f"  {i}: {name}")
        sel = input("Select device index [0]: ").strip()
        try:
            idx = int(sel) if sel else 0
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(devices):
            logger.warning("Invalid selection; defaulting to device 0")
            idx = 0
        device = devices[idx]
        if not api.send_verification_code(device):
            raise RuntimeError("Failed to send verification code")
        code = input("Enter verification code: ")
        if not api.validate_verification_code(device, code):
            raise RuntimeError("Failed to verify code")


# (Former inline helper render_note_html_fragment removed; responsibilities now live
# in pyicloud.services.notes_rendering.exporter.)


def main() -> None:
    # Rich logging with timestamps
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_time=True,
                log_time_format="%H:%M:%S",
            )
        ],
    )
    # Library debug logs toggled via --verbose (see below)

    args = parse_args()
    # Elapsed-time helper
    import time

    t0 = time.perf_counter()

    def phase(msg: str) -> None:
        try:
            dt = time.perf_counter() - t0
            logger.info(f"[+{dt:0.3f}s] {msg}")
        except Exception:
            logger.info(msg)

    if args.verbose:
        logging.getLogger("pyicloud.services.notes.service").setLevel(logging.DEBUG)
        logging.getLogger("pyicloud.services.notes.client").setLevel(logging.DEBUG)

    debug_dir = os.path.join("workspace", "notes_debug")
    if os.getenv("PYICLOUD_NOTES_DEBUG"):
        logger.info(
            f"[yellow]Notes validation debug is enabled[/yellow].\n"
            f"Errors and raw payloads will be saved under: [bold]{debug_dir}[/bold]"
        )

    phase("bootstrap: starting authentication")
    pw = args.password or get_password(args.username)
    api = PyiCloudService(
        apple_id=args.username,
        password=pw,
        china_mainland=args.china_mainland,
        cookie_directory=args.cookie_dir or None,
    )
    ensure_auth(api)
    phase("bootstrap: authentication complete")

    try:
        phase("service: initializing NotesService")
        notes = api.notes  # new NotesService
        phase("service: NotesService ready")
    except PyiCloudServiceUnavailable as e:
        logger.error(f"Notes service not available: {e}")
        return

    max_items = max(1, int(args.max_items))
    out_dir = args.output_dir
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create output directory '{out_dir}': {e}")
        return

    def _safe_name(s: Optional[str]) -> str:
        if not s:
            return "untitled"
        # collapse whitespace and strip
        s = re.sub(r"\s+", " ", s).strip()
        # keep alnum, space, dash, underscore; replace others with '-'
        s = re.sub(r"[^\w\- ]+", "-", s)
        # limit length
        return s[:60] or "untitled"

    # ---- Recents (fetch and render HTML) ----
    # Choose which notes to render
    def _match_title(t: Optional[str]) -> bool:
        if not t:
            return False
        if args.title and t == args.title:
            return True
        if args.title_contains and args.title_contains.lower() in t.lower():
            return True
        return False

    candidates = []
    if args.title or args.title_contains:
        logger.info("[bold]\nSearching notes by title[/bold]")
        phase(
            f"selection: recents-first title search (exact='{args.title}' contains='{args.title_contains}')"
        )
        try:
            # 1) Fast pass over recents
            window = max(500, max_items * 50)
            seen: set[str] = set()
            for n in notes.recents(limit=window):
                if _match_title(n.title or ""):
                    if n.id not in seen:
                        candidates.append(n)
                        seen.add(n.id)
                    if len(candidates) >= max_items:
                        break
            phase(
                f"selection: recents matched {len(candidates)} candidate(s) in window={window}"
            )

            # 2) Fallback: scan full feed if needed
            if len(candidates) < max_items:
                phase("selection: fallback to full feed scan (iter_all)")
                for n in notes.iter_all(page_size=200):
                    if _match_title(n.title or "") and n.id not in seen:
                        candidates.append(n)
                        seen.add(n.id)
                        if len(candidates) >= max_items:
                            break
                phase(f"selection: total matched {len(candidates)} candidate(s)")

            # Ensure newest-first order (recents already are, iter_all might not be)
            try:
                epoch = __import__("datetime").datetime(
                    1970, 1, 1, tzinfo=__import__("datetime").timezone.utc
                )
                candidates.sort(key=lambda x: x.modified_at or epoch, reverse=True)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Title search failed, falling back to recents: {e}")
    if not candidates:
        logger.info("[bold]\nMost Recent Notes (HTML)[/bold]")
        phase(f"selection: loading {max_items} most recent notes")
        for n in notes.recents(limit=max_items):
            candidates.append(n)
        phase(f"selection: using {len(candidates)} recent note(s)")

    for idx, item in enumerate(candidates):
        phase(f"note[{idx}]: start '{(item.title or 'untitled')}'")
        console.rule(f"idx: {idx}")
        console.print(item, end="\n\n")

        console.print("item.title:")
        console.print(item.title, end="\n\n")

        ck = notes.raw
        # Lookup the note record and ask for body + attachments
        phase(f"note[{idx}]: ck.lookup(TextDataEncrypted,Attachments)")
        resp = ck.lookup([item.id], desired_keys=["TextDataEncrypted", "Attachments"])

        console.print("resp:")
        console.print(resp, end="\n\n")

        note_rec = None
        for r in resp.records:
            if isinstance(r, CKRecord) and r.recordName == item.id:
                note_rec = r
                break
        if not note_rec:
            return None

        # Decode + parse into pb.Note
        phase(f"note[{idx}]: decode+parse start")
        proto_note = decode_and_parse_note(note_rec)
        phase(f"note[{idx}]: decode+parse ok")

        console.print("proto_note:")
        console.print(proto_note, end="\n\n")

        # Use NoteExporter from the library for the heavy lifting
        from pyicloud.services.notes.rendering.exporter import NoteExporter

        phase(f"note[{idx}]: exporter init")
        config = ExportConfig(
            debug=bool(args.notes_debug),
            preview_appearance=str(args.preview_appearance).strip().lower(),
            pdf_object_height=int(args.pdf_height or 600),
            # Pass download preferences if ExportConfig supported them, or logic handle in exporter
        )
        # NoteExporter handles downloading if we call export.
        # But wait, logic in script had `should_download_assets`.
        # NoteExporter currently ALWAYS downloads assets in `export`.
        # If we want to skip assets (lightweight mode), we might need to modify NoteExporter
        # or use a different method.
        # For now, let's assume standard behavior is full export, as "archival" is default.

        exporter = NoteExporter(ck, config=config)
        phase(f"note[{idx}]: export start")

        # We pass the filename to control naming exactly as before
        title = item.title or "Apple Note"
        safe = _safe_name(title)
        short_id = (item.id or "note")[:8]
        fname = f"{idx:02d}_{safe}_{short_id}.html"

        try:
            path = exporter.export(note_rec, output_dir=out_dir, filename=fname)
            phase(f"note[{idx}]: export done -> {path}")
            if path:
                console.print(f"[green]Saved:[/green] {path}")
            else:
                console.print("[red]Export returned None (skipped?)[/red]")
        except Exception as e:
            phase(f"note[{idx}]: export failed: {e}")
            console.print(f"[red]Export failed:[/red] {e}")

        # Optional: dump attribute runs for debugging (requires proto_note)
        if args.dump_runs:
            try:
                from pyicloud.services.notes.rendering.debug_tools import (
                    annotate_note_runs_html,
                    dump_runs_text,
                )

                console.rule("attribute runs (utf16 mapping)")
                console.print(dump_runs_text(proto_note))
                # Also show merged runs to mirror renderer chunking
                try:
                    from pyicloud.services.notes.rendering.debug_tools import (
                        map_merged_runs,
                    )

                    merged = map_merged_runs(proto_note)
                    console.rule("merged runs (post-merge)")
                    lines = []
                    for row in merged:
                        raw = str(row.get("text", ""))
                        pretty = (
                            raw.replace("\n", "⏎\n")
                            .replace("\u2028", "⤶\n")
                            .replace("\x00", "␀")
                            .replace("\ufffc", "{OBJ}")
                        )
                        lines.append(
                            f"[{row['index']:03d}] off={row['utf16_start']:<5} len={row['utf16_len']:<4} text=“{pretty}”"
                        )
                    console.print("\n".join(lines))
                except Exception:
                    pass
                runs_dir = os.path.join("workspace", "notes_runs")
                os.makedirs(runs_dir, exist_ok=True)
                runs_name = f"{idx:02d}_{_safe_name(item.title)}_{(item.id or 'note')[:8]}_runs.html"
                with open(
                    os.path.join(runs_dir, runs_name), "w", encoding="utf-8"
                ) as f:
                    f.write(annotate_note_runs_html(proto_note))
                console.print(
                    f"[cyan]Saved runs map:[/cyan] {os.path.join(runs_dir, runs_name)}"
                )
            except Exception as e:
                console.print(f"[red]Failed to dump runs:[/red] {e}")

    # Summary
    try:
        import time as _t

        logger.info(f"[+{(_t.perf_counter() - t0):0.3f}s] completed")
    except Exception:
        logger.info("completed")


if __name__ == "__main__":
    main()
