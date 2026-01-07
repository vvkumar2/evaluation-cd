"""Report command implementation."""

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agenteval.models import RunResult, TestStatus

console = Console()


def report_command(
    results_path: Path,
    format: str,
    output: Optional[Path],
) -> None:
    """View or export evaluation results."""
    # Load results
    with open(results_path) as f:
        data = json.load(f)

    if format == "terminal":
        _print_terminal_report(data)
    elif format == "html":
        if output is None:
            output = results_path.with_suffix(".html")
        _generate_html_report(data, output)
        console.print(f"[green]✓[/green] HTML report saved to [bold]{output}[/bold]")
    elif format == "json":
        if output is None:
            output = results_path
        with open(output, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"[green]✓[/green] JSON report saved to [bold]{output}[/bold]")
    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        console.print("Supported formats: terminal, html, json")


def _print_terminal_report(data: dict) -> None:
    """Print a detailed terminal report."""
    summary = data.get("summary", {})
    results = data.get("results", [])

    # Header
    console.print()
    console.print(Panel(
        f"[bold]{data.get('suite_name', 'Evaluation Results')}[/bold]\n"
        f"Started: {data.get('started_at', 'N/A')}\n"
        f"Duration: {data.get('duration_ms', 0)}ms",
        title="AgentEval Report",
        border_style="blue",
    ))

    # Summary table
    console.print()
    summary_table = Table(title="Summary", show_header=True, header_style="bold")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total Tests", str(summary.get("total", 0)))
    summary_table.add_row("Passed", f"[green]{summary.get('passed', 0)}[/green]")
    summary_table.add_row("Failed", f"[red]{summary.get('failed', 0)}[/red]")
    summary_table.add_row("Errors", f"[yellow]{summary.get('errors', 0)}[/yellow]")
    summary_table.add_row("Pass Rate", f"{summary.get('pass_rate', 0):.1f}%")
    summary_table.add_row("Average Score", f"{summary.get('average_score', 0):.3f}")

    console.print(summary_table)

    # Individual results
    console.print()
    results_table = Table(title="Test Results", show_header=True, header_style="bold")
    results_table.add_column("Test ID", style="cyan", no_wrap=True)
    results_table.add_column("Status", justify="center")
    results_table.add_column("Score", justify="right")
    results_table.add_column("Duration", justify="right")

    for result in results:
        status = result.get("status", "unknown")
        if status == "passed":
            status_text = "[green]✓ PASS[/green]"
        elif status == "failed":
            status_text = "[red]✗ FAIL[/red]"
        elif status == "error":
            status_text = "[yellow]⚠ ERROR[/yellow]"
        else:
            status_text = status

        scores = result.get("scores", {})
        score = scores.get("weighted_score", 0) if scores else 0

        results_table.add_row(
            result.get("test_id", "N/A"),
            status_text,
            f"{score:.3f}" if scores else "N/A",
            f"{result.get('duration_ms', 0)}ms",
        )

    console.print(results_table)

    # Failed tests details
    failed = [r for r in results if r.get("status") in ("failed", "error")]
    if failed:
        console.print()
        console.print("[bold red]Failed Tests Details:[/bold red]")
        for result in failed[:5]:  # Show first 5 failures
            console.print()
            console.print(f"[bold]Test: {result.get('test_id')}[/bold]")

            if result.get("error_message"):
                console.print(f"  Error: [red]{result.get('error_message')}[/red]")
            else:
                response = result.get("agent_response", "")
                if response:
                    truncated = response[:200] + "..." if len(response) > 200 else response
                    console.print(f"  Response: [dim]{truncated}[/dim]")

                evaluations = result.get("evaluations", [])
                for eval_result in evaluations:
                    score = eval_result.get("score", 0)
                    criterion = eval_result.get("criterion", "unknown")
                    feedback = eval_result.get("feedback", "")
                    color = "green" if score >= 0.7 else "red"
                    console.print(f"  • {criterion}: [{color}]{score:.2f}[/{color}] {feedback}")

        if len(failed) > 5:
            console.print(f"\n  [dim]... and {len(failed) - 5} more failures[/dim]")

    # Final verdict
    console.print()
    pass_rate = summary.get("pass_rate", 0)
    if pass_rate >= 80:
        console.print(Panel(
            "[bold green]✓ EVALUATION PASSED[/bold green]\n"
            f"Pass rate: {pass_rate:.1f}% (threshold: 80%)",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold red]✗ EVALUATION FAILED[/bold red]\n"
            f"Pass rate: {pass_rate:.1f}% (threshold: 80%)",
            border_style="red",
        ))


def _generate_html_report(data: dict, output: Path) -> None:
    """Generate an HTML report."""
    from jinja2 import Template

    template = Template(HTML_TEMPLATE)
    html = template.render(
        title=data.get("suite_name", "Evaluation Results"),
        summary=data.get("summary", {}),
        results=data.get("results", []),
        started_at=data.get("started_at", "N/A"),
        duration_ms=data.get("duration_ms", 0),
    )

    with open(output, "w") as f:
        f.write(html)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - AgentEval Report</title>
    <style>
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --yellow: #d29922;
            --blue: #58a6ff;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }
        
        .container { max-width: 1200px; margin: 0 auto; }
        
        h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: var(--blue);
        }
        
        .meta {
            color: var(--text-muted);
            margin-bottom: 2rem;
        }
        
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .stat {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
        }
        
        .stat-label {
            color: var(--text-muted);
            font-size: 0.875rem;
        }
        
        .passed { color: var(--green); }
        .failed { color: var(--red); }
        .error { color: var(--yellow); }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th, td {
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            background: rgba(0,0,0,0.2);
            font-weight: 600;
        }
        
        tr:hover { background: rgba(255,255,255,0.02); }
        
        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .status-passed { background: rgba(63, 185, 80, 0.2); color: var(--green); }
        .status-failed { background: rgba(248, 81, 73, 0.2); color: var(--red); }
        .status-error { background: rgba(210, 153, 34, 0.2); color: var(--yellow); }
        
        .verdict {
            margin-top: 2rem;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            font-size: 1.25rem;
            font-weight: bold;
        }
        
        .verdict-passed {
            background: rgba(63, 185, 80, 0.1);
            border: 2px solid var(--green);
            color: var(--green);
        }
        
        .verdict-failed {
            background: rgba(248, 81, 73, 0.1);
            border: 2px solid var(--red);
            color: var(--red);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ title }}</h1>
        <p class="meta">Generated at {{ started_at }} | Duration: {{ duration_ms }}ms</p>
        
        <div class="summary">
            <div class="stat">
                <div class="stat-value">{{ summary.total }}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value passed">{{ summary.passed }}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value failed">{{ summary.failed }}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value error">{{ summary.errors }}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat">
                <div class="stat-value">{{ "%.1f"|format(summary.pass_rate) }}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
            <div class="stat">
                <div class="stat-value">{{ "%.3f"|format(summary.average_score) }}</div>
                <div class="stat-label">Avg Score</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Test ID</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>
                {% for result in results %}
                <tr>
                    <td>{{ result.test_id }}</td>
                    <td>
                        {% if result.status == 'passed' %}
                        <span class="status-badge status-passed">✓ PASS</span>
                        {% elif result.status == 'failed' %}
                        <span class="status-badge status-failed">✗ FAIL</span>
                        {% else %}
                        <span class="status-badge status-error">⚠ ERROR</span>
                        {% endif %}
                    </td>
                    <td>{{ "%.3f"|format(result.scores.weighted_score) if result.scores else "N/A" }}</td>
                    <td>{{ result.duration_ms }}ms</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="verdict {% if summary.pass_rate >= 80 %}verdict-passed{% else %}verdict-failed{% endif %}">
            {% if summary.pass_rate >= 80 %}
            ✓ EVALUATION PASSED
            {% else %}
            ✗ EVALUATION FAILED
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

