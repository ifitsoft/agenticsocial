from typer.testing import CliRunner

from agenticsocial import __version__
from agenticsocial.cli import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output
