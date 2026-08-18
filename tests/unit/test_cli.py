from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_help_lists_the_version_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_version_command_prints_the_package_version():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output
