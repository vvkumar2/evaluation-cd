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
            "agent": {
                "name": structured_prompt_extraction.agent_name,
                "role": structured_prompt_extraction.agent_role,
            },
            "tests": [i.model_dump() for i in structured_prompt_extraction.intents],
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


def _load_agent_data(agent_path):
    """Load agent tools, entities, and system prompt."""
    console.print(f"\n[cyan]1. Loading agent from:[/cyan] {agent_path}")
    with console.status("[cyan]Loading tools, entities, system prompt..."):
        agent_data = load_agent(agent_path)
        tools_schema = agent_data["tools_schema"]
        entity_schema = agent_data["entity_schema"]
        system_prompt = agent_data["system_prompt"]

    console.print(f"[green]✓[/green] Loaded {len(tools_schema['tools'])} tools")
    console.print(f"[green]✓[/green] Loaded {len(entity_schema['entities'])} entities")
    console.print(f"[green]✓[/green] Loaded system prompt ({len(system_prompt)} chars)")
    return tools_schema, entity_schema, system_prompt


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


if __name__ == "__main__":
    cli()
