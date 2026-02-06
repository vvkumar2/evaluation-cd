"""Generate HTML reports for test execution results."""

from pathlib import Path
from .schemas import TestRunReport


def generate_html_report(report: TestRunReport, output_path: Path) -> None:
    """Generate an HTML report from test results.

    Args:
        report: TestRunReport object with results
        output_path: Path to save HTML file
    """
    # Sort tests: failed first, then passed
    all_results = report.results.results
    failed_tests = [r for r in all_results if not r.passed]
    passed_tests = [r for r in all_results if r.passed]

    html_content = _generate_html(report, failed_tests, passed_tests)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html_content)


def _generate_html(report: TestRunReport, failed_tests, passed_tests) -> str:
    """Generate HTML content for the report."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {report.agent_name.title()}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .header {{
            background: #667eea;
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 16px;
            opacity: 0.9;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }}

        .summary-card {{
            text-align: center;
        }}

        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}

        .summary-card .label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}

        .summary-card.pass-rate .value {{
            color: #10b981;
        }}

        .content {{
            padding: 30px;
        }}

        .section {{
            margin-bottom: 30px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
            color: #333;
        }}

        .test-item {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
            margin-bottom: 15px;
            overflow: hidden;
        }}

        .test-item.failed {{
            border-left-color: #ef4444;
            background: #fef2f2;
        }}

        .test-item.passed {{
            border-left-color: #10b981;
            background: #f0fdf4;
        }}

        .test-header {{
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }}

        .test-header:hover {{
            background: rgba(102, 126, 234, 0.05);
        }}

        .test-header-left {{
            display: flex;
            align-items: center;
            gap: 15px;
            flex: 1;
        }}

        .test-status {{
            font-size: 24px;
            min-width: 30px;
        }}

        .test-info {{
            flex: 1;
        }}

        .test-id {{
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }}

        .test-intent {{
            font-size: 12px;
            color: #666;
            margin-top: 3px;
        }}

        .test-score {{
            text-align: right;
            min-width: 80px;
        }}

        .score-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
        }}

        .score-badge.pass {{
            background: #d1fae5;
            color: #047857;
        }}

        .score-badge.fail {{
            background: #fee2e2;
            color: #dc2626;
        }}

        .test-toggle {{
            color: #999;
            font-size: 18px;
            transition: transform 0.2s;
        }}

        .test-toggle.open {{
            transform: rotate(90deg);
        }}

        .test-details {{
            display: none;
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
        }}

        .test-details.open {{
            display: block;
        }}

        .detail-section {{
            margin-bottom: 15px;
        }}

        .detail-label {{
            font-size: 12px;
            font-weight: 600;
            color: #667eea;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}

        .detail-content {{
            font-family: "Courier New", monospace;
            font-size: 13px;
            background: #f5f5f5;
            padding: 12px;
            border-radius: 4px;
            max-height: 300px;
            overflow-y: auto;
            color: #333;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }}

        .empty-state p {{
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{report.agent_name.title()}</h1>
            <p>Test Execution Report</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="value">{report.total_tests}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card">
                <div class="value">{report.passed_tests}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card">
                <div class="value">{report.failed_tests}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card pass-rate">
                <div class="value">{report.pass_rate*100:.1f}%</div>
                <div class="label">Pass Rate</div>
            </div>
        </div>

        <div class="content">
            {_render_tests_section("Failed Tests", failed_tests, "failed") if failed_tests else ""}
            {_render_tests_section("Passed Tests", passed_tests, "passed") if passed_tests else ""}
            {_render_empty_state(report.total_tests)}
        </div>
    </div>

    <script>
        document.querySelectorAll('.test-header').forEach(header => {{
            header.addEventListener('click', function() {{
                const details = this.nextElementSibling;
                const toggle = this.querySelector('.test-toggle');

                details.classList.toggle('open');
                toggle.classList.toggle('open');
            }});
        }});
    </script>
</body>
</html>"""


def _render_tests_section(title: str, tests, test_class: str) -> str:
    """Render a section of tests."""
    if not tests:
        return ""

    tests_html = "\n".join(_render_test(test, test_class) for test in tests)
    return f"""
        <div class="section">
            <div class="section-title">{title}</div>
            {tests_html}
        </div>"""


def _render_test(test, test_class: str) -> str:
    """Render a single test item."""
    status_icon = "❌" if test_class == "failed" else "✅"
    score_badge_class = "fail" if test_class == "failed" else "pass"

    return f"""
            <div class="test-item {test_class}">
                <div class="test-header">
                    <div class="test-header-left">
                        <div class="test-status">{status_icon}</div>
                        <div class="test-info">
                            <div class="test-id">{test.test_id}</div>
                            <div class="test-intent">{test.intent_name}</div>
                        </div>
                    </div>
                    <div class="test-score">
                        <span class="score-badge {score_badge_class}">{test.score}/10</span>
                    </div>
                    <div class="test-toggle">›</div>
                </div>
                <div class="test-details">
                    <div class="detail-section">
                        <div class="detail-label">Reasoning</div>
                        <div class="detail-content">{_escape_html(test.reasoning)}</div>
                    </div>
                    <div class="detail-section">
                        <div class="detail-label">Agent Output</div>
                        <div class="detail-content">{_escape_html(test.output)}</div>
                    </div>
                </div>
            </div>"""


def _render_empty_state(total: int) -> str:
    """Render empty state if no tests."""
    if total == 0:
        return """
        <div class="section">
            <div class="empty-state">
                <p>No tests to display</p>
            </div>
        </div>"""
    return ""


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
