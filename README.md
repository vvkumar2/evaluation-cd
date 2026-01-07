# AgentEval

A CLI tool for evaluating conversational AI agents against knowledge bases.

## Features

- **Automatic Test Generation**: Analyze knowledge bases and generate Q&A test cases using LLM + heuristics
- **Agent Execution**: Run agents against tests with support for CLI, Python, and HTTP interfaces
- **Evaluation Framework**: Score responses for factual accuracy, completeness, and consistency
- **Rich Reporting**: Terminal output with Rich and HTML report generation

## Installation

```bash
pip install agenteval
```

Or install from source:

```bash
git clone https://github.com/agenteval/agenteval.git
cd agenteval
pip install -e .
```

## Quick Start

### 1. Initialize configuration

```bash
agenteval init
```

This creates an `agenteval.yaml` configuration file.

### 2. Generate tests from your knowledge base

```bash
agenteval generate ./knowledge-base --output tests.yaml
```

This analyzes your knowledge base documents and generates test cases.

### 3. Run your agent against the tests

```bash
agenteval run --agent "python my_agent.py" --tests tests.yaml --kb ./knowledge-base
```

### 4. View results

```bash
agenteval report results.json
```

## Example

See the `examples/` folder for a complete working example with:
- Sample knowledge base (TechGear e-commerce customer service)
- Sample LLM-based agent
- Expected test cases

```bash
cd examples/
agenteval generate ./knowledge-base --output tests.yaml
agenteval run --agent "python sample_agent/agent.py" --tests tests.yaml
```

## Configuration

Create an `agenteval.yaml` file:

```yaml
# LLM settings for test generation and evaluation
llm:
  provider: openai  # or anthropic, ollama, etc.
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}  # Uses environment variable

# Test generation settings
generation:
  count: 30  # Number of tests to generate
  types:
    qa: 0.7       # 70% simple Q&A
    edge: 0.2     # 20% edge cases
    consistency: 0.1  # 10% consistency tests

# Evaluation settings
evaluation:
  weights:
    factual_accuracy: 0.4
    completeness: 0.3
    citation: 0.2
    tone: 0.1
  pass_threshold: 0.7
```

## Test Case Format

```yaml
tests:
  - id: test_001
    type: qa
    input:
      message: "What is your return policy?"
    expected:
      contains_facts:
        - "30-day return window"
        - "original packaging required"
      sources: ["policies/returns.md"]
```

## License

MIT

