import sys
from pathlib import Path
from dotenv import load_dotenv
import click
from rich.console import Console
from rich.table import Table
from openai import OpenAI
from ..context_extractor.agent_loader import load_agent
from ..context_extractor import AgentTestSpaceExtractor
import yaml

console = Console()


@click.group()
@click.version_option(version="0.3.0")
def cli():
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
        # Step 1: Load agent
        console.print(f"\n[cyan]1. Loading agent from:[/cyan] {agent_path}")
        with console.status("[cyan]Loading tools, entities, system prompt..."):
            agent_data = load_agent(agent_path)
            tools_schema = agent_data["tools_schema"]
            entity_schema = agent_data["entity_schema"]
            system_prompt = agent_data["system_prompt"]

        console.print(f"   [green]✓[/green] Loaded {len(tools_schema['tools'])} tools")
        console.print(f"   [green]✓[/green] Loaded {len(entity_schema['entities'])} entities")
        console.print(f"   [green]✓[/green] Loaded system prompt ({len(system_prompt)} chars)")

        # Step 2: Initialize LLM
        console.print(f"\n[cyan]2. Initializing LLM client...")
        try:
            client = OpenAI()
            console.print(f"   [green]✓[/green] OpenAI client ready")
        except Exception as e:
            console.print(f"   [red]✗[/red] Failed to initialize OpenAI: {e}")
            console.print(
                "[yellow]Hint:[/yellow] Set OPENAI_API_KEY environment variable"
            )
            sys.exit(1)

        # Step 3: Extract test input space
        console.print(f"\n[cyan]3. Running extraction pipeline...")
        with console.status("[cyan]Extracting tools, entities, intents, rules..."):
            extractor = AgentTestSpaceExtractor(llm_client=client)
            extraction = extractor.extract_all(
                tools_schema=tools_schema,
                entity_schema=entity_schema,
                system_prompt=system_prompt,
            )

        console.print(f"   [green]✓[/green] Step 1: Parsed {len(extraction['tools'].tools)} tools")
        console.print(
            f"   [green]✓[/green] Step 2: Parsed {len(extraction['entities'].entities)} entities"
        )
        console.print(f"   [green]✓[/green] Step 3: Extracted intents/rules")
        console.print(f"   [green]✓[/green] Step 4: Enriched tools and entities")
        console.print(f"   [green]✓[/green] Step 5: Validated extraction")

        if validate and "validation" in extraction:
            validation = extraction["validation"]
            console.print(
                f"      Valid: [{'green' if validation['is_valid'] else 'red'}]{validation['is_valid']}[/]"
            )
            if validation["errors"]:
                console.print(
                    f"      Errors: [yellow]{len(validation['errors'])}[/]"
                )

        # Convert to YAML
        console.print(f"\n[cyan]6. Converting to YAML format...")

        output_dict = {
            "agent": {
                "name": extraction["prompt"].agent_name,
                "role": extraction["prompt"].agent_role,
            },
            "tools": extraction["tools"].model_dump()["tools"],
            "entities": extraction["entities"].model_dump()["entities"],
            "intents": [i.model_dump() for i in extraction["prompt"].intents],
            "global_rules": [r.model_dump() for r in extraction["prompt"].global_rules],
            "refusals": [r.model_dump() for r in extraction["prompt"].refusals],
        }

        console.print(f"   [green]✓[/green] Converted to YAML format")

        console.print(f"\n[cyan]7. Saving results...")
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w") as f:
            yaml.dump(output_dict, f, default_flow_style=False, sort_keys=False)

        console.print(f"   [green]✓[/green] Results saved to: {output}")
        console.print(f"   [green]✓[/green] File size: {output.stat().st_size} bytes")

        # Summary table
        console.print("\n[bold green]✓ Extraction Complete![/bold green]")
        summary = Table(title="Extraction Summary", show_header=True)
        summary.add_column("Component", style="cyan")
        summary.add_column("Count", justify="right", style="magenta")
        summary.add_row("Tools", str(len(extraction["tools"].tools)))
        summary.add_row("Entities", str(len(extraction["entities"].entities)))
        summary.add_row("Intents", str(len(extraction["prompt"].intents)))
        summary.add_row("Global Rules", str(len(extraction["prompt"].global_rules)))
        summary.add_row("Refusals", str(len(extraction["prompt"].refusals)))
        console.print(summary)

        console.print(
            f"\n[green]✓ Output saved to:[/green] {output}\n"
        )

    except ImportError as e:
        console.print(f"\n[red]✗ Import error:[/red] {e}")
        console.print(
            "[yellow]Hint:[/yellow] Make sure required dependencies are installed"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Extraction failed:[/red] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
