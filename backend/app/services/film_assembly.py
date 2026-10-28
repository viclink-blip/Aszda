"""Join scene clips and their voices into one MP4 with ffmpeg (installed in the API image).

For each scene: the clip is scaled and padded to one frame size (1280x720, or 720x1280 for
portrait) at 24 fps; the scene's voice replaces the clip's sound (a clip without a voice keeps
its own sound, or silence). If the voice is longer than the clip, the last frame is held until
the voice ends. Each scene is encoded the same way (H.264 + AAC), then the scenes are joined
without re-encoding.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_SECONDS = 600
FPS = 24


class AssemblyError(Exception):
    pass


@dataclass
class Segment:
    video: Path
    audio: Path | None = None


def _run(args: list[str]) -> str:
    try:
        # Fixed ffmpeg/ffprobe arguments; the only paths are our own temporary files.
        done = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False)  # noqa: S603
    except FileNotFoundError as exc:
        raise AssemblyError(f"{args[0]} is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise AssemblyError(f"{args[0]} took too long") from exc
    if done.returncode != 0:
        raise AssemblyError(f"{args[0]} failed: {done.stderr.strip()[-500:]}")
    return done.stdout


def _duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    try:
        return float(out.strip())
    except ValueError as exc:
        raise AssemblyError(f"could not read the length of {path.name}") from exc


def _has_audio(path: Path) -> bool:
    out = _run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                "-of", "csv=p=0", str(path)])
    return bool(out.strip())


def _encode_segment(segment: Segment, out: Path, width: int, height: int) -> float:
    video_seconds = _duration(segment.video)
    audio_seconds = _duration(segment.audio) if segment.audio else 0.0
    length = max(video_seconds, audio_seconds)
    video_chain = (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={FPS},format=yuv420p")
    if length > video_seconds + 0.05:
        video_chain += f",tpad=stop_mode=clone:stop_duration={length - video_seconds:.3f}"
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(segment.video)]
    if segment.audio:
        args += ["-i", str(segment.audio)]
        audio_source = "[1:a]"
    elif _has_audio(segment.video):
        audio_source = "[0:a]"
    else:
        args += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_source = "[1:a]"
    audio_chain = f"{audio_source}aresample=48000,aformat=channel_layouts=stereo,apad"
    args += ["-filter_complex", f"{video_chain}[v];{audio_chain}[a]", "-map", "[v]", "-map", "[a]",
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    _run(args)
    return length


def join(segments: list[Segment], out: Path, *, portrait: bool = False) -> tuple[Path, float]:
    """Join the segments in order into `out`. Returns the file and its length in seconds."""
    if not segments:
        raise AssemblyError("there are no clips to join")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AssemblyError("ffmpeg is not installed")
    width, height = (720, 1280) if portrait else (1280, 720)
    work = out.parent
    parts, total = [], 0.0
    for index, segment in enumerate(segments):
        part = work / f"part-{index:03d}.mp4"
        total += _encode_segment(segment, part, width, height)
        parts.append(part)
    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
          "-movflags", "+faststart", str(out)])
    return out, round(total, 2)
