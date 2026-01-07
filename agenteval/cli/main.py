"""Main CLI entrypoint for AgentEval."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from agenteval import __version__
from agenteval.cli.generate import generate_command
from agenteval.cli.run import run_command
from agenteval.cli.report import report_command
from agenteval.config import get_default_config_yaml

app = typer.Typer(
    name="agenteval",
    help="Evaluate conversational AI agents against knowledge bases.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"[bold blue]AgentEval[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """AgentEval - Evaluate conversational AI agents against knowledge bases."""
    pass


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Directory to initialize (defaults to current directory).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration.",
    ),
):
    """Initialize AgentEval configuration in a directory."""
    config_path = path / "agenteval.yaml"

    if config_path.exists() and not force:
        console.print(
            f"[yellow]Configuration already exists at {config_path}[/yellow]"
        )
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    # Create config file
    config_path.write_text(get_default_config_yaml())
    console.print(f"[green]✓[/green] Created configuration at [bold]{config_path}[/bold]")

    # Print next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Set your API key: [dim]export OPENAI_API_KEY=your-key[/dim]")
    console.print("  2. Generate tests: [dim]agenteval generate ./knowledge-base[/dim]")
    console.print("  3. Run evaluation: [dim]agenteval run --agent 'python agent.py' --tests tests.yaml[/dim]")


@app.command()
def generate(
    kb_path: Path = typer.Argument(
        ...,
        help="Path to knowledge base directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output: Path = typer.Option(
        Path("tests.yaml"),
        "--output",
        "-o",
        help="Output file for generated tests.",
    ),
    count: Optional[int] = typer.Option(
        None,
        "--count",
        "-n",
        help="Number of tests to generate (overrides config).",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file.",
    ),
):
    """Generate test cases from a knowledge base."""
    generate_command(kb_path, output, count, config)


@app.command()
def run(
    agent: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Agent command to execute (e.g., 'python my_agent.py').",
    ),
    tests: Path = typer.Option(
        ...,
        "--tests",
        "-t",
        help="Path to test suite YAML file.",
        exists=True,
    ),
    kb_path: Optional[Path] = typer.Option(
        None,
        "--kb",
        "-k",
        help="Path to knowledge base (for evaluation context).",
    ),
    output: Path = typer.Option(
        Path("results.json"),
        "--output",
        "-o",
        help="Output file for results.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file.",
    ),
):
    """Run an agent against a test suite."""
    run_command(agent, tests, kb_path, output, config)


@app.command()
def report(
    results: Path = typer.Argument(
        ...,
        help="Path to results JSON file.",
        exists=True,
    ),
    format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal, html, json.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file (for html/json formats).",
    ),
):
    """View or export evaluation results."""
    report_command(results, format, output)


@app.command()
def eval(
    kb_path: Path = typer.Argument(
        ...,
        help="Path to knowledge base directory.",
        exists=True,
    ),
    agent: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Agent command to execute.",
    ),
    output: Path = typer.Option(
        Path("results.json"),
        "--output",
        "-o",
        help="Output file for results.",
    ),
    count: Optional[int] = typer.Option(
        None,
        "--count",
        "-n",
        help="Number of tests to generate.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file.",
    ),
):
    """Generate tests and run evaluation in one step."""
    from tempfile import NamedTemporaryFile

    # Generate tests to a temporary file
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        tests_path = Path(f.name)

    try:
        generate_command(kb_path, tests_path, count, config)
        run_command(agent, tests_path, kb_path, output, config)
    finally:
        # Clean up temporary file
        if tests_path.exists():
            tests_path.unlink()


if __name__ == "__main__":
    app()

