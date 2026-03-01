"""Generate HTML reports for test execution results."""

import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
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
    timestamp = datetime.now().strftime("%b %d, %Y at %H:%M")
    pass_pct = report.pass_rate * 100

    if pass_pct >= 80:
        gauge_color = "#34d399"
    elif pass_pct >= 60:
        gauge_color = "#f0b429"
    else:
        gauge_color = "#f87171"

    avg_score = 0
    if report.total_tests > 0:
        avg_score = sum(r.score for r in report.results.results) / report.total_tests

    duration = report.duration_seconds
    if duration >= 60:
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
    else:
        duration_str = f"{duration:.1f}s"

    # SVG gauge
    radius = 54
    circumference = 2 * 3.14159265 * radius  # ~339.29
    gauge_offset = circumference * (1 - report.pass_rate)

    # Score distribution
    score_dist = [0] * 10
    for r in report.results.results:
        idx = max(0, min(9, r.score - 1))
        score_dist[idx] += 1
    max_count = max(score_dist) if any(score_dist) else 1
    dist_bars_html = _render_score_distribution(score_dist, max_count)

    # Intent-grouped tests
    intent_groups_html = _render_intent_groups(report.results.results)

    # Empty state
    empty_html = _render_empty_state(report.total_tests)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eval Report \u2014 {_escape_html(report.agent_name)}</title>
    <style>
        :root {{
            --bg: #0c0d10;
            --surface: #141519;
            --surface-2: #1c1d24;
            --border: #26272f;
            --border-light: #32333d;
            --text: #e2e3e8;
            --text-secondary: #9a9ba3;
            --text-dim: #4e5059;
            --amber: #f0b429;
            --amber-dim: rgba(240,180,41,0.1);
            --green: #34d399;
            --green-dim: rgba(52,211,153,0.08);
            --red: #f87171;
            --red-dim: rgba(248,113,113,0.08);
            --blue: #60a5fa;
            --mono: "SF Mono","Cascadia Code","Fira Code","JetBrains Mono","Consolas",monospace;
            --sans: "Avenir Next","Avenir","Segoe UI",system-ui,sans-serif;
        }}

        * {{ margin:0; padding:0; box-sizing:border-box; }}

        body {{
            font-family: var(--sans);
            background: var(--bg);
            color: var(--text);
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        body::before {{
            content: '';
            position: fixed;
            inset: 0;
            background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(240,180,41,0.025) 0%, transparent 100%);
            pointer-events: none;
            z-index: 0;
        }}

        ::-webkit-scrollbar {{ width:5px; height:5px; }}
        ::-webkit-scrollbar-track {{ background:transparent; }}
        ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:3px; }}
        ::-webkit-scrollbar-thumb:hover {{ background:var(--text-dim); }}

        .page {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 48px 28px 64px;
            position: relative;
            z-index: 1;
        }}

        /* ── Header ───────────────────────────────── */
        .header {{
            margin-bottom: 36px;
        }}
        .header-label {{
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--amber);
            margin-bottom: 10px;
        }}
        .header-title {{
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.03em;
            color: var(--text);
            line-height: 1.2;
        }}
        .header-meta {{
            font-family: var(--mono);
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 8px;
        }}

        /* ── Dashboard ────────────────────────────── */
        .dashboard {{
            display: flex;
            gap: 0;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 36px;
            overflow: hidden;
        }}
        .dashboard-gauge {{
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 28px 32px;
            border-right: 1px solid var(--border);
        }}
        .gauge-svg {{ display: block; }}
        .gauge-track {{
            fill: none;
            stroke: var(--border);
            stroke-width: 5;
        }}
        .gauge-fill {{
            fill: none;
            stroke: {gauge_color};
            stroke-width: 5;
            stroke-linecap: round;
            stroke-dasharray: {circumference:.2f};
            stroke-dashoffset: {circumference:.2f};
            transition: stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1);
            filter: drop-shadow(0 0 8px {gauge_color}30);
        }}
        .gauge-pct {{
            font-family: var(--mono);
            font-size: 26px;
            font-weight: 700;
            fill: var(--text);
            text-anchor: middle;
            dominant-baseline: central;
        }}
        .gauge-sublabel {{
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 600;
            fill: var(--text-dim);
            text-anchor: middle;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .dashboard-right {{
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }}
        .dashboard-stats {{
            display: flex;
            border-bottom: 1px solid var(--border);
        }}
        .stat {{
            flex: 1;
            padding: 20px 22px;
            border-right: 1px solid var(--border);
        }}
        .stat:last-child {{ border-right: none; }}
        .stat-value {{
            font-family: var(--mono);
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.02em;
            line-height: 1.1;
        }}
        .stat-label {{
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-top: 5px;
        }}
        .stat-value.s-green {{ color: var(--green); }}
        .stat-value.s-red {{ color: var(--red); }}

        .dashboard-dist {{
            flex: 1;
            padding: 16px 22px 18px;
        }}
        .dist-title {{
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 10px;
        }}
        .dist-chart {{
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 48px;
        }}
        .dist-col {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
        }}
        .dist-bar-wrap {{
            flex: 1;
            width: 100%;
            display: flex;
            align-items: flex-end;
            justify-content: center;
        }}
        .dist-bar {{
            width: 100%;
            max-width: 18px;
            border-radius: 2px 2px 0 0;
            min-height: 2px;
            opacity: 0.85;
            transition: opacity 0.2s;
        }}
        .dist-col:hover .dist-bar {{ opacity: 1; }}
        .dist-num {{
            font-family: var(--mono);
            font-size: 8px;
            color: var(--text-dim);
            margin-top: 4px;
            line-height: 1;
        }}

        /* ── Intent Groups ────────────────────────── */
        .intent-group {{
            margin-bottom: 24px;
        }}
        .intent-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
            padding: 0 2px;
        }}
        .intent-name {{
            font-family: var(--mono);
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
        }}
        .intent-meta {{
            font-family: var(--mono);
            font-size: 11px;
            color: var(--text-dim);
        }}
        .intent-pass-count {{ color: var(--green); }}
        .intent-fail-indicator {{ color: var(--red); }}

        /* ── Test List ────────────────────────────── */
        .test-list {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }}
        .test-row {{
            border-bottom: 1px solid var(--border);
        }}
        .test-row:last-child {{ border-bottom: none; }}

        .test-row-header {{
            display: flex;
            align-items: stretch;
            cursor: pointer;
            user-select: none;
            transition: background 0.15s;
        }}
        .test-row-header:hover {{
            background: var(--surface-2);
        }}

        .test-status-bar {{
            width: 3px;
            flex-shrink: 0;
        }}
        .test-status-bar.pass {{ background: var(--green); }}
        .test-status-bar.fail {{ background: var(--red); }}

        .test-row-content {{
            flex: 1;
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 11px 16px;
            min-width: 0;
        }}
        .test-name {{
            flex: 1;
            min-width: 0;
            font-family: var(--mono);
            font-size: 12.5px;
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text);
        }}
        .score-bar-track {{
            width: 56px;
            height: 3px;
            background: var(--border);
            border-radius: 2px;
            overflow: hidden;
            flex-shrink: 0;
        }}
        .score-bar-fill {{
            height: 100%;
            border-radius: 2px;
            transition: width 0.5s ease 0.2s;
        }}
        .test-score {{
            font-family: var(--mono);
            font-size: 11px;
            font-weight: 600;
            min-width: 30px;
            text-align: right;
            flex-shrink: 0;
        }}
        .test-score.pass {{ color: var(--green); }}
        .test-score.fail {{ color: var(--red); }}
        .chevron {{
            color: var(--text-dim);
            font-size: 13px;
            transition: transform 0.25s cubic-bezier(0.16,1,0.3,1);
            flex-shrink: 0;
            width: 14px;
            text-align: center;
        }}
        .chevron.open {{
            transform: rotate(90deg);
        }}

        /* ── Test Detail (expanded) ───────────────── */
        .test-detail {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s cubic-bezier(0.16,1,0.3,1);
        }}
        .test-detail-inner {{
            padding: 0 18px 20px 19px;
            border-top: 1px solid var(--border);
        }}

        .eval-section {{
            margin-top: 16px;
        }}
        .detail-label {{
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 6px;
        }}
        .eval-text {{
            font-size: 13px;
            line-height: 1.7;
            color: var(--text-secondary);
            background: var(--surface-2);
            padding: 12px 14px;
            border-radius: 4px;
            border: 1px solid var(--border);
        }}

        .detail-columns {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }}

        .code-block {{
            font-family: var(--mono);
            font-size: 11.5px;
            line-height: 1.65;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 12px 14px;
            overflow-x: auto;
            max-height: 320px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
            color: var(--text-secondary);
        }}

        .msg-block {{
            font-size: 13px;
            line-height: 1.65;
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 12px 14px;
            color: var(--text-secondary);
        }}

        /* ── JSON Highlighting ────────────────────── */
        .json-key {{ color: #7dd3fc; }}
        .json-str {{ color: #86efac; }}
        .json-num {{ color: #fbbf24; }}
        .json-bool {{ color: #c084fc; }}
        .json-null {{ color: #6b7280; }}
        .json-bracket {{ color: var(--text-dim); }}

        /* ── Disclosure (collapsible) ─────────────── */
        .detail-disclosure {{
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 14px;
        }}
        .detail-disclosure summary {{
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            padding: 10px 14px;
            cursor: pointer;
            user-select: none;
            list-style: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background 0.15s, color 0.15s;
        }}
        .detail-disclosure summary::-webkit-details-marker {{ display:none; }}
        .detail-disclosure summary::before {{
            content: "\\203A";
            font-size: 13px;
            display: inline-block;
            width: 10px;
            text-align: center;
            transition: transform 0.2s ease;
        }}
        .detail-disclosure[open] summary::before {{
            transform: rotate(90deg);
        }}
        .detail-disclosure summary:hover {{
            background: var(--surface-2);
            color: var(--text-secondary);
        }}
        .disclosure-body {{
            border-top: 1px solid var(--border);
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .tool-calls-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }}

        /* ── Tool Tags ────────────────────────────── */
        .tools-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            min-height: 26px;
            align-items: center;
        }}
        .tool-tag {{
            display: inline-block;
            font-family: var(--mono);
            font-size: 10.5px;
            padding: 3px 9px;
            border-radius: 3px;
            border: 1px solid var(--border);
            background: var(--surface-2);
            color: var(--text-secondary);
        }}
        .tool-tag.match {{
            background: var(--green-dim);
            border-color: rgba(52,211,153,0.2);
            color: var(--green);
        }}
        .tool-tag.missing {{
            background: var(--red-dim);
            border-color: rgba(248,113,113,0.2);
            color: var(--red);
        }}
        .tool-tag.extra {{
            background: rgba(96,165,250,0.08);
            border-color: rgba(96,165,250,0.2);
            color: var(--blue);
        }}
        .no-tools {{
            font-family: var(--mono);
            font-size: 11px;
            color: var(--text-dim);
            font-style: italic;
        }}

        /* ── Empty State ──────────────────────────── */
        .empty-state {{
            text-align: center;
            padding: 80px 20px;
            color: var(--text-dim);
            font-family: var(--mono);
            font-size: 13px;
        }}

        /* ── Footer ───────────────────────────────── */
        .footer {{
            margin-top: 48px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            font-family: var(--mono);
            font-size: 10px;
            color: var(--text-dim);
            letter-spacing: 0.04em;
        }}

        /* ── Animations ───────────────────────────── */
        @keyframes fadeUp {{
            from {{ opacity:0; transform:translateY(10px); }}
            to {{ opacity:1; transform:translateY(0); }}
        }}
        .anim {{
            opacity: 0;
            animation: fadeUp 0.45s ease forwards;
        }}

        /* ── Responsive ───────────────────────────── */
        @media (max-width: 768px) {{
            .dashboard {{
                flex-direction: column;
            }}
            .dashboard-gauge {{
                border-right: none;
                border-bottom: 1px solid var(--border);
                padding: 24px;
            }}
            .dashboard-stats {{
                flex-wrap: wrap;
            }}
            .stat {{
                min-width: 45%;
                flex: 1 1 45%;
            }}
            .detail-columns {{
                grid-template-columns: 1fr;
            }}
        }}
        @media (max-width: 480px) {{
            .page {{ padding: 24px 14px 48px; }}
            .header-title {{ font-size: 20px; }}
            .stat-value {{ font-size: 18px; }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <header class="header anim" style="animation-delay:0s">
            <div class="header-label">Evaluation Report</div>
            <h1 class="header-title">{_escape_html(report.agent_name)}</h1>
            <div class="header-meta">{timestamp} &middot; {report.total_tests} tests &middot; {duration_str}</div>
        </header>

        <div class="dashboard anim" style="animation-delay:0.06s">
            <div class="dashboard-gauge">
                <svg class="gauge-svg" width="132" height="132" viewBox="0 0 132 132">
                    <circle class="gauge-track" cx="66" cy="66" r="{radius}"/>
                    <circle class="gauge-fill" data-offset="{gauge_offset:.2f}" cx="66" cy="66" r="{radius}" transform="rotate(-90 66 66)"/>
                    <text class="gauge-pct" x="66" y="62">{pass_pct:.0f}%</text>
                    <text class="gauge-sublabel" x="66" y="80">pass rate</text>
                </svg>
            </div>
            <div class="dashboard-right">
                <div class="dashboard-stats">
                    <div class="stat">
                        <div class="stat-value">{report.total_tests}</div>
                        <div class="stat-label">Total</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value s-green">{report.passed_tests}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value s-red">{report.failed_tests}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{avg_score:.1f}</div>
                        <div class="stat-label">Avg Score</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{duration_str}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                </div>
                <div class="dashboard-dist">
                    <div class="dist-title">Score Distribution</div>
                    <div class="dist-chart">
                        {dist_bars_html}
                    </div>
                </div>
            </div>
        </div>

        {intent_groups_html}
        {empty_html}

        <footer class="footer anim" style="animation-delay:0.5s">Agent Evaluation Platform</footer>
    </div>

    <script>
        /* Expand / collapse */
        document.querySelectorAll('.test-row-header').forEach(function(header) {{
            header.addEventListener('click', function() {{
                var detail = header.nextElementSibling;
                var chevron = header.querySelector('.chevron');
                var isOpen = detail.classList.contains('open');
                if (isOpen) {{
                    detail.style.maxHeight = detail.scrollHeight + 'px';
                    detail.offsetHeight;
                    detail.style.maxHeight = '0px';
                    detail.classList.remove('open');
                    chevron.classList.remove('open');
                }} else {{
                    detail.classList.add('open');
                    chevron.classList.add('open');
                    detail.style.maxHeight = detail.scrollHeight + 'px';
                    detail.addEventListener('transitionend', function handler() {{
                        if (detail.classList.contains('open')) {{
                            detail.style.maxHeight = 'none';
                        }}
                        detail.removeEventListener('transitionend', handler);
                    }});
                }}
            }});
        }});

        /* Animate gauge on load */
        setTimeout(function() {{
            var g = document.querySelector('.gauge-fill');
            if (g) g.style.strokeDashoffset = g.getAttribute('data-offset');
        }}, 350);
    </script>
</body>
</html>"""


def _render_intent_groups(all_results) -> str:
    """Render test results grouped by intent name."""
    if not all_results:
        return ""

    groups = defaultdict(list)
    for r in all_results:
        groups[r.intent_name].append(r)

    # Sort: groups with failures first, then alphabetically
    sorted_groups = sorted(
        groups.items(),
        key=lambda x: (-sum(1 for r in x[1] if not r.passed), x[0]),
    )

    parts = []
    for idx, (intent_name, tests) in enumerate(sorted_groups):
        passed = sum(1 for t in tests if t.passed)
        total = len(tests)
        failed = total - passed

        # Sort within group: failed first, then by score ascending
        tests.sort(key=lambda t: (t.passed, t.score))

        tests_html = "\n".join(
            _render_test(t, "pass" if t.passed else "fail") for t in tests
        )

        fail_indicator = ""
        if failed > 0:
            fail_indicator = (
                f'<span class="intent-fail-indicator">'
                f"{failed} failed</span> &middot; "
            )

        delay = 0.12 + idx * 0.06
        parts.append(f"""
        <div class="intent-group anim" style="animation-delay:{delay:.2f}s">
            <div class="intent-header">
                <span class="intent-name">{_escape_html(intent_name)}</span>
                <span class="intent-meta">
                    {fail_indicator}<span class="intent-pass-count">{passed}/{total}</span>
                </span>
            </div>
            <div class="test-list">
                {tests_html}
            </div>
        </div>""")

    return "\n".join(parts)


def _render_score_distribution(score_dist, max_count) -> str:
    """Render score distribution histogram bars."""
    bars = []
    for i, count in enumerate(score_dist):
        score = i + 1
        height_pct = (count / max_count * 100) if max_count > 0 else 0
        if score >= 7:
            color = "var(--green)"
        elif score >= 4:
            color = "var(--amber)"
        else:
            color = "var(--red)"

        bar_style = (
            f"height:{height_pct}%;background:{color}"
            if count > 0
            else "height:2px;background:var(--border)"
        )

        bars.append(
            f'<div class="dist-col">'
            f'<div class="dist-bar-wrap">'
            f'<div class="dist-bar" style="{bar_style}"></div>'
            f"</div>"
            f'<div class="dist-num">{score}</div>'
            f"</div>"
        )
    return "\n".join(bars)


def _render_tests_section(title: str, tests, status_class: str) -> str:
    """Render a section of tests with a title."""
    if not tests:
        return ""
    tests_html = "\n".join(_render_test(t, status_class) for t in tests)
    return f"""
        <div class="intent-group">
            <div class="intent-header">
                <span class="intent-name">{_escape_html(title)}</span>
                <span class="intent-meta">{len(tests)}</span>
            </div>
            <div class="test-list">
                {tests_html}
            </div>
        </div>"""


def _render_test(test, status_class: str) -> str:
    expected = set(test.expected_tool_calls) if test.expected_tool_calls else set()
    actual = set(test.actual_tool_calls) if test.actual_tool_calls else set()

    expected_tags = _render_tool_tags(
        test.expected_tool_calls or [], actual, mode="expected"
    )
    actual_tags = _render_tool_tags(
        test.actual_tool_calls or [], expected, mode="actual"
    )

    score_pct = test.score * 10
    score_color = "var(--green)" if test.passed else "var(--red)"

    return f"""
                <div class="test-row">
                    <div class="test-row-header">
                        <div class="test-status-bar {status_class}"></div>
                        <div class="test-row-content">
                            <div class="test-name">{_escape_html(test.test_id)}</div>
                            <div class="score-bar-track">
                                <div class="score-bar-fill" style="width:{score_pct}%;background:{score_color}"></div>
                            </div>
                            <div class="test-score {status_class}">{test.score}/10</div>
                            <span class="chevron">&#x203A;</span>
                        </div>
                    </div>
                    <div class="test-detail">
                        <div class="test-detail-inner">
                            <div class="eval-section">
                                <div class="detail-label">Reasoning</div>
                                <div class="eval-text">{_escape_html(test.reasoning)}</div>
                            </div>
                            <details class="detail-disclosure">
                                <summary>Agent Input</summary>
                                <div class="disclosure-body">
                                    <div>
                                        <div class="detail-label">Message</div>
                                        <div class="msg-block">{_escape_html(test.input_message)}</div>
                                    </div>
                                    <div>
                                        <div class="detail-label">Context</div>
                                        <pre class="code-block">{_highlight_json(test.input_context)}</pre>
                                    </div>
                                    <div>
                                        <div class="detail-label">Backend State</div>
                                        <pre class="code-block">{_highlight_json(test.backend_state)}</pre>
                                    </div>
                                </div>
                            </details>
                            <details class="detail-disclosure">
                                <summary>Agent Output</summary>
                                <div class="disclosure-body">
                                    <div class="tool-calls-row">
                                        <div>
                                            <div class="detail-label">Expected Tools</div>
                                            <div class="tools-container">{expected_tags if expected_tags else '<span class="no-tools">none</span>'}</div>
                                        </div>
                                        <div>
                                            <div class="detail-label">Actual Tools</div>
                                            <div class="tools-container">{actual_tags if actual_tags else '<span class="no-tools">none</span>'}</div>
                                        </div>
                                    </div>
                                    <div>
                                        <div class="detail-label">Response</div>
                                        <pre class="code-block">{_escape_html(test.output)}</pre>
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>"""


def _render_tool_tags(tools: list[str], comparison_set: set, mode: str) -> str:
    """Render tool name tags with color coding."""
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


def _highlight_json(data) -> str:
    """Render JSON with syntax highlighting."""
    if not data:
        return '<span class="json-null">null</span>'

    json_str = json.dumps(data, indent=2, default=str)
    result = []
    i = 0
    n = len(json_str)

    while i < n:
        ch = json_str[i]

        if ch == '"':
            j = i + 1
            while j < n:
                if json_str[j] == "\\":
                    j += 2
                    continue
                if json_str[j] == '"':
                    break
                j += 1
            j = min(j + 1, n)
            token = _escape_html(json_str[i:j])
            rest = json_str[j:].lstrip()
            if rest.startswith(":"):
                result.append(f'<span class="json-key">{token}</span>')
            else:
                result.append(f'<span class="json-str">{token}</span>')
            i = j

        elif ch == "-" or ch.isdigit():
            j = i + 1
            while j < n and json_str[j] in "0123456789.eE+-":
                j += 1
            result.append(f'<span class="json-num">{json_str[i:j]}</span>')
            i = j

        elif json_str[i : i + 4] == "true":
            result.append('<span class="json-bool">true</span>')
            i += 4

        elif json_str[i : i + 5] == "false":
            result.append('<span class="json-bool">false</span>')
            i += 5

        elif json_str[i : i + 4] == "null":
            result.append('<span class="json-null">null</span>')
            i += 4

        elif ch in "{}[]":
            result.append(f'<span class="json-bracket">{ch}</span>')
            i += 1

        else:
            result.append(_escape_html(ch))
            i += 1

    return "".join(result)
