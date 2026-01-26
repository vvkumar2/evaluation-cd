"""
AgentEval CLI - AI Agent Test Space Extraction

A clean, extensible CLI for extracting and analyzing AI agent capabilities.

Commands:
- extract: Extract agent test input space (tools, entities, intents, rules)
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.3.0")
def cli():
    """
    AgentEval - AI Agent Test Extraction CLI
    """
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
        # Import here to ensure dependencies are available
        from openai import OpenAI
        from ..context_extractor.agent_loader import load_agent
        from ..context_extractor import AgentTestSpaceExtractor
        import yaml
        import json

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
            result = extractor.extract_all(
                tools_schema=tools_schema,
                entity_schema=entity_schema,
                system_prompt=system_prompt,
                validate=validate,
            )

        console.print(f"   [green]✓[/green] Step 1: Parsed {len(result['tools'].tools)} tools")
        console.print(
            f"   [green]✓[/green] Step 2a: Parsed {len(result['entities'].entities)} entities"
        )
        console.print(f"   [green]✓[/green] Step 2b: Enriched entities")
        console.print(f"   [green]✓[/green] Step 3: Extracted intents/rules")
        console.print(f"   [green]✓[/green] Step 4: Validated")

        if validate and "validation" in result:
            validation = result["validation"]
            console.print(
                f"      Valid: [{'green' if validation['is_valid'] else 'red'}]{validation['is_valid']}[/]"
            )
            if validation["errors"]:
                console.print(
                    f"      Errors: [yellow]{len(validation['errors'])}[/]"
                )

        # Step 4: Convert to YAML
        console.print(f"\n[cyan]4. Converting to YAML format...")
        output_dict = {
            "agent": {
                "name": result["prompt"].agent_name,
                "role": result["prompt"].agent_role,
            },
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "description": p.description,
                            "required": p.required,
                            "enum": p.enum,
                            "constraints": [
                                {"operator": c.operator, "value": c.value}
                                for c in p.constraints
                            ],
                        }
                        for p in tool.parameters
                    ],
                }
                for tool in result["tools"].tools
            ],
            "entities": [
                {
                    "name": entity.name,
                    "description": entity.description,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.type,
                            "description": f.description,
                            "required": f.required,
                            "enum": f.enum,
                            "constraints": [
                                {"operator": c.operator, "value": c.value}
                                for c in f.constraints
                            ],
                        }
                        for f in entity.fields
                    ],
                    "thresholds": [
                        {
                            "name": t.name,
                            "value": t.value,
                            "unit": t.unit,
                            "description": t.description,
                        }
                        for t in entity.thresholds
                    ],
                }
                for entity in result["entities"].entities
            ],
            "intents": [
                {
                    "name": i.name,
                    "description": i.description,
                    "trigger_examples": i.trigger_examples,
                    "required_slots": i.required_slots,
                    "workflow": i.workflow,
                    "rules": [
                        {
                            "description": r.description,
                            "conditions": r.conditions,
                            "actions": r.actions,
                        }
                        for r in i.rules
                    ],
                    "requires_confirmation": i.requires_confirmation,
                    "outcomes": [
                        {
                            "outcome_name": o.outcome_name,
                            "description": o.description,
                            "triggering_conditions": o.triggering_conditions,
                        }
                        for o in i.outcomes
                    ],
                }
                for i in result["prompt"].intents
            ],
            "global_rules": [
                {
                    "name": r.name,
                    "description": r.description,
                    "applies_to": r.applies_to,
                    "behavior": r.behavior,
                }
                for r in result["prompt"].global_rules
            ],
            "refusals": [
                {
                    "reason": r.reason,
                    "trigger_patterns": r.trigger_patterns,
                    "response": r.response,
                }
                for r in result["prompt"].refusals
            ],
            "personality_traits": result["prompt"].personality_traits,
        }

        console.print(f"   [green]✓[/green] Converted to YAML format")

        # Step 5: Save to file
        console.print(f"\n[cyan]5. Saving results...")
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
        summary.add_row("Tools", str(len(result["tools"].tools)))
        summary.add_row("Entities", str(len(result["entities"].entities)))
        summary.add_row("Intents", str(len(result["prompt"].intents)))
        summary.add_row("Global Rules", str(len(result["prompt"].global_rules)))
        summary.add_row("Refusals", str(len(result["prompt"].refusals)))
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
