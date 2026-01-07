"""
Main CLI for AgentEval.

Commands:
- generate: Analyze codebase and generate test cases
- run: Execute tests against an agent
- evaluate: Evaluate test execution results
- full: Run the complete pipeline (generate -> run -> evaluate)
"""

import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from ..analyzer.parser import CodeParser
from ..analyzer.extractor import BusinessLogicExtractor
from ..analyzer.scorer import TestPriorityScorer
from ..generator.generator import TestCaseGenerator
from ..runner.runner import TestRunner, AgentExecutor, AgentType
from ..evaluator.evaluator import Evaluator

console = Console()


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """
    AgentEval - AI Agent Testing Platform

    Analyze codebases, generate test cases, and evaluate AI agents.
    """
    pass


@cli.command()
@click.option(
    '--codebase',
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help='Path to codebase directory to analyze'
)
@click.option(
    '--output',
    type=click.Path(),
    default='tests/generated_tests.yaml',
    help='Output file for generated tests'
)
@click.option(
    '--max-tests',
    type=int,
    default=20,
    help='Maximum number of test cases to generate'
)
@click.option(
    '--use-llm/--no-llm',
    default=False,
    help='Use LLM to enrich test cases'
)
def generate(codebase, output, max_tests, use_llm):
    """
    Analyze codebase and generate test cases.

    Extracts business logic, policies, and validation rules from your code,
    then generates realistic conversation test cases.
    """
    console.print("\n[bold cyan]AgentEval Test Generator[/bold cyan]")
    console.print("=" * 70)

    codebase_path = Path(codebase)
    output_path = Path(output)

    with Progress() as progress:
        # Step 1: Parse codebase
        task1 = progress.add_task("[cyan]Parsing codebase...", total=100)
        parser = CodeParser()
        analyses = parser.parse_directory(codebase_path)
        progress.update(task1, completed=100)

        console.print(f"✓ Parsed {len(analyses)} Python files")

        # Step 2: Extract business logic
        task2 = progress.add_task("[cyan]Extracting business logic...", total=100)
        extractor = BusinessLogicExtractor()
        logic = extractor.extract(analyses)
        progress.update(task2, completed=100)

        console.print(f"✓ Found {len(logic.policies)} policies")
        console.print(f"✓ Found {len(logic.scenarios)} testable scenarios")

        # Step 3: Generate test cases
        task3 = progress.add_task("[cyan]Generating test cases...", total=100)
        generator = TestCaseGenerator()
        test_cases = generator.generate(logic, max_tests=max_tests, use_llm=use_llm)
        progress.update(task3, completed=100)

        # Step 4: Save to file
        task4 = progress.add_task("[cyan]Saving test cases...", total=100)
        generator.save_to_yaml(test_cases, output_path)
        progress.update(task4, completed=100)

    console.print(f"\n✓ Generated {len(test_cases)} test cases → [green]{output_path}[/green]")

    # Show summary table
    table = Table(title="Generated Test Cases")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="magenta")

    categories = {}
    for tc in test_cases:
        categories[tc.category] = categories.get(tc.category, 0) + 1

    for category, count in sorted(categories.items()):
        table.add_row(category, str(count))

    console.print("\n")
    console.print(table)


@cli.command()
@click.option(
    '--tests',
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help='Path to test cases YAML file'
)
@click.option(
    '--agent',
    required=True,
    help='Agent command (e.g., "python agent.py") or function path'
)
@click.option(
    '--agent-type',
    type=click.Choice(['subprocess', 'python', 'http']),
    default='subprocess',
    help='Type of agent interface'
)
@click.option(
    '--output',
    type=click.Path(),
    default='results/execution_results.json',
    help='Output file for execution results'
)
@click.option(
    '--max-tests',
    type=int,
    help='Limit number of tests to run'
)
@click.option(
    '--timeout',
    type=int,
    default=30,
    help='Timeout per agent response (seconds)'
)
def run(tests, agent, agent_type, output, max_tests, timeout):
    """
    Execute test cases against an agent.

    Runs multi-turn conversations with your agent and captures responses.
    """
    console.print("\n[bold cyan]AgentEval Test Runner[/bold cyan]")
    console.print("=" * 70)

    tests_path = Path(tests)
    output_path = Path(output)

    # Create agent executor
    if agent_type == 'subprocess':
        executor = AgentExecutor(
            agent_type=AgentType.SUBPROCESS,
            agent_config={'command': agent},
            timeout_seconds=timeout
        )
    elif agent_type == 'python':
        # Import Python callable
        # Format: module.path:function_name
        console.print("[red]Error: Python callable not yet implemented[/red]")
        return
    elif agent_type == 'http':
        executor = AgentExecutor(
            agent_type=AgentType.HTTP,
            agent_config={'url': agent, 'method': 'POST'},
            timeout_seconds=timeout
        )
    else:
        console.print(f"[red]Error: Unsupported agent type: {agent_type}[/red]")
        return

    # Create runner
    runner = TestRunner(executor)

    # Run tests
    console.print(f"\n[cyan]Running tests from:[/cyan] {tests_path}")
    console.print(f"[cyan]Agent:[/cyan] {agent}")
    console.print()

    results = runner.run_all(tests_path, max_tests=max_tests)

    # Save results
    runner.save_results(results, output_path)

    # Show summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    console.print("\n[bold]Execution Summary[/bold]")
    console.print(f"  Total: {len(results)}")
    console.print(f"  [green]Successful: {successful}[/green]")
    console.print(f"  [red]Failed: {failed}[/red]")

    if failed > 0:
        console.print("\n[yellow]Failed tests:[/yellow]")
        for r in results:
            if not r.success:
                console.print(f"  ✗ {r.test_name}: {r.error}")


@cli.command()
@click.option(
    '--results',
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help='Path to execution results JSON file'
)
@click.option(
    '--output',
    type=click.Path(),
    default='results/evaluation_results.json',
    help='Output file for evaluation results'
)
@click.option(
    '--use-llm/--no-llm',
    default=True,
    help='Use LLM-as-judge for evaluation'
)
@click.option(
    '--llm-provider',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM provider for evaluation'
)
def evaluate(results, output, use_llm, llm_provider):
    """
    Evaluate test execution results.

    Scores agent performance using compliance checks and LLM-as-judge.
    """
    console.print("\n[bold cyan]AgentEval Evaluator[/bold cyan]")
    console.print("=" * 70)

    results_path = Path(results)
    output_path = Path(output)

    # Load execution results
    with open(results_path, 'r') as f:
        data = json.load(f)

    # Convert to TestExecution objects
    from ..runner.runner import TestExecution, TurnExecution

    test_executions = []
    for result in data['results']:
        turns = [
            TurnExecution(
                turn_number=t['turn_number'],
                customer_message=t['customer_message'],
                agent_response=t['agent_response'],
                duration_ms=t['duration_ms'],
                error=t.get('error'),
                metadata=t.get('metadata', {})
            )
            for t in result['turns']
        ]

        test_exec = TestExecution(
            test_id=result['test_id'],
            test_name=result['test_name'],
            turns=turns,
            total_duration_ms=result['total_duration_ms'],
            success=result['success'],
            error=result.get('error'),
            context=result.get('context', {})
        )
        test_executions.append(test_exec)

    # Create evaluator
    evaluator = Evaluator(use_llm=use_llm, llm_provider=llm_provider)

    # Evaluate
    console.print(f"\n[cyan]Evaluating {len(test_executions)} test results...[/cyan]")
    if use_llm:
        console.print(f"[cyan]Using LLM:[/cyan] {llm_provider}")
    console.print()

    eval_results = evaluator.evaluate_batch(test_executions)

    # Save results
    output_data = {
        'metadata': {
            'total_tests': len(eval_results),
            'passed': sum(1 for r in eval_results if r.status.value == 'pass'),
            'failed': sum(1 for r in eval_results if r.status.value == 'fail'),
            'errors': sum(1 for r in eval_results if r.status.value == 'error'),
            'use_llm': use_llm,
            'llm_provider': llm_provider if use_llm else None
        },
        'results': [
            {
                'test_id': r.test_id,
                'test_name': r.test_name,
                'status': r.status.value,
                'overall_score': r.overall_score,
                'dimension_scores': [
                    {
                        'dimension': d.dimension,
                        'score': d.score,
                        'weight': d.weight,
                        'reasoning': d.reasoning
                    }
                    for d in r.dimension_scores
                ],
                'turn_evaluations': [
                    {
                        'turn_number': t.turn_number,
                        'turn_score': t.turn_score,
                        'feedback': t.feedback
                    }
                    for t in r.turn_evaluations
                ],
                'pass_threshold': r.pass_threshold,
                'feedback': r.feedback,
                'improvement_suggestions': r.improvement_suggestions,
                'metadata': r.metadata
            }
            for r in eval_results
        ]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    console.print(f"\n✓ Evaluation results saved → [green]{output_path}[/green]")


@cli.command()
@click.option(
    '--results',
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help='Path to evaluation results JSON file'
)
@click.option(
    '--format',
    type=click.Choice(['summary', 'detailed', 'json']),
    default='summary',
    help='Report format'
)
def report(results, format):
    """
    Display evaluation results in a readable format.
    """
    results_path = Path(results)

    with open(results_path, 'r') as f:
        data = json.load(f)

    if format == 'json':
        console.print_json(data=data)
        return

    # Summary view
    metadata = data['metadata']

    console.print("\n[bold cyan]AgentEval Results[/bold cyan]")
    console.print("=" * 70)

    # Overall stats
    total = metadata['total_tests']
    passed = metadata['passed']
    failed = metadata['failed']
    errors = metadata.get('errors', 0)

    pass_rate = (passed / total * 100) if total > 0 else 0

    stats_panel = Panel(
        f"""[green]Passed:[/green] {passed}/{total} ({pass_rate:.1f}%)
[red]Failed:[/red] {failed}
[yellow]Errors:[/yellow] {errors}
[cyan]LLM Used:[/cyan] {metadata.get('use_llm', False)}""",
        title="Summary",
        border_style="cyan"
    )

    console.print("\n")
    console.print(stats_panel)

    # Results table
    table = Table(title="\nTest Results")
    table.add_column("Test", style="cyan", no_wrap=False)
    table.add_column("Status", justify="center")
    table.add_column("Score", justify="right", style="magenta")
    table.add_column("Threshold", justify="right")

    for result in data['results']:
        status = result['status']
        status_emoji = "✓" if status == "pass" else "✗" if status == "fail" else "!"
        status_color = "green" if status == "pass" else "red" if status == "fail" else "yellow"

        score = result['overall_score']
        threshold = result['pass_threshold']

        table.add_row(
            result['test_name'][:50],
            f"[{status_color}]{status_emoji} {status.upper()}[/{status_color}]",
            f"{score:.2f}",
            f"{threshold:.2f}"
        )

    console.print(table)

    # Detailed view
    if format == 'detailed':
        console.print("\n[bold]Detailed Results[/bold]")
        console.print("=" * 70)

        for result in data['results']:
            console.print(f"\n[bold cyan]{result['test_name']}[/bold cyan]")
            console.print(f"Status: {result['status'].upper()}")
            console.print(f"Score: {result['overall_score']:.2f}")

            if result['dimension_scores']:
                console.print("\nDimensions:")
                for dim in result['dimension_scores']:
                    console.print(f"  • {dim['dimension']}: {dim['score']:.1f}/5.0 - {dim['reasoning']}")

            if result['improvement_suggestions']:
                console.print("\nSuggestions:")
                for suggestion in result['improvement_suggestions']:
                    console.print(f"  - {suggestion}")

            console.print()


@cli.command()
@click.option(
    '--codebase',
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help='Path to codebase directory to analyze'
)
@click.option(
    '--agent',
    required=True,
    help='Agent command (e.g., "python agent.py")'
)
@click.option(
    '--output-dir',
    type=click.Path(),
    default='results',
    help='Output directory for all results'
)
@click.option(
    '--max-tests',
    type=int,
    default=10,
    help='Maximum number of test cases to generate and run'
)
@click.option(
    '--use-llm/--no-llm',
    default=True,
    help='Use LLM for test generation and evaluation'
)
def full(codebase, agent, output_dir, max_tests, use_llm):
    """
    Run the complete pipeline: generate → run → evaluate → report.

    This is the easiest way to test your agent end-to-end.
    """
    console.print("\n[bold cyan]AgentEval Full Pipeline[/bold cyan]")
    console.print("=" * 70)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tests_file = output_path / 'generated_tests.yaml'
    exec_file = output_path / 'execution_results.json'
    eval_file = output_path / 'evaluation_results.json'

    # Step 1: Generate
    console.print("\n[bold]Step 1: Generating test cases[/bold]")
    console.print("-" * 70)
    ctx = click.Context(generate)
    ctx.invoke(
        generate,
        codebase=codebase,
        output=str(tests_file),
        max_tests=max_tests,
        use_llm=use_llm
    )

    # Step 2: Run
    console.print("\n[bold]Step 2: Running tests[/bold]")
    console.print("-" * 70)
    ctx = click.Context(run)
    ctx.invoke(
        run,
        tests=str(tests_file),
        agent=agent,
        agent_type='subprocess',
        output=str(exec_file),
        max_tests=None,
        timeout=30
    )

    # Step 3: Evaluate
    console.print("\n[bold]Step 3: Evaluating results[/bold]")
    console.print("-" * 70)
    ctx = click.Context(evaluate)
    ctx.invoke(
        evaluate,
        results=str(exec_file),
        output=str(eval_file),
        use_llm=use_llm,
        llm_provider='openai'
    )

    # Step 4: Report
    console.print("\n[bold]Step 4: Final Report[/bold]")
    console.print("-" * 70)
    ctx = click.Context(report)
    ctx.invoke(
        report,
        results=str(eval_file),
        format='summary'
    )

    console.print(f"\n✓ All results saved to: [green]{output_path}[/green]")


if __name__ == '__main__':
    cli()
