"""
AgentEval CLI - AI Agent Testing Platform

Commands:
- parse: Analyze codebase and extract agent capabilities
- generate: Generate test cases from parsed capabilities or codebase
"""

import click
import json
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..analyzer.comprehensive_parser import ComprehensiveParser

console = Console()


@click.group()
@click.version_option(version='0.2.0')
def cli():
    """
    AgentEval - AI Agent Testing Platform

    Parse codebases and generate LLM-powered test cases for AI agents.
    """
    pass


@cli.command()
@click.option(
    '--codebase',
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help='Path to agent codebase directory'
)
@click.option(
    '--business-logic',
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help='Path to business_logic.yaml file describing agent capabilities'
)
@click.option(
    '--output',
    type=click.Path(),
    default='tests/parsed_codebase.json',
    help='Output file for parsed capabilities (JSON format)'
)
def parse(codebase, business_logic, output):
    """
    Parse agent codebase and extract complete capabilities.

    Analyzes Python code to extract:
    - Business rules and policies
    - All execution paths through functions
    - Decision points and branches
    - Constants and validation rules

    Example:
        agenteval parse --codebase ./my-agent --business-logic ./business_logic.yaml --output capabilities.json
    """
    console.print("\n[bold cyan]AgentEval - Codebase Parser[/bold cyan]")
    console.print("=" * 70)

    codebase_path = Path(codebase)
    output_path = Path(output)
    business_logic_path = Path(business_logic) if business_logic else None

    # Parse
    console.print(f"\n[cyan]Parsing codebase:[/cyan] {codebase_path}")
    if business_logic_path:
        console.print(f"[cyan]Business logic:[/cyan] {business_logic_path}")

    parser = ComprehensiveParser()
    capabilities = parser.parse(codebase_path, business_logic_path)

    # Summary
    console.print("\n[bold green]✓ Parsing Complete[/bold green]\n")

    total_paths = sum(len(w.paths) for w in capabilities.workflows)

    summary_table = Table(title="Extracted Capabilities")
    summary_table.add_column("Component", style="cyan")
    summary_table.add_column("Count", justify="right", style="magenta")
    summary_table.add_row("Workflows", str(len(capabilities.workflows)))
    summary_table.add_row("Total Paths", str(total_paths))
    summary_table.add_row("Constants", str(len(capabilities.constants)))

    console.print(summary_table)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = parser.export_to_dict()

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    console.print(f"\n[green]✓ Saved to:[/green] {output_path}")

if __name__ == '__main__':
    cli()
