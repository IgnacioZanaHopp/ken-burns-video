import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ken_burns_video.errors import ConfigurationError, RenderError
from ken_burns_video.planner import VideoConfig
from ken_burns_video.render import render_video, validate_files


def config_at(tmp_path: Path, overwrite: bool = False) -> VideoConfig:
    image, audio = tmp_path / "image.png", tmp_path / "audio.wav"
    image.touch()
    audio.touch()
    return VideoConfig((image,), audio, tmp_path / "out.mp4", overwrite=overwrite)


def test_failure_preserves_previous_output_and_cleans_temporary(tmp_path: Path) -> None:
    config = config_at(tmp_path, overwrite=True)
    config.output.write_bytes(b"original")
    with (
        patch(
            "ken_burns_video.render.subprocess.run", return_value=subprocess.CompletedProcess([], 1)
        ),
        pytest.raises(RenderError),
    ):
        render_video(config, 1)
    assert config.output.read_bytes() == b"original"
    assert not list(tmp_path.glob(".ken-burns-*"))


def test_missing_tool_cleans_temporary(tmp_path: Path) -> None:
    config = config_at(tmp_path)
    with (
        patch("ken_burns_video.render.subprocess.run", side_effect=FileNotFoundError()),
        pytest.raises(RenderError, match="ffmpeg"),
    ):
        render_video(config, 1)
    assert not config.output.exists()
    assert not list(tmp_path.glob(".ken-burns-*"))


def test_empty_render_is_not_published(tmp_path: Path) -> None:
    config = config_at(tmp_path)
    with (
        patch(
            "ken_burns_video.render.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
        ),
        pytest.raises(RenderError, match="válido"),
    ):
        render_video(config, 1)
    assert not config.output.exists()


def test_rejects_unsupported_image_and_missing_output_directory(tmp_path: Path) -> None:
    config = config_at(tmp_path)
    other = tmp_path / "image.svg"
    other.touch()
    with pytest.raises(ConfigurationError, match="Formato"):
        validate_files(VideoConfig((other,), config.audio, config.output))
    with pytest.raises(ConfigurationError, match="directorio"):
        validate_files(VideoConfig(config.images, config.audio, tmp_path / "missing" / "out.mp4"))
