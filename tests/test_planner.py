from dataclasses import replace
from pathlib import Path

import pytest

from ken_burns_video.errors import ConfigurationError
from ken_burns_video.planner import VideoConfig, build_plan


@pytest.fixture
def config() -> VideoConfig:
    return VideoConfig(
        (Path("primera.png"), Path("segunda con espacios.png"), Path("tercera.png")),
        Path("voz.wav"),
        Path("salida.mp4"),
    )


def test_distributes_frames_and_preserves_audio_duration(config: VideoConfig) -> None:
    plan = build_plan(config, 10)
    assert plan.clip_frames == (120, 120, 120)
    assert plan.fade_frames == 30
    assert sum(plan.clip_frames) - 2 * plan.fade_frames == plan.video_frames == 300
    assert "duration=1:offset=3[mix1]" in plan.filter_graph
    assert "duration=1:offset=6[mix2]" in plan.filter_graph
    assert plan.video_duration == 10


def test_rounding_is_bounded_to_one_frame(config: VideoConfig) -> None:
    plan = build_plan(replace(config, fps=24, fade=0.23), 10.03)
    assert plan.clip_frames == (85, 84, 84)
    assert plan.fade_frames == 6
    assert sum(plan.clip_frames) - 12 == plan.video_frames
    assert 0 <= plan.video_duration - plan.audio_duration < 1 / 24
    assert all(value >= 2 * plan.fade_frames for value in plan.clip_frames)


def test_graph_alternates_zoom_and_pan(config: VideoConfig) -> None:
    plan = build_plan(config, 10)
    assert "zoompan=z='1+0.12*(on/119)'" in plan.filter_graph
    assert "zoompan=z='1.12-0.12*(on/119)'" in plan.filter_graph
    assert "x='(iw-iw/zoom)*(1-(on/119))'" in plan.filter_graph
    assert plan.filter_graph.count("settb=AVTB") == 3
    assert plan.filter_graph.count("setsar=1") == 3
    assert plan.filter_graph.count("xfade=transition=fade") == 2
    assert "s=1280x720:fps=30" in plan.filter_graph
    assert "scale=2560:1440:force_original_aspect_ratio=increase" in plan.filter_graph


def test_command_is_argument_vector_with_unambiguous_mapping(config: VideoConfig) -> None:
    plan = build_plan(config, 10)
    command = plan.command
    assert "-n" in command and "-y" not in command
    assert command[command.index("-filter_complex") + 1] == plan.filter_graph
    assert command[command.index("-map") + 1] == "[outv]"
    assert "3:a:0" in command
    assert str(config.images[1].resolve()) in command
    assert command[-1] == str(config.output.resolve())
    assert command[command.index("-t") + 1] == "10"
    assert "libx264" in command and "aac" in command and "+faststart" in command


def test_single_image_has_no_transition(config: VideoConfig) -> None:
    plan = build_plan(
        replace(config, images=(config.images[0],), fade=0, resolution="1080p", overwrite=True), 2
    )
    assert plan.clip_frames == (60,)
    assert plan.fade_frames == 0
    assert "xfade" not in plan.filter_graph
    assert "s=1920x1080" in plan.filter_graph
    assert "1:a:0" in plan.command
    assert "-y" in plan.command


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), 86401])
def test_invalid_duration(config: VideoConfig, duration: float) -> None:
    with pytest.raises(ConfigurationError):
        build_plan(config, duration)


@pytest.mark.parametrize(
    "changes",
    [
        {"images": ()},
        {"images": (Path("a.png"),) * 101},
        {"fps": 0},
        {"fps": 61},
        {"fps": 1.5},
        {"fps": True},
        {"resolution": "4k"},
        {"fade": -1},
        {"fade": float("nan")},
        {"fade": 0},
        {"zoom": 1},
        {"zoom": 1.51},
        {"zoom": float("inf")},
        {"output": Path("out.mkv")},
    ],
)
def test_invalid_configuration(config: VideoConfig, changes: dict[str, object]) -> None:
    with pytest.raises(ConfigurationError):
        build_plan(replace(config, **changes), 10)  # type: ignore[arg-type]


def test_rejects_overlapping_transitions_and_short_audio(config: VideoConfig) -> None:
    with pytest.raises(ConfigurationError, match="corto"):
        build_plan(config, 0.1)
    with pytest.raises(ConfigurationError, match="solapan"):
        build_plan(config, 2)


def test_never_replaces_input_even_with_overwrite(config: VideoConfig) -> None:
    config = replace(config, audio=Path("audio.mp4"), output=Path("audio.mp4"), overwrite=True)
    with pytest.raises(ConfigurationError, match="entrada"):
        build_plan(config, 10)
