"""Validación de archivos y escritura atómica de la salida."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from .errors import ConfigurationError, RenderError
from .planner import VideoConfig, build_plan

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".ppm"}


def validate_files(config: VideoConfig) -> None:
    for path in (*config.images, config.audio):
        if not path.is_file():
            raise ConfigurationError(f"No existe el archivo de entrada: {path}")
    for path in config.images:
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ConfigurationError(f"Formato de imagen no admitido: {path.suffix}")
    if not config.output.parent.is_dir():
        raise ConfigurationError(f"No existe el directorio de salida: {config.output.parent}")
    if config.output.exists() and not config.overwrite:
        raise ConfigurationError("La salida ya existe. Usa --overwrite para reemplazarla.")
    if config.output.exists() and not config.output.is_file():
        raise ConfigurationError("La salida debe ser un archivo, no un directorio.")


def render_video(config: VideoConfig, duration: float) -> Path:
    """Un fallo conserva la salida anterior y elimina el temporal incompleto."""
    validate_files(config)
    build_plan(config, duration)  # Validar también la identidad de entradas y salida.
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".ken-burns-",
        suffix=".mp4",
        dir=config.output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        plan = build_plan(replace(config, output=temporary, overwrite=True), duration)
        try:
            # stderr va a un temporal para no retener un log arbitrariamente grande en RAM.
            with tempfile.TemporaryFile(mode="w+b") as log:
                result = subprocess.run(
                    plan.command, stdout=subprocess.DEVNULL, stderr=log, check=False
                )
                if result.returncode:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 4000))
                    detail = log.read().decode("utf-8", errors="replace").strip()
                    raise RenderError(f"ffmpeg terminó con código {result.returncode}: {detail}")
        except FileNotFoundError as error:
            raise RenderError("No se encontró ffmpeg; instálalo y revisa tu PATH.") from error
        if temporary.stat().st_size == 0:
            raise RenderError("ffmpeg no generó un video válido.")
        if config.overwrite:
            os.replace(temporary, config.output)
        else:
            # link() falla si otro proceso creó la salida durante el render.
            try:
                os.link(temporary, config.output)
            except FileExistsError as error:
                raise RenderError(
                    "La salida apareció durante el render; no se reemplazó."
                ) from error
        return config.output
    except OSError as error:
        raise RenderError(f"No fue posible escribir el video: {error.strerror}") from error
    finally:
        temporary.unlink(missing_ok=True)
