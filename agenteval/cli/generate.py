"""Generate command implementation."""

from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from agenteval.config import Config
from agenteval.knowledge import KnowledgeBaseParser, KnowledgeIndexer
from agenteval.generator import HeuristicGenerator, LLMGenerator
from agenteval.models import TestSuite

console = Console()


def generate_command(
    kb_path: Path,
    output: Path,
    count: Optional[int],
    config_path: Optional[Path],
) -> None:
    """Generate test cases from a knowledge base."""
    # Load configuration
    config = Config.load(config_path)

    # Override count if specified
    if count is not None:
        config.generation.count = count

    console.print(f"\n[bold]Generating tests from:[/bold] {kb_path}")
    console.print(f"[bold]Target count:[/bold] {config.generation.count}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Parse knowledge base
        task = progress.add_task("Parsing knowledge base...", total=None)
        parser = KnowledgeBaseParser()
        kb = parser.parse(kb_path)
        progress.update(task, completed=True)
        console.print(f"  [green]✓[/green] Parsed {kb.document_count} documents ({kb.total_words} words)")

        # Step 2: Index knowledge base
        task = progress.add_task("Indexing documents...", total=None)
        indexer = KnowledgeIndexer()
        indexer.index(kb)
        progress.update(task, completed=True)
        console.print(f"  [green]✓[/green] Indexed for search")

        # Step 3: Generate heuristic tests
        task = progress.add_task("Generating heuristic tests...", total=None)
        heuristic_gen = HeuristicGenerator()
        heuristic_tests = heuristic_gen.generate(kb, config)
        progress.update(task, completed=True)
        console.print(f"  [green]✓[/green] Generated {len(heuristic_tests)} heuristic tests")

        # Step 4: Generate LLM tests
        task = progress.add_task("Generating LLM tests...", total=None)
        llm_gen = LLMGenerator(config.llm)

        # Calculate how many more tests we need
        remaining = config.generation.count - len(heuristic_tests)
        if remaining > 0:
            llm_tests = llm_gen.generate(kb, remaining, config.generation.types)
            progress.update(task, completed=True)
            console.print(f"  [green]✓[/green] Generated {len(llm_tests)} LLM tests")
        else:
            llm_tests = []
            progress.update(task, completed=True)
            console.print("  [dim]Skipped LLM generation (enough heuristic tests)[/dim]")

    # Combine tests
    all_tests = heuristic_tests + llm_tests

    # Create test suite
    suite = TestSuite(
        name=f"Tests for {kb_path.name}",
        knowledge_base_path=str(kb_path),
        tests=all_tests,
        metadata={
            "generated_by": "agenteval",
            "source": str(kb_path),
        },
    )

    # Write to output file
    with open(output, "w") as f:
        yaml.dump(suite.to_dict(), f, default_flow_style=False, sort_keys=False)

    console.print(f"\n[green]✓[/green] Generated {len(all_tests)} tests → [bold]{output}[/bold]")

    # Summary
    qa_count = len(suite.qa_tests)
    edge_count = len(suite.edge_case_tests)
    consistency_count = len(suite.consistency_tests)

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  • Q&A tests: {qa_count}")
    console.print(f"  • Edge case tests: {edge_count}")
    console.print(f"  • Consistency tests: {consistency_count}")

