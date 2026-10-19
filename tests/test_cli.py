import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from ken_burns_video.cli import app
from ken_burns_video.errors import MediaError

# Sin colores ni cortes de línea: en CI Rich fuerza ANSI y parte las opciones.
runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200", "FORCE_COLOR": None})


def inputs(tmp_path: Path) -> tuple[Path, Path]:
    image = tmp_path / "imagen con espacios.png"
    audio = tmp_path / "voz.wav"
    image.touch()
    audio.touch()
    return image, audio


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--audio" in result.stdout
    assert "--dry-run" in result.stdout


def test_dry_run_does_not_render(tmp_path: Path) -> None:
    image, audio = inputs(tmp_path)
    output = tmp_path / "demo.mp4"
    with (
        patch("ken_burns_video.cli.probe_duration", return_value=2),
        patch("ken_burns_video.cli.render_video") as render,
    ):
        result = runner.invoke(
            app, [str(image), "--audio", str(audio), "--output", str(output), "--dry-run"]
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["audio_duration"] == 2
    assert str(image.resolve()) in data["command"]
    assert not output.exists()
    render.assert_not_called()


def test_missing_input_is_friendly(tmp_path: Path) -> None:
    result = runner.invoke(
        app, [str(tmp_path / "no.png"), "--audio", "no.wav", "--output", "out.mp4"]
    )
    assert result.exit_code == 1
    assert "No existe" in result.stderr
    assert "Traceback" not in result.output


def test_reports_probe_failure(tmp_path: Path) -> None:
    image, audio = inputs(tmp_path)
    with patch("ken_burns_video.cli.probe_duration", side_effect=MediaError("Audio inválido")):
        result = runner.invoke(app, [str(image), "-a", str(audio), "-o", str(tmp_path / "out.mp4")])
    assert result.exit_code == 1
    assert "Audio inválido" in result.stderr


def test_rejects_existing_output_by_default(tmp_path: Path) -> None:
    image, audio = inputs(tmp_path)
    output = tmp_path / "out.mp4"
    output.write_bytes(b"contenido anterior")
    result = runner.invoke(app, [str(image), "-a", str(audio), "-o", str(output), "--dry-run"])
    assert result.exit_code == 1
    assert output.read_bytes() == b"contenido anterior"


def test_resolution_and_fps_are_validated_by_cli(tmp_path: Path) -> None:
    image, audio = inputs(tmp_path)
    for flag, value in [("--resolution", "4k"), ("--fps", "61")]:
        result = runner.invoke(app, [str(image), "-a", str(audio), "-o", "out.mp4", flag, value])
        assert result.exit_code == 2
