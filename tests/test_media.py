import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ken_burns_video.errors import MediaError
from ken_burns_video.media import probe_duration


def test_reads_audio_stream_before_container_duration() -> None:
    data = {"streams": [{"codec_type": "audio", "duration": "2.25"}], "format": {"duration": "10"}}
    with patch(
        "ken_burns_video.media.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, json.dumps(data)),
    ) as run:
        assert probe_duration(Path("audio con espacios.wav")) == 2.25
        args, kwargs = run.call_args
        assert args[0][-1] == str(Path("audio con espacios.wav").resolve())
        assert kwargs["timeout"] == 30
        assert kwargs["check"] is True


def test_falls_back_to_container_duration() -> None:
    data = {"streams": [{"codec_type": "audio", "duration": "N/A"}], "format": {"duration": "3.5"}}
    with patch(
        "ken_burns_video.media.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, json.dumps(data)),
    ):
        assert probe_duration(Path("audio.wav")) == 3.5


@pytest.mark.parametrize(
    "data",
    [
        "{",
        "null",
        "[]",
        "{}",
        '{"streams": []}',
        '{"streams": [{"codec_type": "video", "duration": "5"}]}',
        '{"streams": [{"codec_type": "audio", "duration": "nan"}]}',
        '{"streams": [{"codec_type": "audio", "duration": "-1"}]}',
    ],
)
def test_rejects_invalid_audio(data: str) -> None:
    with (
        patch(
            "ken_burns_video.media.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, data),
        ),
        pytest.raises(MediaError),
    ):
        probe_duration(Path("audio.wav"))


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(),
        subprocess.TimeoutExpired("ffprobe", 30),
        subprocess.CalledProcessError(1, "ffprobe"),
    ],
)
def test_wraps_process_failures(error: Exception) -> None:
    with (
        patch("ken_burns_video.media.subprocess.run", side_effect=error),
        pytest.raises(MediaError),
    ):
        probe_duration(Path("audio.wav"))
