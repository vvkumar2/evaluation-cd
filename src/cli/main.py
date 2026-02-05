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
from ..context_extractor.validation import AgentTestValidator
from ..context_extractor.schemas.prompt_schema import StructuredSystemPromptExtraction
from ..context_extractor.parsers.entity_parser import parse_entity_schema, EntitySchemaList
from ..test_generator.generator import TestCaseGenerator

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
    help="Path to agent directory (must contain: agent.py, tools.py, entity_schema.yml)",
)
@click.option(
    "--validate",
    is_flag=True,
    default=True,
    help="Validate extracted outputs (default: True)",
)
def extract(agent_dir, validate):
    """
    Extract complete test input space from an agent.
    """
    console.print("\n[bold cyan]AgentEval - Test Input Space Extractor[/bold cyan]")
    console.print("=" * 70)

    agent_path = Path(agent_dir)
    agent_name = agent_path.name
    output = Path("tests/extraction") / f"{agent_name}_extraction.yml"

    try:
        # Load agent data
        tools_schema, entity_schema, system_prompt = _load_agent_data(agent_path)

        # Initialize LLM client
        client = _init_llm_client()

        # Run extraction pipeline
        tools, code_rules, entities, structured_prompt_extraction, validation_result = (
            _run_extraction(
                client, tools_schema, entity_schema, system_prompt, agent_path
            )
        )

        # Print extraction steps
        _print_extraction_steps()

        if validate:
            color = "green" if validation_result.is_valid else "red"
            console.print(
                f"[green]✓[/green] Valid: [{color}]{validation_result.is_valid}[/]"
            )
            if validation_result.errors:
                console.print(
                    f"[yellow]⚠[/yellow] Errors: [yellow]{len(validation_result.errors)}[/]"
                )

        # Convert to YAML and save
        console.print("\n[cyan]7. Converting to YAML format...")
        output_dict = {
            "agent_name": structured_prompt_extraction.agent_name,
            "agent_role": structured_prompt_extraction.agent_role,
            "intents": [i.model_dump() for i in structured_prompt_extraction.intents],
        }
        console.print("[green]✓[/green] Converted to YAML format")

        console.print("\n[cyan]8. Saving results...")
        _save_extraction_results(output_dict, output)

        # Handle validation errors
        if validate:
            _handle_validation_errors(validation_result, output)

        # Print summary
        _print_summary(tools, code_rules, entities, structured_prompt_extraction)

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
    output = Path("tests/generation") / f"{extraction_path.stem}_tests.yml"

    try:
        # Load extracted rules
        console.print(f"\n[cyan]1. Loading extraction file...[/cyan]")
        with open(extraction_path) as f:
            extraction_data = yaml.safe_load(f)

        # Load entity schema
        console.print("[cyan]2. Loading entity schema...[/cyan]")
        with open(entity_schema_path) as f:
            entity_schema = parse_entity_schema(yaml.safe_load(f))

        # Initialize LLM client
        client = _init_llm_client()

        # Generate test cases
        console.print("\n[cyan]3. Generating test cases from rules...[/cyan]")
        test_suite = _generate_test_cases(
            extraction_data, entity_schema, client
        )

        # Save results
        console.print("\n[cyan]4. Saving test cases...[/cyan]")
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w") as f:
            yaml.dump(test_suite.model_dump(), f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓[/green] Results saved to: {output}")
        console.print(f"[green]✓[/green] File size: {output.stat().st_size} bytes")

        # Print summary
        console.print(f"\n[bold green]✓ Test Generation Complete![/bold green]")
        console.print(f"Summary: {test_suite.summary()}")

    except Exception as e:
        console.print(f"\n[red]✗ Test generation failed:[/red] {e}")
        traceback.print_exc()
        sys.exit(1)
        

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
    console.print("\n[cyan]2. Initializing LLM client...")
    try:
        client = OpenAI()
        console.print("[green]✓[/green] OpenAI client ready")
        return client
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize OpenAI: {e}")
        console.print("[yellow]Hint:[/yellow] Set OPENAI_API_KEY environment variable")
        sys.exit(1)


def _run_extraction(client, tools_schema, entity_schema, system_prompt, agent_path):
    """Run extraction pipeline."""
    console.print("\n[cyan]3. Running extraction pipeline...")
    with console.status("[cyan]Extracting tools, entities, intents, rules..."):
        extractor = AgentTestSpaceExtractor(llm_client=client)
        return extractor.extract_all(
            tools_schema=tools_schema,
            entity_schema=entity_schema,
            system_prompt=system_prompt,
            agent_dir=agent_path,
        )


def _print_extraction_steps():
    """Print extraction pipeline steps."""
    console.print("[green]✓[/green] Step 1: Parsed tools")
    console.print("[green]✓[/green] Step 2: Parsed entities")
    console.print("[green]✓[/green] Step 3: Extracted tests")
    console.print("[green]✓[/green] Step 4: Enriched tools and entities")
    console.print("[green]✓[/green] Step 5: Enriched tests to structured format")
    console.print("[green]✓[/green] Step 6: Validated extraction")


def _save_extraction_results(output_dict, output):
    """Save extraction results to YAML file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(output_dict, f, default_flow_style=False, sort_keys=False)
    console.print(f"[green]✓[/green] Results saved to: {output}")
    console.print(f"[green]✓[/green] File size: {output.stat().st_size} bytes")


def _handle_validation_errors(validation_result, output):
    """Handle and write validation errors."""
    if validation_result.errors:
        validator = AgentTestValidator()
        validator.write_validation_errors(validation_result, output)
        error_path = output.parent / f"{output.stem}_errors.json"
        console.print(f"[yellow]⚠[/yellow] Validation errors written to: {error_path}")


def _print_summary(tools, code_rules, entities, structured_prompt_extraction):
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


def _generate_test_cases(extraction_data, entity_schema, client):
    """Generate test cases from extraction data using LLM."""
    # Reconstruct schema objects from YAML dicts
    extraction = StructuredSystemPromptExtraction.model_validate(extraction_data)
    entities = EntitySchemaList.model_validate(entity_schema)

    # Generate test cases
    generator = TestCaseGenerator(client)
    test_suite = generator.generate_test_suite(
        agent_name=extraction.agent_name,
        extraction=extraction,
        entities=entities,
    )

    return test_suite

if __name__ == "__main__":
    cli()
