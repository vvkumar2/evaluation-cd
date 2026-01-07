"""Run command implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.progress import Progress, BarColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from agenteval.config import Config
from agenteval.knowledge import KnowledgeBaseParser, KnowledgeIndexer
from agenteval.executor import CLIAgent
from agenteval.evaluator import FactualAccuracyEvaluator, CompletenessEvaluator, ConsistencyEvaluator
from agenteval.models import TestSuite, TestResult, RunResult, TestStatus, EvaluationScore

console = Console()


def run_command(
    agent_cmd: str,
    tests_path: Path,
    kb_path: Optional[Path],
    output: Path,
    config_path: Optional[Path],
) -> None:
    """Run an agent against a test suite."""
    # Load configuration
    config = Config.load(config_path)

    console.print(f"\n[bold]Running evaluation[/bold]")
    console.print(f"  Agent: [cyan]{agent_cmd}[/cyan]")
    console.print(f"  Tests: [cyan]{tests_path}[/cyan]")
    if kb_path:
        console.print(f"  Knowledge Base: [cyan]{kb_path}[/cyan]")
    console.print()

    # Load test suite
    with open(tests_path) as f:
        suite_data = yaml.safe_load(f)
    suite = TestSuite.from_dict(suite_data)

    console.print(f"Loaded {len(suite.tests)} tests from [bold]{suite.name}[/bold]\n")

    # Load knowledge base if provided
    kb = None
    indexer = None
    if kb_path and kb_path.exists():
        parser = KnowledgeBaseParser()
        kb = parser.parse(kb_path)
        indexer = KnowledgeIndexer()
        indexer.index(kb)

    # Initialize agent
    agent = CLIAgent(agent_cmd)

    # Initialize evaluators
    factual_eval = FactualAccuracyEvaluator(config.llm, kb, indexer)
    completeness_eval = CompletenessEvaluator(config.llm)
    consistency_eval = ConsistencyEvaluator(config.llm)

    # Run tests
    run_result = RunResult(
        suite_name=suite.name,
        started_at=datetime.now(),
        metadata={"agent": agent_cmd, "tests_path": str(tests_path)},
    )

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running tests...", total=len(suite.tests))

        for test in suite.tests:
            try:
                # Execute agent
                start_time = datetime.now()
                response = agent.send(test.message)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # Evaluate response
                scores = EvaluationScore()
                evaluations = []

                # Factual accuracy
                factual_result = factual_eval.evaluate(
                    test.message, response, test.expected
                )
                scores.factual_accuracy = factual_result.score
                evaluations.append(factual_result)

                # Completeness
                completeness_result = completeness_eval.evaluate(
                    test.message, response, test.expected
                )
                scores.completeness = completeness_result.score
                evaluations.append(completeness_result)

                # Consistency (for consistency tests)
                if test.expected.consistency_with:
                    # Find the original test result
                    original_result = next(
                        (r for r in run_result.results if r.test_id == test.expected.consistency_with),
                        None,
                    )
                    if original_result and original_result.agent_response:
                        consistency_result = consistency_eval.evaluate(
                            response, original_result.agent_response
                        )
                        scores.consistency = consistency_result.score
                        evaluations.append(consistency_result)

                result = TestResult(
                    test_id=test.id,
                    status=TestStatus.PASSED if scores.weighted_score >= config.evaluation.pass_threshold else TestStatus.FAILED,
                    agent_response=response,
                    scores=scores,
                    evaluations=evaluations,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                result = TestResult(
                    test_id=test.id,
                    status=TestStatus.ERROR,
                    error_message=str(e),
                )

            run_result.results.append(result)
            progress.update(task, advance=1)

    run_result.completed_at = datetime.now()

    # Save results
    with open(output, "w") as f:
        json.dump(run_result.to_dict(), f, indent=2)

    console.print(f"\n[green]✓[/green] Results saved to [bold]{output}[/bold]")

    # Print summary table
    console.print()
    _print_summary(run_result)


def _print_summary(run_result: RunResult) -> None:
    """Print a summary table of the run results."""
    table = Table(title="Evaluation Summary", show_header=True, header_style="bold")

    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Tests", str(run_result.total_tests))
    table.add_row("Passed", f"[green]{run_result.passed_tests}[/green]")
    table.add_row("Failed", f"[red]{run_result.failed_tests}[/red]")
    table.add_row("Errors", f"[yellow]{run_result.error_tests}[/yellow]")
    table.add_row("Pass Rate", f"{run_result.pass_rate:.1f}%")
    table.add_row("Avg Score", f"{run_result.average_score:.3f}")
    table.add_row("Duration", f"{run_result.duration_ms}ms")

    console.print(table)

    # Pass/fail indicator
    if run_result.pass_rate >= 80:
        console.print("\n[bold green]✓ PASSED[/bold green] (≥80% pass rate)")
    else:
        console.print("\n[bold red]✗ FAILED[/bold red] (<80% pass rate)")

