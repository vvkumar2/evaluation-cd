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
```

### 2. Analyze Your Codebase

```bash
python -m src.cli.main generate \
  --codebase ./my-cs-agent \
  --output tests/generated.yaml
```

This extracts business logic and generates test cases.

### 3. Run Tests

```bash
python -m src.cli.main run \
  --tests tests/generated.yaml \
  --agent "python my_agent.py"
```

### 4. View Results

```
✓ handles_refund_within_window    (4.5/5.0, 2.3s)
✗ angry_customer_de_escalation    (2.8/5.0, 1.9s)
  - Empathy: 2/5 (didn't acknowledge frustration)
  - Policy: 5/5 (followed refund rules)

Results: 1/2 passed (50%)
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
