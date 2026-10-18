"""Genera paisajes geométricos y un tono propios; no usa material externo."""

from __future__ import annotations

import argparse
import math
import struct
import wave
import zlib
from pathlib import Path


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))


def landscape(path: Path, index: int) -> None:
    width, height = 960, 540
    palettes = [
        ((246, 219, 181), (211, 133, 94), (138, 72, 57), (64, 59, 59)),
        ((204, 224, 216), (128, 168, 155), (68, 116, 112), (29, 66, 75)),
        ((218, 211, 234), (164, 152, 189), (109, 98, 148), (50, 55, 91)),
    ]
    sky, hill, middle, foreground = palettes[index]
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # Filtro PNG de fila: ninguno.
        for x in range(width):
            nx, ny = x / width, y / height
            color = tuple(int(value * (1 - ny * 0.12)) for value in sky)
            if (nx - 0.72) ** 2 + (ny - 0.25) ** 2 < 0.006:
                color = (255, 245, 216)
            if ny > 0.55 + 0.15 * math.sin(nx * 5 + index):
                color = hill
            if ny > 0.70 + 0.11 * math.sin(nx * 7 + 2 + index):
                color = middle
            if ny > 0.86 + 0.07 * math.sin(nx * 9 + index):
                color = foreground
            pixels.extend(color)
    header = struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(pixels), 9))
        + chunk(b"IEND", b"")
    )


def tone(path: Path, duration: float) -> None:
    rate = 48000
    frames = bytearray()
    for index in range(round(rate * duration)):
        time = index / rate
        envelope = min(1, time / 0.25, (duration - time) / 0.25)
        value = math.sin(2 * math.pi * 220 * time) + 0.4 * math.sin(2 * math.pi * 330 * time)
        frames.extend(struct.pack("<h", round(3500 * max(0, envelope) * value)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "assets")
    parser.add_argument("--duration", type=float, default=6.0)
    args = parser.parse_args()
    if not math.isfinite(args.duration) or not 1 <= args.duration <= 60:
        parser.error("La duración debe estar entre 1 y 60 segundos.")
    args.output.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        landscape(args.output / f"paisaje-{index + 1}.png", index)
    tone(args.output / "tono.wav", args.duration)
    print(f"Tres imágenes originales y un tono de {args.duration:g} s en {args.output}")


if __name__ == "__main__":
    main()
