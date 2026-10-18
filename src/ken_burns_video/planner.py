"""Construcción pura de la línea de tiempo y de argumentos de ffmpeg."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .errors import ConfigurationError

Resolution = Literal["720p", "1080p"]
SIZES: dict[str, tuple[int, int]] = {"720p": (1280, 720), "1080p": (1920, 1080)}


@dataclass(frozen=True)
class VideoConfig:
    images: tuple[Path, ...]
    audio: Path
    output: Path
    resolution: Resolution = "720p"
    fps: int = 30
    fade: float = 1.0
    zoom: float = 1.12
    overwrite: bool = False


@dataclass(frozen=True)
class RenderPlan:
    command: tuple[str, ...]
    filter_graph: str
    audio_duration: float
    video_frames: int
    clip_frames: tuple[int, ...]
    fade_frames: int
    fps: int

    @property
    def video_duration(self) -> float:
        return self.video_frames / self.fps


def number(value: float) -> str:
    """Decimales independientes de locale para el parser de ffmpeg."""
    return f"{value:.9f}".rstrip("0").rstrip(".")


def build_plan(config: VideoConfig, audio_duration: float, ffmpeg: str = "ffmpeg") -> RenderPlan:
    """No toca archivos ni ejecuta procesos: permite inspeccionar el comando."""
    if not config.images:
        raise ConfigurationError("Se necesita al menos una imagen.")
    if len(config.images) > 100:
        raise ConfigurationError("Se admiten como máximo 100 imágenes por video.")
    if config.resolution not in SIZES:
        raise ConfigurationError("La resolución debe ser 720p o 1080p.")
    if isinstance(config.fps, bool) or not isinstance(config.fps, int) or not 1 <= config.fps <= 60:
        raise ConfigurationError("Los FPS deben ser un entero entre 1 y 60.")
    if not math.isfinite(audio_duration) or not 0 < audio_duration <= 86400:
        raise ConfigurationError("El audio debe durar entre 0 y 86.400 segundos (máximo un día).")
    if not math.isfinite(config.fade) or config.fade < 0:
        raise ConfigurationError("El fundido debe ser un número finito no negativo.")
    if not math.isfinite(config.zoom) or not 1 < config.zoom <= 1.5:
        raise ConfigurationError("El zoom final debe ser mayor que 1 y como máximo 1.5.")
    if config.output.suffix.lower() != ".mp4":
        raise ConfigurationError("La salida debe tener extensión .mp4.")
    if config.output.resolve() in {p.resolve() for p in (*config.images, config.audio)}:
        raise ConfigurationError("La salida no puede reemplazar un archivo de entrada.")
    width, height = SIZES[config.resolution]
    count = len(config.images)
    target_frames = math.ceil(audio_duration * config.fps)
    # Redondeo explícito al fotograma más cercano; una sola imagen no necesita xfade.
    fade_frames = math.floor(config.fade * config.fps + 0.5) if count > 1 else 0
    if count > 1 and fade_frames == 0:
        raise ConfigurationError("El fundido debe ocupar al menos un fotograma.")
    total = target_frames + (count - 1) * fade_frames
    quotient, remainder = divmod(total, count)
    clips = tuple(quotient + (index < remainder) for index in range(count))
    if min(clips) <= fade_frames or min(clips) < 2:
        raise ConfigurationError(
            "Audio demasiado corto para estas imágenes y fundidos; reduce --fade."
        )
    # Evitar que dos transiciones simultáneas consuman un clip intermedio entero.
    if any(length < 2 * fade_frames for length in clips[1:-1]):
        raise ConfigurationError("Los fundidos se solapan; reduce --fade o usa menos imágenes.")
    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y" if config.overwrite else "-n",
    ]
    for image in config.images:
        args.extend(["-loop", "1", "-framerate", str(config.fps), "-i", str(image.resolve())])
    args.extend(["-i", str(config.audio.resolve()), "-filter_complex_threads", "1"])
    filters: list[str] = []
    delta = config.zoom - 1
    for index, frames in enumerate(clips):
        progress = f"on/{frames - 1}"
        zoom = f"1+{number(delta)}*({progress})"
        position = progress
        if index % 2:
            zoom = f"{number(config.zoom)}-{number(delta)}*({progress})"
            position = f"1-({progress})"
        filters.append(
            f"[{index}:v]scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},setsar=1,"
            f"zoompan=z='{zoom}':x='(iw-iw/zoom)*({position})':y='(ih-ih/zoom)/2':"
            f"d=1:s={width}x{height}:fps={config.fps},"
            f"trim=end_frame={frames},setpts=PTS-STARTPTS,settb=AVTB,format=yuv420p[v{index}]"
        )
    previous = "v0"
    elapsed_frames = clips[0]
    for index in range(1, count):
        offset = (elapsed_frames - fade_frames) / config.fps
        label = f"mix{index}"
        filters.append(
            f"[{previous}][v{index}]xfade=transition=fade:"
            f"duration={number(fade_frames / config.fps)}:offset={number(offset)}[{label}]"
        )
        previous = label
        elapsed_frames += clips[index] - fade_frames
    filters.append(f"[{previous}]format=yuv420p[outv]")
    graph = ";".join(filters)
    args.extend(
        [
            "-filter_complex",
            graph,
            "-map",
            "[outv]",
            "-map",
            f"{count}:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            "apad",
            "-t",
            number(audio_duration),
            "-movflags",
            "+faststart",
            str(config.output.resolve()),
        ]
    )
    return RenderPlan(
        tuple(args), graph, audio_duration, target_frames, clips, fade_frames, config.fps
    )
