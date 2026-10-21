"""Detect a file's real type from its first bytes ("magic numbers").

The file name and the browser-supplied Content-Type are both under the
uploader's control, so they are never trusted on their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import AssetKind


@dataclass(frozen=True)
class FileType:
    mime: str
    kind: AssetKind
    extension: str


def sniff(head: bytes) -> FileType | None:
    """Return the detected type for an allowed format, or None."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileType("image/png", AssetKind.IMAGE, "png")
    if head.startswith(b"\xff\xd8\xff"):
        return FileType("image/jpeg", AssetKind.IMAGE, "jpg")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return FileType("image/webp", AssetKind.IMAGE, "webp")
    if head.startswith((b"GIF87a", b"GIF89a")):
        return FileType("image/gif", AssetKind.IMAGE, "gif")
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return FileType("video/quicktime", AssetKind.VIDEO, "mov")
        if brand in (b"M4A ", b"M4B "):
            return FileType("audio/mp4", AssetKind.AUDIO, "m4a")
        return FileType("video/mp4", AssetKind.VIDEO, "mp4")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return FileType("video/webm", AssetKind.VIDEO, "webm")
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return FileType("audio/wav", AssetKind.AUDIO, "wav")
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return FileType("audio/mpeg", AssetKind.AUDIO, "mp3")
    if head.startswith(b"OggS"):
        return FileType("audio/ogg", AssetKind.AUDIO, "ogg")
    if head.startswith(b"fLaC"):
        return FileType("audio/flac", AssetKind.AUDIO, "flac")
    return None


# Formats a provider might return that we save without sniffing an upload.
EXTENSIONS = {
    "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif",
    "video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov",
    "audio/mpeg": "mp3", "audio/wav": "wav", "audio/ogg": "ogg", "audio/flac": "flac",
    "audio/aac": "aac", "audio/opus": "opus", "audio/mp4": "m4a", "text/markdown": "md",
}
