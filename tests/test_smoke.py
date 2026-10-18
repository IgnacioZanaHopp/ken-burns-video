"""Integración real: medios sintéticos propios y decodificación de salida."""

import json
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from ken_burns_video.media import probe_duration
from ken_burns_video.planner import VideoConfig
from ken_burns_video.render import render_video

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
        reason="Requiere ffmpeg y ffprobe",
    ),
]


def write_media(tmp_path: Path, duration: float) -> tuple[tuple[Path, ...], Path]:
    images = []
    for index, rgb in enumerate([(230, 35, 20), (25, 220, 35), (20, 35, 230)]):
        image = tmp_path / f"imagen {index}.ppm"
        image.write_bytes(b"P6\n64 48\n255\n" + bytes(rgb) * (64 * 48))
        images.append(image)
    audio = tmp_path / "tono.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(struct.pack("<h", 0) * round(8000 * duration))
    return tuple(images), audio


def inspect(path: Path) -> dict[str, object]:
    output = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.stdout)  # type: ignore[no-any-return]


def average_color(path: Path, time: float) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(time),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=1:1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    assert len(result.stdout) == 3
    return result.stdout


def test_real_720p_render_has_audio_transitions_and_expected_duration(tmp_path: Path) -> None:
    images, audio = write_media(tmp_path, 2)
    config = VideoConfig(images, audio, tmp_path / "out.mp4", fps=12, fade=0.25)
    assert probe_duration(audio) == 2
    output = render_video(config, probe_duration(audio))
    metadata = inspect(output)
    streams = metadata["streams"]
    assert isinstance(streams, list)
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1280, 720)
    assert video["pix_fmt"] == "yuv420p"
    assert int(video["nb_frames"]) == 24
    assert any(stream["codec_type"] == "audio" for stream in streams)
    assert abs(float(metadata["format"]["duration"]) - 2) < 0.15  # type: ignore[index]
    # Verifica que se vea cada imagen, y una mezcla durante el primer fundido.
    for time, channel in [(0.1, 0), (0.95, 1), (1.8, 2)]:
        color = average_color(output, time)
        assert color[channel] == max(color)
    mixed = average_color(output, 0.67)
    assert mixed[0] > 40 and mixed[1] > 40
    assert not list(tmp_path.glob(".ken-burns-*"))


def test_real_single_image_1080p_render(tmp_path: Path) -> None:
    images, audio = write_media(tmp_path, 0.5)
    output = render_video(
        VideoConfig(images[:1], audio, tmp_path / "full.mp4", resolution="1080p", fps=12, fade=0),
        0.5,
    )
    streams = inspect(output)["streams"]
    assert isinstance(streams, list)
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1920, 1080)
    assert int(video["nb_frames"]) == 6
