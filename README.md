# AgentEval - AI Agent Testing Platform

A local-first tool for testing and evaluating AI agents by analyzing codebases to automatically generate test cases.

## Overview

AgentEval analyzes your application codebase to extract business logic, policies, and validation rules, then automatically generates test cases to evaluate AI agent behavior. Currently focused on **customer service agents** with multi-turn conversation support.

## How It Works

```
Your Codebase → Extract Business Logic → Generate Test Cases → Run Agent → Evaluate → Report
```

**Example:** You have a customer service agent for an e-commerce site. AgentEval:
1. Analyzes your `refund_processor.py` to find refund policies (30-day window, $200 limit, etc.)
2. Generates test cases like "angry customer wants refund outside window"
3. Runs your agent against these scenarios
4. Evaluates using LLM-as-judge (empathy, resolution, policy compliance)
5. Shows you what passed, what failed, and why

## Features

- **Automated Test Generation**: Analyzes Python codebases to extract testable business logic
- **Multi-Turn Conversations**: Test dialogues with checkpoint-based evaluation
- **LLM-as-Judge**: Score subjective qualities (empathy, tone, helpfulness)
- **Policy Compliance**: Hard checks for business rule violations
- **Local Execution**: No external services needed (beyond LLM API for evaluation)

## Quick Start

### 1. Install

```bash
cd evaluation-cd
pip install -r requirements.txt

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### 2. Option A: Full Pipeline (Easiest)

Run everything in one command:

```bash
python -m src.cli.main full \
  --codebase ./my-cs-agent \
  --agent "python my_agent.py" \
  --max-tests 10
```

This will:
1. Analyze your codebase
2. Generate test cases
3. Run tests against your agent
4. Evaluate with LLM-as-judge
5. Show results

### 2. Option B: Step-by-Step

**Generate test cases:**
```bash
python -m src.cli.main generate \
  --codebase ./my-cs-agent \
  --output tests/generated.yaml \
  --max-tests 20
```

**Run tests:**
```bash
python -m src.cli.main run \
  --tests tests/generated.yaml \
  --agent "python my_agent.py" \
  --output results/execution.json
```

**Evaluate results:**
```bash
python -m src.cli.main evaluate \
  --results results/execution.json \
  --output results/evaluation.json \
  --use-llm
```

**View report:**
```bash
python -m src.cli.main report \
  --results results/evaluation.json \
  --format detailed
```

### 3. Example Output

```
AgentEval Results
════════════════════════════════════════════════════════════════════

┌─ Summary ──────────────────────────────────────────────────────┐
│ Passed: 7/10 (70.0%)                                            │
│ Failed: 3                                                       │
│ Errors: 0                                                       │
│ LLM Used: True                                                  │
└─────────────────────────────────────────────────────────────────┘

                          Test Results
┌──────────────────────────────┬────────┬───────┬───────────┐
│ Test                         │ Status │ Score │ Threshold │
├──────────────────────────────┼────────┼───────┼───────────┤
│ refund_request_gold          │ ✓ PASS │  0.82 │      0.70 │
│ angry_customer_broken_produc │ ✗ FAIL │  0.65 │      0.70 │
│ policy_violation_refund_wind │ ✓ PASS │  0.91 │      0.80 │
└──────────────────────────────┴────────┴───────┴───────────┘
```

## Project Structure

```
evaluation-cd/
├── src/
│   ├── analyzer/          # Codebase analysis
│   │   ├── parser.py      # AST parsing
│   │   ├── extractor.py   # Extract business logic
│   │   └── scorer.py      # Prioritize test-worthy code
│   ├── generator/         # Test case generation
│   │   ├── templates.py   # Test templates
│   │   └── generator.py   # LLM-assisted generation
│   ├── runner/            # Test execution
│   │   └── runner.py      # Orchestrate test runs
│   ├── evaluator/         # Evaluation engine
│   │   ├── llm_judge.py   # LLM-based evaluation
│   │   ├── compliance.py  # Policy checking
│   │   └── metrics.py     # Scoring
│   └── cli/               # CLI interface
│       └── main.py
├── tests/                 # Unit tests
└── examples/              # Example agents
    └── sample_cs_agent/   # Sample customer service agent
```

## Example Test Case

```yaml
test_case:
  id: "refund-angry-customer"
  name: "Angry customer requesting refund for damaged item"

  context:
    customer_tier: "gold"
    order_value: 149.99
    days_since_delivery: 5

  conversation:
    - turn: 1
      customer: "This is ridiculous! My headphones are broken!"

      checkpoints:
        - criterion: "empathy"
          must: "Acknowledge frustration explicitly"
        - criterion: "no_blame"
          must_not: "Blame customer or shipping"

    - turn: 2
      customer: "Fine. What can you do about it?"

      checkpoints:
        - criterion: "offers_solution"
          must: "Offer refund or replacement with timeline"
        - criterion: "gold_benefits"
          must: "Mention expedited shipping for gold members"

  evaluation:
    dimensions:
      - empathy: weight 0.25
      - resolution: weight 0.30
      - policy_compliance: weight 0.25
      - efficiency: weight 0.20
    pass_threshold: 4.0/5.0
```

## Configuration

Create `.env`:

```bash
# LLM API for evaluation
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

## Status

🚧 **MVP in Development**

Current: Building codebase analyzer and test generator

## License

MIT
