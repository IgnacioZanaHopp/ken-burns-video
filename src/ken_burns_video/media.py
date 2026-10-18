"""Inspección acotada de audio con ffprobe."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from .errors import MediaError


def probe_duration(audio: Path, ffprobe: str = "ffprobe") -> float:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_type,duration:format=duration",
        "-of",
        "json",
        str(audio.resolve()),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as error:
        raise MediaError("No se encontró ffprobe; instala ffmpeg y revisa tu PATH.") from error
    except subprocess.TimeoutExpired as error:
        raise MediaError("ffprobe superó el tiempo de espera de 30 segundos.") from error
    except (subprocess.CalledProcessError, OSError) as error:
        raise MediaError("No se pudo leer el audio con ffprobe.") from error
    try:
        data: Any = json.loads(result.stdout)
        streams = data["streams"]
        if not streams or streams[0].get("codec_type") != "audio":
            raise ValueError("sin pista de audio")
        # Preferir la duración de la pista; la del contenedor puede incluir video adicional.
        value = streams[0].get("duration")
        if value in (None, "N/A"):
            value = data.get("format", {}).get("duration")
        duration = float(value)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duración inválida")
        return duration
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        raise MediaError(
            "El archivo no contiene una pista de audio con duración válida."
        ) from error
