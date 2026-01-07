# AgentEval Demo - Complete Walkthrough

This demonstrates the full AgentEval pipeline with a sample customer service agent.

## Sample Agent

**TechGear Customer Service Agent** - A rule-based customer service bot for an e-commerce platform.

**Business Logic:**
- `refund_processor.py` - Handles refunds with tiered policies (30/60/90 day windows)
- `order_manager.py` - Manages orders, shipping, and modifications

**Key Policies Extracted:**
- Standard customers: 30-day refund window
- Gold customers: 60-day refund window
- Refunds up to $200: auto-approved
- Refunds $200-$1000: manager approval needed
- Free shipping on orders > $50
- Gold members: free expedited shipping

## Pipeline Execution

### Step 1: Generate Test Cases

```bash
python3 -m src.cli.main generate \
  --codebase examples/sample_cs_agent/business_logic \
  --output examples/generated_tests.yaml \
  --max-tests 5
```

**Results:**
- Parsed 3 Python files
- Found 26 policies
- Found 9 testable scenarios
- Generated 5 test cases

**Test Categories:**
- `refunds`: 4 tests
- `policy_enforcement`: 1 test

### Step 2: Run Tests

```bash
python3 -m src.cli.main run \
  --tests examples/generated_tests.yaml \
  --agent "python3 examples/sample_cs_agent/agent.py" \
  --output examples/execution_results.json
```

**Results:**
- 5/5 tests executed successfully
- Average response time: ~150ms per turn

### Step 3: Evaluate

```bash
python3 -m src.cli.main evaluate \
  --results examples/execution_results.json \
  --output examples/evaluation_results.json \
  --no-llm
```

**Results:**
- 0/5 tests passed (without LLM judge, only compliance checks)
- Issues identified:
  - Missing empathy acknowledgment in turn 1
  - Missing information gathering questions
  - Some policy explanations not detailed enough

### Step 4: View Report

```bash
python3 -m src.cli.main report \
  --results examples/evaluation_results.json \
  --format detailed
```

## Sample Test Case

Here's one of the generated test cases:

```yaml
- id: test_RefundProcessor.__init___happy_path
  name: RefundProcessor.__init___happy_path
  category: refunds

  conversation:
    name: refund_request_standard
    scenario_type: happy_path
    context:
      customer_tier: standard
      order:
        item: product
        price: 99.99
        delivered_date_days_ago: 5

    turns:
      - customer_message: "I want to return my product. It doesn't work as expected."
        checkpoints:
          - criterion: empathy
            check_type: must
            description: Acknowledges customer's issue

          - criterion: information_gathering
            check_type: must
            description: Asks about order details

          - criterion: no_immediate_refusal
            check_type: must_not
            description: Does not refuse without understanding
```

## Agent Response

**Turn 1:**
```
Customer: I want to return my product. It doesn't work as expected.

Agent: I can help you with that. I can absolutely help with a refund.
Since you're within our 30-day return window, you're eligible for a
full refund of $99.99. I've initiated the refund, and you should see
it in 3-5 business days. Is there anything else I can help you with?
```

**Evaluation:**
- ❌ **Empathy**: Missing explicit acknowledgment of customer frustration
- ❌ **Information Gathering**: Jumped straight to solution without asking questions
- ✅ **No Immediate Refusal**: Correctly didn't refuse
- ✅ **Offers Solution**: Provided refund details
- ✅ **Timeline**: Gave specific timeframe

**Overall Score:** 0.63/1.0 (below 0.70 threshold)

## Improvement Suggestions

Based on evaluation, the agent should:

1. **Add empathy**: "I'm sorry to hear you're having issues with your product"
2. **Gather information first**: "Can you tell me your order number?"
3. **Explain policies clearly**: Mention the 30-day window explicitly

## With LLM-as-Judge (Optional)

To use GPT-4 or Claude for more nuanced evaluation:

```bash
# Add API key to .env
echo "OPENAI_API_KEY=sk-..." >> .env

# Re-run evaluation with LLM
python3 -m src.cli.main evaluate \
  --results examples/execution_results.json \
  --output examples/evaluation_llm.json \
  --use-llm \
  --llm-provider openai
```

This would add scores for:
- Empathy (1-5)
- Resolution (1-5)
- Policy Compliance (1-5)
- Efficiency (1-5)

Plus reasoning for each score.

## Full Pipeline Command

Run everything in one command:

```bash
python3 -m src.cli.main full \
  --codebase examples/sample_cs_agent/business_logic \
  --agent "python3 examples/sample_cs_agent/agent.py" \
  --max-tests 5 \
  --output-dir results
```

This will:
1. Generate tests from codebase
2. Run tests against agent
3. Evaluate with compliance checks (+ LLM if API key set)
4. Show detailed report

## What This Demonstrates

✅ **Automatic test generation** from business logic
✅ **Multi-turn conversation testing** with context
✅ **Checkpoint-based evaluation** (must/must_not/should)
✅ **Actionable feedback** (specific failures + suggestions)
✅ **Ready for LLM-as-judge** integration
✅ **Complete CLI workflow**

The MVP is fully functional and ready to test real customer service agents!
