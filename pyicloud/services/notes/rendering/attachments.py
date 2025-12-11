"""
UTI-based attachment rendering strategies for Apple Notes.

This module contains a small, pure dispatcher that maps a note attachment's
type_uti (and available datasource metadata) to an HTML fragment. It
intentionally performs no I/O; all data must be provided by the caller via the
AttachmentContext.

Design:
  - AttachmentContext: immutable bundle of fields the strategies may use
  - Renderers: small classes implementing `render(ctx, render_note_cb)`
  - Dispatcher: exact UTI map, then prefix rules, then default fallback

`render_note_cb` is a callback used by the table renderer to render nested
pb.Note cells (delegates back to the main note renderer without creating a
cyclic import).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Callable, Optional

from tinyhtml import h

from .table_builder import render_table_from_mergeable


@dataclass(frozen=True)
class AttachmentContext:
    id: str
    uti: str
    title: Optional[str]
    primary_url: Optional[str]
    thumb_url: Optional[str]
    mergeable_gz: Optional[bytes]
    # Optional: preceding text in the same paragraph/line before the attachment
    prior_text: Optional[str] = None
    # Optional: behavior flags supplied by caller
    link_target: Optional[str] = None
    link_rel: Optional[str] = None
    link_referrerpolicy: Optional[str] = None
    pdf_object_height: Optional[int] = None

    def base_attrs(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        base = {
            "class": "attachment",
            "data-uti": self.uti,
            "data-id": self.id,
        }
        if extra:
            base.update(extra)
        return base


class _Renderer:
    def render(
        self, ctx: AttachmentContext, render_note_cb: Callable
    ) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class _DefaultRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        label = ctx.title or ctx.uti or "attachment"
        # No URL available → omit href entirely for clarity
        extra = {"class": "attachment link"}
        if ctx.link_rel:
            extra["rel"] = ctx.link_rel
        if ctx.link_referrerpolicy:
            extra["referrerpolicy"] = ctx.link_referrerpolicy
        if ctx.link_target:
            extra["target"] = ctx.link_target
        return h("a", **ctx.base_attrs(extra))(label).render()


class _TableRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        if ctx.mergeable_gz:
            html_tbl = render_table_from_mergeable(ctx.mergeable_gz, render_note_cb)
            if html_tbl:
                return html_tbl
        # Fallback to a link
        label = ctx.title or ctx.uti or "table"
        extra = {"class": "attachment link"}
        if ctx.link_rel:
            extra["rel"] = ctx.link_rel
        if ctx.link_referrerpolicy:
            extra["referrerpolicy"] = ctx.link_referrerpolicy
        if ctx.link_target:
            extra["target"] = ctx.link_target
        return h("a", **ctx.base_attrs(extra))(label).render()


class _UrlRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        title = ctx.title or ctx.uti or "link"
        if ctx.primary_url:
            extra_link_attrs = {}
            if ctx.link_rel:
                extra_link_attrs["rel"] = ctx.link_rel
            if ctx.link_referrerpolicy:
                extra_link_attrs["referrerpolicy"] = ctx.link_referrerpolicy
            if ctx.link_target:
                extra_link_attrs["target"] = ctx.link_target
            return h(
                "a",
                **ctx.base_attrs(
                    {
                        "href": ctx.primary_url,
                        "class": "attachment link",
                        **extra_link_attrs,
                    }
                ),
            )(title).render()
        extra = {"class": "attachment link"}
        if ctx.link_rel:
            extra["rel"] = ctx.link_rel
        if ctx.link_referrerpolicy:
            extra["referrerpolicy"] = ctx.link_referrerpolicy
        if ctx.link_target:
            extra["target"] = ctx.link_target
        return h("a", **ctx.base_attrs(extra))(title).render()


class _ImageRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        url = ctx.primary_url or ctx.thumb_url
        alt = ctx.title or ctx.uti or "image"
        if url:
            # Add responsive sizing so large images don't overflow the viewport
            attrs = ctx.base_attrs(
                {
                    "src": url,
                    "alt": alt,
                    "class": "attachment image",
                    "style": "max-width:100%;height:auto",
                }
            )
            attr_html = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())
            return f"<img {attr_html}>"
        return h("a", **ctx.base_attrs({"class": "attachment link"}))(alt).render()


class _AudioRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        if ctx.primary_url:
            attrs = ctx.base_attrs(
                {"src": ctx.primary_url, "class": "attachment audio"}
            )
            attr_html = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())
            return f"<audio controls {attr_html}></audio>"
        # title = ctx.title or ctx.uti or "audio"


class _VideoRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        if ctx.primary_url:
            attrs = ctx.base_attrs(
                {
                    "src": ctx.primary_url,
                    "class": "attachment video",
                    "controls": "controls",
                    "style": "max-width:100%;height:auto",
                }
            )
            attr_html = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())
            return f"<video {attr_html}></video>"
        title = ctx.title or ctx.uti or "video"
        return h("a", **ctx.base_attrs({"class": "attachment link"}))(title).render()


class _PdfRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        title = ctx.title or "PDF"
        url = ctx.primary_url
        if url:
            # Only embed local PDFs. Remote CloudKit URLs often force downloads and break UX.
            is_remote = url.startswith("http://") or url.startswith("https://")
            if not is_remote:
                height_px = (
                    ctx.pdf_object_height
                    if isinstance(ctx.pdf_object_height, int)
                    and ctx.pdf_object_height > 0
                    else 600
                )
                obj_attrs = ctx.base_attrs(
                    {
                        "data": url,
                        "type": "application/pdf",
                        "class": "attachment pdf",
                        # allow config to control height
                        "style": f"width:100%;height:{height_px}px",
                    }
                )
                extra_link_attrs = {}
                if ctx.link_rel:
                    extra_link_attrs["rel"] = ctx.link_rel
                if ctx.link_referrerpolicy:
                    extra_link_attrs["referrerpolicy"] = ctx.link_referrerpolicy
                if ctx.link_target:
                    extra_link_attrs["target"] = ctx.link_target
                fallback = h(
                    "a",
                    href=url,
                    **ctx.base_attrs({"class": "attachment link", **extra_link_attrs}),
                )(title)
                return h("object", **obj_attrs)(fallback).render()
            # Remote embed not allowed → use a link
            extra_link_attrs = {}
            if ctx.link_rel:
                extra_link_attrs["rel"] = ctx.link_rel
            if ctx.link_referrerpolicy:
                extra_link_attrs["referrerpolicy"] = ctx.link_referrerpolicy
            if ctx.link_target:
                extra_link_attrs["target"] = ctx.link_target
            return h(
                "a",
                **ctx.base_attrs(
                    {"href": url, "class": "attachment file", **extra_link_attrs}
                ),
            )(title).render()
        # No URL → plain label link without href
        return h("a", **ctx.base_attrs({"class": "attachment file"}))(title).render()


class _VCardRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        title = ctx.title or "contact"
        if ctx.primary_url:
            extra_link_attrs = {}
            if ctx.link_rel:
                extra_link_attrs["rel"] = ctx.link_rel
            if ctx.link_referrerpolicy:
                extra_link_attrs["referrerpolicy"] = ctx.link_referrerpolicy
            if ctx.link_target:
                extra_link_attrs["target"] = ctx.link_target
            return h(
                "a",
                **ctx.base_attrs(
                    {
                        "href": ctx.primary_url,
                        "class": "attachment contact",
                        **extra_link_attrs,
                    }
                ),
            )(title).render()
        return h("a", **ctx.base_attrs({"class": "attachment contact"}))(title).render()


class _HashtagRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        # Avoid double prefix when AltText already includes '#'
        if ctx.title:
            raw = ctx.title.strip()
            text = raw if raw.startswith("#") else f"#{raw}"
        else:
            text = ctx.uti or "hashtag"
        # Expose the normalized tag (without '#') for consumers
        tag_norm = text[1:] if text.startswith("#") else text
        attrs = ctx.base_attrs({"class": "attachment hashtag", "data-tag": tag_norm})
        return h("span", **attrs)(text).render()


class _CalculatorRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        # Render exactly what the server provides (AltTextEncrypted/TitleEncrypted/SummaryEncrypted),
        # without any additional normalization.
        label = ctx.title or ctx.uti or "result"
        return h("span", **ctx.base_attrs({"class": "attachment calc"}))(label).render()


# Graph expression (Calculate) – inline token that typically renders the left-hand
# side of an equation (e.g., "y = "). We mirror calculator's behavior and render
# a semantic, non-clickable span with a distinct class.
class _GraphExpressionRenderer(_Renderer):
    def render(self, ctx: AttachmentContext, render_note_cb: Callable) -> str:
        label = ctx.title or ctx.uti or "expression"
        return h("span", **ctx.base_attrs({"class": "attachment calc-graph"}))(
            label
        ).render()


# Singletons
_DEFAULT = _DefaultRenderer()
_TABLE = _TableRenderer()
_URL = _UrlRenderer()
_IMAGE = _ImageRenderer()
_AUDIO = _AudioRenderer()
_AUDIO = _AudioRenderer()
_VIDEO = _VideoRenderer()
_PDF = _PdfRenderer()
_VCARD = _VCardRenderer()
_HASHTAG = _HashtagRenderer()
_CALC = _CalculatorRenderer()
_GRAPH = _GraphExpressionRenderer()


# Exact UTI mappings
_EXACT: dict[str, _Renderer] = {
    "com.apple.notes.table": _TABLE,
    "public.url": _URL,
    "com.apple.m4a-audio": _AUDIO,
    "com.adobe.pdf": _PDF,
    "public.pdf": _PDF,
    "com.apple.paper.doc.pdf": _PDF,
    "public.vcard": _VCARD,
    "com.apple.notes.inlinetextattachment.hashtag": _HASHTAG,
    "com.apple.notes.inlinetextattachment.calculateresult": _CALC,
    "com.apple.notes.inlinetextattachment.calculategraphexpression": _GRAPH,
    # com.apple.paper (sketch) – prefer image-like rendering when URLs are present
    "com.apple.paper": _IMAGE,
    "com.apple.quicktime-movie": _VIDEO,
    "public.movie": _VIDEO,
    "public.video": _VIDEO,
    "public.mpeg-4": _VIDEO,
}


# Prefix matchers in order
_PREFIX: list[tuple[str, _Renderer]] = [
    ("public.image", _IMAGE),
    ("public.jpeg", _IMAGE),
    ("public.jpg", _IMAGE),
    ("public.png", _IMAGE),
    ("public.heic", _IMAGE),
    ("public.heif", _IMAGE),
    ("public.tiff", _IMAGE),
    ("public.gif", _IMAGE),
    ("public.bmp", _IMAGE),
    ("public.webp", _IMAGE),
]


def render_attachment(
    ctx: AttachmentContext, render_note_cb: Callable[[Any], str]
) -> str:
    uti = (ctx.uti or "").lower()
    r = _EXACT.get(uti)
    if r is not None:
        return r.render(ctx, render_note_cb)
    for prefix, rr in _PREFIX:
        if uti.startswith(prefix):
            return rr.render(ctx, render_note_cb)
    # fallback
    return _DEFAULT.render(ctx, render_note_cb)
