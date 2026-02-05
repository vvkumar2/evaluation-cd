import sys
import traceback
from pathlib import Path
import click
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table
from ..context_extractor import AgentTestSpaceExtractor
from ..context_extractor.agent_loader import load_agent
from ..context_extractor.schemas.prompt_schema import StructuredSystemPromptExtraction
from ..context_extractor.parsers.entity_parser import parse_entity_schema
from ..test_generator.generator import TestCaseGenerator
from ..test_runner.runner import TestRunner

console = Console()


@click.group()
@click.version_option(version="0.3.0")
def cli():
    """Entry point for AgentEval CLI."""
    load_dotenv()


@cli.command()
@click.option(
    "--agent-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Path to agent directory",
)
def run_pipeline(agent_dir):
    """
    Run the complete evaluation pipeline: extract → generate → run tests.
    Saves intermediate outputs from each stage.
    """
    console.print("\n[bold cyan]AgentEval - Complete Pipeline[/bold cyan]")
    console.print("=" * 70)

    agent_path = Path(agent_dir)
    agent_name = agent_path.name

    try:
        # Initialize LLM client once
        client = _init_llm_client()

        # Stage 1: Extract
        _, output_dict = _run_extraction_stage(agent_path, agent_name, client)

        # Stage 2: Generate Tests
        entity_schema_path = agent_path / "entity_schema.yml"
        with open(entity_schema_path) as f:
            entity_schema_data = parse_entity_schema(yaml.safe_load(f))
        generation_file, _ = _run_generation_stage(
            agent_name, output_dict, entity_schema_data, client
        )

        # Stage 3: Run Tests
        _run_execution_stage(agent_path, generation_file, client, agent_name)

    except Exception as e:
        console.print(f"\n[red]✗ Pipeline failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--agent-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Path to agent directory (must contain: agent.py, tools.py, entity_schema.yml)",
)
def extract(agent_dir):
    """
    Extract complete test input space from an agent.
    """
    console.print("\n[bold cyan]AgentEval - Test Input Space Extractor[/bold cyan]")
    console.print("=" * 70)

    agent_path = Path(agent_dir)
    agent_name = agent_path.name

    try:
        client = _init_llm_client()
        _run_extraction_stage(agent_path, agent_name, client)
    except Exception as e:
        console.print(f"\n[red]✗ Extraction failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--extraction-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to extraction YAML file (output from extract command)",
)
@click.option(
    "--entity-schema",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to entity schema YAML file (entity_schema.yml from agent)",
)
def generate_tests(extraction_file, entity_schema):
    """
    Generate test cases from extracted agent specifications.
    """
    console.print("\n[bold cyan]AgentEval - Test Case Generator[/bold cyan]")
    console.print("=" * 70)

    extraction_path = Path(extraction_file)
    entity_schema_path = Path(entity_schema)

    try:
        client = _init_llm_client()
        console.print("\n[cyan]1. Loading extraction file...[/cyan]")
        with open(extraction_path) as f:
            extraction_data = yaml.safe_load(f)

        console.print("[cyan]2. Loading entity schema...[/cyan]")
        with open(entity_schema_path) as f:
            entity_schema_obj = parse_entity_schema(yaml.safe_load(f))

        # Generate tests using stage helper
        agent_name = extraction_data.get("agent_name", extraction_path.stem)
        _run_generation_stage(agent_name, extraction_data, entity_schema_obj, client)
    except Exception as e:
        console.print(f"\n[red]✗ Test generation failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--test-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to test cases YAML file (output from generate-tests command)",
)
@click.option(
    "--agent-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Path to agent directory (must contain agent.py and backend_service.py)",
)
def run_tests(test_file, agent_dir):
    """
    Run generated test cases against an agent.
    """
    console.print("\n[bold cyan]AgentEval - Test Runner[/bold cyan]")
    console.print("=" * 70)

    test_path = Path(test_file)
    agent_path = Path(agent_dir)

    try:
        client = _init_llm_client()
        _run_execution_stage(agent_path, test_path, client)

    except Exception as e:
        console.print(f"\n[red]✗ Test run failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


def _run_extraction_stage(
    agent_path: Path, agent_name: str, client
) -> tuple[Path, dict]:
    """Run extraction stage and return extraction file path and output dict."""
    console.print("\n[bold]Extraction[/bold]")
    extraction_file = Path("tests/extraction") / f"{agent_name}_extraction.yml"

    tools_schema, entity_schema, system_prompt = _load_agent_data(agent_path)

    console.print("[cyan]Running extraction pipeline...[/cyan]")
    with console.status("[cyan]Extracting tools, entities, intents, rules..."):
        extractor = AgentTestSpaceExtractor(llm_client=client)
        tools, code_rules, entities, structured_prompt_extraction, _ = (
            extractor.extract_all(
                tools_schema=tools_schema,
                entity_schema=entity_schema,
                system_prompt=system_prompt,
                agent_dir=agent_path,
            )
        )

    output_dict = {
        "agent_name": structured_prompt_extraction.agent_name,
        "agent_role": structured_prompt_extraction.agent_role,
        "intents": [i.model_dump() for i in structured_prompt_extraction.intents],
    }
    extraction_file.parent.mkdir(parents=True, exist_ok=True)
    with open(extraction_file, "w") as f:
        yaml.dump(output_dict, f, default_flow_style=False, sort_keys=False)
    console.print(f"[green]✓[/green] Extraction saved to: {extraction_file}")

    _print_extraction_summary(tools, code_rules, entities, structured_prompt_extraction)

    return extraction_file, output_dict


def _run_generation_stage(
    agent_name: str, output_dict: dict, entity_schema_data: object, client
) -> tuple[Path, object]:
    """Run test generation stage and return generation file path and test suite.

    Args:
        agent_name: Name of the agent
        output_dict: Extraction output dict
        entity_schema_data: Parsed entity schema
        client: LLM client
    """
    console.print("\n[bold]Test Generation[/bold]")
    generation_file = Path("tests/generation") / f"{agent_name}_extraction_tests.yml"
    console.print("[cyan]Generating test cases...[/cyan]")

    with console.status("[cyan]Creating tests from extracted rules..."):
        extraction = StructuredSystemPromptExtraction.model_validate(output_dict)
        generator = TestCaseGenerator(client)
        test_suite = generator.generate_test_suite(
            agent_name=extraction.agent_name,
            extraction=extraction,
            entities=entity_schema_data,
        )
    generation_file.parent.mkdir(parents=True, exist_ok=True)
    with open(generation_file, "w") as f:
        yaml.dump(test_suite.model_dump(), f, default_flow_style=False, sort_keys=False)
    console.print(f"[green]✓[/green] Tests saved to: {generation_file}")

    _print_generation_summary(test_suite)

    return generation_file, test_suite


def _run_execution_stage(
    agent_path: Path, generation_file: Path, client, agent_name: str = None
) -> tuple[Path, object]:
    """Run test execution stage and return report file path and report.

    Args:
        agent_path: Path to agent directory
        generation_file: Path to generation file (or used to derive report filename if agent_name not given)
        client: LLM client
        agent_name: Optional agent name (for pipeline stage labeling); if not given, derives from generation_file
    """
    if agent_name is not None:
        console.print("\n[bold]Stage 3: Test Execution[/bold]")
        report_file = Path("tests/runner") / f"{agent_name}_extraction_tests_report.yml"
    else:
        report_file = Path("tests/runner") / f"{generation_file.stem}_report.yml"

    console.print("[cyan]Running tests...[/cyan]")
    with console.status("[cyan]Executing test cases and evaluating results..."):
        runner = TestRunner(llm_client=client)
        report = runner.run_tests(generation_file, agent_path)

    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        yaml.dump(report.model_dump(), f, default_flow_style=False, sort_keys=False)
    console.print(f"[green]✓[/green] Report saved to: {report_file}")

    _print_execution_summary(report)

    return report_file, report


def _load_agent_data(agent_path: Path) -> tuple[dict, dict, str]:
    """Load agent tools, entities, and system prompt."""
    console.print(f"\n[cyan]1. Loading agent from:[/cyan] {agent_path}")
    with console.status("[cyan]Loading tools, entities, system prompt..."):
        tools_schema, entity_schema, system_prompt = load_agent(agent_path)

    console.print(f"[green]✓[/green] Loaded {len(tools_schema['tools'])} tools")
    console.print(f"[green]✓[/green] Loaded {len(entity_schema['entities'])} entities")
    console.print(f"[green]✓[/green] Loaded system prompt ({len(system_prompt)} chars)")
    return (tools_schema, entity_schema, system_prompt)


def _init_llm_client():
    """Initialize OpenAI client."""
    console.print("\n[cyan]Initializing LLM client...")
    try:
        client = OpenAI()
        console.print("[green]✓[/green] OpenAI client ready")
        return client
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize OpenAI: {e}")
        console.print("[yellow]Hint:[/yellow] Set OPENAI_API_KEY environment variable")
        sys.exit(1)


def _print_extraction_summary(
    tools, code_rules, entities, structured_prompt_extraction
):
    """Print extraction summary table."""
    console.print("\n[bold green]✓ Extraction Complete![/bold green]")
    summary = Table(title="Extraction Summary", show_header=True)
    summary.add_column("Component", style="cyan")
    summary.add_column("Count", justify="right", style="magenta")
    summary.add_row("Tools", str(len(tools.tools)))
    summary.add_row("Code Rules", str(len(code_rules.rules)))
    summary.add_row("Entities", str(len(entities.entities)))
    summary.add_row("Intents", str(len(structured_prompt_extraction.intents)))
    console.print(summary)


def _print_generation_summary(test_suite):
    """Print generation summary table."""
    console.print("\n[bold green]✓ Test Generation Complete![/bold green]")
    summary = Table(title="Test Generation Summary", show_header=True)
    summary.add_column("Category", style="cyan")
    summary.add_column("Count", justify="right", style="magenta")
    for category, count in test_suite.count_by_category().items():
        summary.add_row(category, str(count))
    console.print(summary)


def _print_execution_summary(report) -> None:
    """Print execution summary table."""
    console.print("\n[bold green]✓ Test Execution Complete![/bold green]")
    summary = Table(title="Test Execution Summary", show_header=True)
    summary.add_column("Test", style="cyan")
    summary.add_column("Status", justify="right", style="magenta")
    summary.add_row("Total Tests", str(report.total_tests))
    summary.add_row("Passed", str(report.passed_tests))
    summary.add_row("Failed", str(report.failed_tests))
    console.print(summary)


if __name__ == "__main__":
    cli()
