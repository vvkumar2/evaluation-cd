"""Generate HTML reports for test execution results."""

import json
from datetime import datetime
from pathlib import Path
from .schemas import TestRunReport


def generate_html_report(report: TestRunReport, output_path: Path) -> None:
    """Generate an HTML report from test results."""
    all_results = report.results.results
    failed_tests = [r for r in all_results if not r.passed]
    passed_tests = [r for r in all_results if r.passed]

    html_content = _generate_html(report, failed_tests, passed_tests)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html_content)


def _generate_html(report: TestRunReport, failed_tests, passed_tests) -> str:
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")
    pass_pct = report.pass_rate * 100
    # Color the progress bar based on pass rate
    if pass_pct >= 80:
        bar_color = "#16a34a"
    elif pass_pct >= 60:
        bar_color = "#ca8a04"
    else:
        bar_color = "#dc2626"

    avg_score = 0
    if report.total_tests > 0:
        avg_score = sum(r.score for r in report.results.results) / report.total_tests

    duration = report.duration_seconds
    if duration >= 60:
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
    else:
        duration_str = f"{duration:.1f}s"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report — {_escape_html(report.agent_name)}</title>
    <style>
        :root {{
            --bg: #f8f9fb;
            --surface: #ffffff;
            --border: #e2e5e9;
            --text: #1a1d23;
            --text-secondary: #5f6672;
            --text-tertiary: #8b919d;
            --green: #16a34a;
            --green-bg: #f0fdf4;
            --green-border: #bbf7d0;
            --red: #dc2626;
            --red-bg: #fef2f2;
            --red-border: #fecaca;
            --blue: #2563eb;
            --blue-bg: #eff6ff;
            --radius: 6px;
            --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        .page {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px; }}

        /* Header */
        .report-header {{
            margin-bottom: 32px;
        }}
        .report-header h1 {{
            font-size: 22px;
            font-weight: 600;
            letter-spacing: -0.02em;
        }}
        .report-header .meta {{
            color: var(--text-tertiary);
            font-size: 13px;
            margin-top: 4px;
        }}

        /* Stats row */
        .stats {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
        }}
        .stat-card .stat-value {{
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.03em;
            line-height: 1.1;
        }}
        .stat-card .stat-label {{
            font-size: 12px;
            font-weight: 500;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 6px;
        }}
        .stat-card.green .stat-value {{ color: var(--green); }}
        .stat-card.red .stat-value {{ color: var(--red); }}

        /* Progress bar */
        .progress-section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 32px;
        }}
        .progress-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }}
        .progress-header .label {{
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }}
        .progress-header .value {{
            font-size: 13px;
            font-weight: 600;
        }}
        .progress-bar {{
            height: 8px;
            background: var(--bg);
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.4s ease;
        }}

        /* Test sections */
        .section {{
            margin-bottom: 28px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
        }}
        .section-header h2 {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-secondary);
        }}
        .section-count {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
            background: var(--bg);
            color: var(--text-tertiary);
        }}

        /* Test items */
        .test-list {{
            display: flex;
            flex-direction: column;
            gap: 2px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }}
        .test-row {{
            border-bottom: 1px solid var(--border);
        }}
        .test-row:last-child {{
            border-bottom: none;
        }}
        .test-row-header {{
            display: flex;
            align-items: center;
            padding: 12px 16px;
            cursor: pointer;
            gap: 12px;
            user-select: none;
            transition: background 0.15s;
        }}
        .test-row-header:hover {{
            background: var(--bg);
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .status-dot.pass {{ background: var(--green); }}
        .status-dot.fail {{ background: var(--red); }}
        .test-name {{
            flex: 1;
            min-width: 0;
            font-size: 13px;
            font-weight: 500;
            font-family: var(--mono);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .test-intent-tag {{
            font-size: 11px;
            color: var(--text-tertiary);
            background: var(--bg);
            padding: 2px 8px;
            border-radius: 3px;
            white-space: nowrap;
        }}
        .score-pill {{
            font-size: 12px;
            font-weight: 600;
            font-family: var(--mono);
            min-width: 42px;
            text-align: center;
            padding: 3px 8px;
            border-radius: 3px;
        }}
        .score-pill.pass {{
            background: var(--green-bg);
            color: var(--green);
        }}
        .score-pill.fail {{
            background: var(--red-bg);
            color: var(--red);
        }}
        .chevron {{
            color: var(--text-tertiary);
            font-size: 14px;
            transition: transform 0.2s;
            flex-shrink: 0;
            width: 16px;
            text-align: center;
        }}
        .chevron.open {{
            transform: rotate(90deg);
        }}

        /* Expanded detail panel */
        .test-detail {{
            display: none;
            padding: 0 16px 16px 38px;
        }}
        .test-detail.open {{
            display: block;
        }}
        .detail-grid {{
            display: grid;
            gap: 12px;
        }}
        .detail-block {{
        }}
        .detail-block-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-tertiary);
            margin-bottom: 4px;
        }}
        .detail-block-content {{
            font-size: 13px;
            line-height: 1.6;
            color: var(--text-secondary);
            background: var(--bg);
            padding: 10px 12px;
            border-radius: 4px;
            border: 1px solid var(--border);
        }}
        pre.detail-block-content {{
            font-family: var(--mono);
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 280px;
            overflow-y: auto;
        }}

        /* Collapsible detail sections */
        .detail-disclosure {{
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
        }}
        .detail-disclosure summary {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-tertiary);
            padding: 8px 12px;
            cursor: pointer;
            user-select: none;
            list-style: none;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .detail-disclosure summary::-webkit-details-marker {{
            display: none;
        }}
        .detail-disclosure summary::before {{
            content: "\\203A";
            font-size: 14px;
            transition: transform 0.15s ease;
            display: inline-block;
            width: 12px;
            text-align: center;
            transform-origin: center center;
        }}
        .detail-disclosure[open] summary::before {{
            transform: rotate(90deg);
        }}
        .detail-disclosure summary:hover {{
            background: var(--bg);
        }}
        .detail-disclosure .disclosure-body {{
            border-top: 1px solid var(--border);
        }}
        .disclosure-grid {{
            display: grid;
            gap: 12px;
            padding: 12px;
        }}
        .disclosure-grid .detail-block-content {{
            border: 1px solid var(--border);
            border-radius: 4px;
        }}

        /* Tool calls comparison */
        .tool-calls-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}
        .tool-tag {{
            display: inline-block;
            font-size: 11px;
            font-family: var(--mono);
            padding: 2px 7px;
            border-radius: 3px;
            margin: 2px 2px;
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text-secondary);
        }}
        .tool-tag.match {{
            background: var(--green-bg);
            border-color: var(--green-border);
            color: var(--green);
        }}
        .tool-tag.missing {{
            background: var(--red-bg);
            border-color: var(--red-border);
            color: var(--red);
        }}
        .tool-tag.extra {{
            background: var(--blue-bg);
            border-color: #bfdbfe;
            color: var(--blue);
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-tertiary);
            font-size: 14px;
        }}

        @media (max-width: 640px) {{
            .stats {{ grid-template-columns: repeat(2, 1fr); }}
            .tool-calls-row {{ grid-template-columns: 1fr; }}
            .test-intent-tag {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <div class="report-header">
            <h1>{_escape_html(report.agent_name)}</h1>
            <div class="meta">Evaluation report &middot; {timestamp} &middot; {report.total_tests} tests &middot; {duration_str}</div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{report.total_tests}</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat-card green">
                <div class="stat-value">{report.passed_tests}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card red">
                <div class="stat-value">{report.failed_tests}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_score:.1f}</div>
                <div class="stat-label">Avg Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{duration_str}</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>

        <div class="progress-section">
            <div class="progress-header">
                <span class="label">Pass Rate</span>
                <span class="value" style="color: {bar_color}">{pass_pct:.1f}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_pct:.1f}%; background: {bar_color}"></div>
            </div>
        </div>

        {_render_tests_section("Failed", failed_tests, "fail") if failed_tests else ""}
        {_render_tests_section("Passed", passed_tests, "pass") if passed_tests else ""}
        {_render_empty_state(report.total_tests)}
    </div>

    <script>
        document.querySelectorAll('.test-row-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const detail = header.nextElementSibling;
                const chevron = header.querySelector('.chevron');
                detail.classList.toggle('open');
                chevron.classList.toggle('open');
            }});
        }});
    </script>
</body>
</html>"""


def _render_tests_section(title: str, tests, status_class: str) -> str:
    if not tests:
        return ""

    tests_html = "\n".join(_render_test(t, status_class) for t in tests)
    return f"""
        <div class="section">
            <div class="section-header">
                <h2>{title}</h2>
                <span class="section-count">{len(tests)}</span>
            </div>
            <div class="test-list">
                {tests_html}
            </div>
        </div>"""


def _render_test(test, status_class: str) -> str:
    score_class = status_class
    expected = set(test.expected_tool_calls) if test.expected_tool_calls else set()
    actual = set(test.actual_tool_calls) if test.actual_tool_calls else set()

    expected_tags = _render_tool_tags(
        test.expected_tool_calls or [], actual, mode="expected"
    )
    actual_tags = _render_tool_tags(
        test.actual_tool_calls or [], expected, mode="actual"
    )

    return f"""
                <div class="test-row">
                    <div class="test-row-header">
                        <div class="status-dot {status_class}"></div>
                        <div class="test-name">{_escape_html(test.test_id)}</div>
                        <span class="test-intent-tag">{_escape_html(test.intent_name)}</span>
                        <span class="score-pill {score_class}">{test.score}/10</span>
                        <span class="chevron">&#x203A;</span>
                    </div>
                    <div class="test-detail">
                        <div class="detail-grid">
                            <div class="detail-block">
                                <div class="detail-block-label">Reasoning</div>
                                <div class="detail-block-content">{_escape_html(test.reasoning)}</div>
                            </div>
                            <details class="detail-disclosure">
                                <summary>Agent Input</summary>
                                <div class="disclosure-body disclosure-grid">
                                    <div class="detail-block">
                                        <div class="detail-block-label">Message</div>
                                        <div class="detail-block-content">{_escape_html(test.input_message)}</div>
                                    </div>
                                    <div class="detail-block">
                                        <div class="detail-block-label">Context</div>
                                        <pre class="detail-block-content">{_escape_html(json.dumps(test.input_context, indent=2))}</pre>
                                    </div>
                                    <div class="detail-block">
                                        <div class="detail-block-label">Backend State</div>
                                        <pre class="detail-block-content">{_escape_html(json.dumps(test.backend_state, indent=2))}</pre>
                                    </div>
                                </div>
                            </details>
                            <details class="detail-disclosure">
                                <summary>Agent Output</summary>
                                <div class="disclosure-body disclosure-grid">
                                    <div class="tool-calls-row">
                                        <div class="detail-block">
                                            <div class="detail-block-label">Expected Tools</div>
                                            <div class="detail-block-content">{expected_tags if expected_tags else '<span style="color: var(--text-tertiary)">none</span>'}</div>
                                        </div>
                                        <div class="detail-block">
                                            <div class="detail-block-label">Actual Tools</div>
                                            <div class="detail-block-content">{actual_tags if actual_tags else '<span style="color: var(--text-tertiary)">none</span>'}</div>
                                        </div>
                                    </div>
                                    <div class="detail-block">
                                        <div class="detail-block-label">Response</div>
                                        <pre class="detail-block-content">{_escape_html(test.output)}</pre>
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>"""


def _render_tool_tags(tools: list[str], comparison_set: set, mode: str) -> str:
    """Render tool name tags with color coding.

    For expected tools: green if in actual (match), red if not (missing).
    For actual tools: green if in expected (match), blue if not (extra).
    """
    tags = []
    for tool in tools:
        if tool in comparison_set:
            cls = "match"
        elif mode == "expected":
            cls = "missing"
        else:
            cls = "extra"
        tags.append(f'<span class="tool-tag {cls}">{_escape_html(tool)}</span>')
    return "".join(tags)


def _render_empty_state(total: int) -> str:
    if total == 0:
        return '<div class="empty-state">No tests to display</div>'
    return ""


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
