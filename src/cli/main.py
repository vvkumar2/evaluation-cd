import sys
import traceback
from pathlib import Path
import click
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from ..context_extractor import AgentTestSpaceExtractor
from ..context_extractor.agent_loader import load_agent
from ..context_extractor.schemas.prompt_schema import StructuredSystemPromptExtraction
from ..context_extractor.parsers.entity_parser import parse_entity_schema
from ..test_generator.generator import TestCaseGenerator
from ..test_runner.runner import TestRunner
from ..test_runner.html_reporter import generate_html_report
from ..config import AGENT_ENTITY_SCHEMA_FILE, AGENT_TOOLS_FILE, AGENT_ENTRY_FILE

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
    console.print("\n[bold cyan]AgentEval Pipeline[/bold cyan]")

    agent_path = Path(agent_dir)
    agent_name = agent_path.name

    try:
        client = _init_llm_client()

        # Extract
        _, output_dict = _run_extraction_stage(agent_path, agent_name, client)

        # Generate
        entity_schema_path = agent_path / AGENT_ENTITY_SCHEMA_FILE
        with open(entity_schema_path) as f:
            entity_schema_raw = yaml.safe_load(f)
        entity_schema_data = parse_entity_schema(entity_schema_raw)
        external_tools = entity_schema_raw.get("external_tools", [])
        generation_file, _ = _run_generation_stage(
            agent_name, output_dict, entity_schema_data, client, external_tools
        )

        # Run
        _run_execution_stage(agent_path, generation_file, client, agent_name)

    except Exception as e:
        console.print(f"\n[red]Pipeline failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--agent-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help=f"Path to agent directory (must contain: {AGENT_ENTRY_FILE}, {AGENT_TOOLS_FILE}, {AGENT_ENTITY_SCHEMA_FILE})",
)
def extract(agent_dir):
    """
    Extract complete test input space from an agent.
    """
    console.print("\n[bold cyan]AgentEval - Extraction[/bold cyan]")

    agent_path = Path(agent_dir)
    agent_name = agent_path.name

    try:
        client = _init_llm_client()
        _run_extraction_stage(agent_path, agent_name, client)
    except Exception as e:
        console.print(f"\n[red]Extraction failed:[/red] {e}")
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
    help=f"Path to entity schema YAML file ({AGENT_ENTITY_SCHEMA_FILE} from agent)",
)
def generate_tests(extraction_file, entity_schema):
    """
    Generate test cases from extracted agent specifications.
    """
    console.print("\n[bold cyan]AgentEval - Test Generation[/bold cyan]")

    extraction_path = Path(extraction_file)
    entity_schema_path = Path(entity_schema)

    try:
        client = _init_llm_client()
        with open(extraction_path) as f:
            extraction_data = yaml.safe_load(f)

        with open(entity_schema_path) as f:
            entity_schema_raw = yaml.safe_load(f)
        entity_schema_obj = parse_entity_schema(entity_schema_raw)
        external_tools = entity_schema_raw.get("external_tools", [])

        agent_name = extraction_data.get("agent_name", extraction_path.stem)
        _run_generation_stage(
            agent_name, extraction_data, entity_schema_obj, client, external_tools
        )
    except Exception as e:
        console.print(f"\n[red]Test generation failed:[/red] {e}")
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
    help=f"Path to agent directory (must contain {AGENT_ENTRY_FILE})",
)
def run_tests(test_file, agent_dir):
    """
    Run generated test cases against an agent.
    """
    console.print("\n[bold cyan]AgentEval - Test Runner[/bold cyan]")

    test_path = Path(test_file)
    agent_path = Path(agent_dir)

    try:
        client = _init_llm_client()
        _run_execution_stage(agent_path, test_path, client)

    except Exception as e:
        console.print(f"\n[red]Test run failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)


def _run_extraction_stage(
    agent_path: Path, agent_name: str, client
) -> tuple[Path, dict]:
    """Run extraction stage and return extraction file path and output dict."""
    extraction_file = Path("tests/extraction") / f"{agent_name}_extraction.yml"

    with console.status("[dim]Loading agent..."):
        tools_schema, entity_schema, system_prompt = load_agent(agent_path)

    console.print(
        f"  Loaded [cyan]{len(tools_schema['tools'])}[/cyan] tools, "
        f"[cyan]{len(entity_schema['entities'])}[/cyan] entities, "
        f"[cyan]{len(system_prompt)}[/cyan] char prompt"
    )

    with console.status("[dim]Extracting intents and rules..."):
        extractor = AgentTestSpaceExtractor(llm_client=client)
        _, _, _, structured_prompt_extraction, _ = extractor.extract_all(
            tools_schema=tools_schema,
            entity_schema=entity_schema,
            system_prompt=system_prompt,
            agent_dir=agent_path,
        )

    output_dict = {
        "agent_name": structured_prompt_extraction.agent_name,
        "agent_role": structured_prompt_extraction.agent_role,
        "intents": [i.model_dump() for i in structured_prompt_extraction.intents],
    }
    extraction_file.parent.mkdir(parents=True, exist_ok=True)
    with open(extraction_file, "w") as f:
        yaml.dump(output_dict, f, default_flow_style=False, sort_keys=False)

    n_intents = len(structured_prompt_extraction.intents)
    n_rules = sum(len(i.rules) for i in structured_prompt_extraction.intents)
    console.print(
        f"  [green]Extraction complete:[/green] "
        f"{n_intents} intents, {n_rules} rules "
        f"[dim]→ {extraction_file}[/dim]"
    )

    return extraction_file, output_dict


def _run_generation_stage(
    agent_name: str,
    output_dict: dict,
    entity_schema_data: object,
    client,
    external_tools: list[dict] | None = None,
) -> tuple[Path, object]:
    """Run test generation stage and return generation file path and test suite."""
    generation_file = Path("tests/generation") / f"{agent_name}_extraction_tests.yml"

    with console.status("[dim]Generating test cases..."):
        extraction = StructuredSystemPromptExtraction.model_validate(output_dict)
        generator = TestCaseGenerator(client)
        test_suite = generator.generate_test_suite(
            agent_name=extraction.agent_name,
            extraction=extraction,
            entities=entity_schema_data,
            external_tools=external_tools,
        )
    generation_file.parent.mkdir(parents=True, exist_ok=True)
    with open(generation_file, "w") as f:
        yaml.dump(test_suite.model_dump(), f, default_flow_style=False, sort_keys=False)

    categories = test_suite.count_by_category()
    cat_str = ", ".join(f"{k}: {v}" for k, v in categories.items())
    console.print(
        f"  [green]Generated {len(test_suite.test_cases)} tests:[/green] "
        f"{cat_str} "
        f"[dim]→ {generation_file}[/dim]"
    )

    return generation_file, test_suite


def _run_execution_stage(
    agent_path: Path, generation_file: Path, client, agent_name: str = None
) -> tuple[Path, object]:
    """Run test execution stage and return report file path and report."""
    if agent_name is not None:
        report_file = Path("tests/runner") / f"{agent_name}_extraction_tests_report.yml"
    else:
        report_file = Path("tests/runner") / f"{generation_file.stem}_report.yml"

    with console.status("[dim]Running tests..."):
        runner = TestRunner(llm_client=client)
        report = runner.run_tests(generation_file, agent_path)

    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        yaml.dump(report.model_dump(), f, default_flow_style=False, sort_keys=False)

    html_file = report_file.with_suffix(".html")
    generate_html_report(report, html_file)

    duration = report.duration_seconds
    if duration >= 60:
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
    else:
        duration_str = f"{duration:.1f}s"

    pass_color = (
        "green"
        if report.pass_rate >= 0.8
        else ("yellow" if report.pass_rate >= 0.6 else "red")
    )
    console.print(
        f"  [{pass_color}]{report.passed_tests}/{report.total_tests} passed[/{pass_color}] "
        f"({report.pass_rate*100:.0f}%) in {duration_str} "
        f"[dim]→ {html_file}[/dim]"
    )

    return report_file, report


def _init_llm_client():
    """Initialize OpenAI client."""
    try:
        return OpenAI()
    except Exception as e:
        console.print(f"[red]Failed to initialize OpenAI:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Set OPENAI_API_KEY environment variable")
        sys.exit(1)


if __name__ == "__main__":
    cli()
