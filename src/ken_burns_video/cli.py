"""Interfaz de línea de comandos con Typer."""

from __future__ import annotations

import json
import shlex
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from .errors import VideoError
from .media import probe_duration
from .planner import VideoConfig, build_plan
from .render import render_video, validate_files

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


class Size(StrEnum):
    hd = "720p"
    full_hd = "1080p"


@app.command()
def main(
    images: Annotated[list[Path], typer.Argument(help="Imágenes en el orden de aparición.")],
    audio: Annotated[Path, typer.Option("--audio", "-a", help="Archivo con la pista de audio.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Archivo MP4 de salida.")],
    resolution: Annotated[Size, typer.Option(help="Resolución horizontal de salida.")] = Size.hd,
    fps: Annotated[int, typer.Option(min=1, max=60, help="Fotogramas por segundo.")] = 30,
    fade: Annotated[float, typer.Option(help="Segundos de fundido entre imágenes.")] = 1.0,
    zoom: Annotated[
        float, typer.Option(help="Factor máximo de zoom, mayor que 1 y hasta 1.5.")
    ] = 1.12,
    overwrite: Annotated[
        bool, typer.Option(help="Reemplaza la salida solo si el render termina.")
    ] = False,
    dry_run: Annotated[bool, typer.Option(help="Muestra el plan JSON sin renderizar.")] = False,
) -> None:
    """Crea un video con zoom, paneo y fundidos, ajustado al audio."""
    config = VideoConfig(
        tuple(images),
        audio,
        output,
        resolution.value,
        fps,
        fade,
        zoom,
        overwrite,
    )
    try:
        validate_files(config)
        duration = probe_duration(audio)
        plan = build_plan(config, duration)
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "audio_duration": duration,
                        "video_duration": plan.video_duration,
                        "fps": fps,
                        "clip_frames": plan.clip_frames,
                        "fade_frames": plan.fade_frames,
                        "command": plan.command,
                        "display_command": shlex.join(plan.command),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            path = render_video(config, duration)
            typer.echo(f"Video creado: {path} ({duration:.2f} s, {resolution.value}, {fps} fps)")
    except VideoError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    except OSError as error:
        typer.echo(f"Error de archivos: {error.strerror}", err=True)
        raise typer.Exit(1) from error


if __name__ == "__main__":
    app()
