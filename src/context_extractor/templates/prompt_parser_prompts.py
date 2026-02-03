"""LLM prompt templates for prompt parser."""

INTENT_EXTRACTION_PROMPT = """Extract all agent intents from its system prompt, available tools, and rules from its code. An intent is a goal or task the agent can help with.

## SYSTEM PROMPT
{system_prompt}

## AVAILABLE TOOLS
{tools_context}

## BUSINESS RULES PARSED FROM CODE
{code_rules_context}

Each intent must be a single goal or task the agent can help with. For each intent, extract the following:
- name: Intent name (e.g., 'process_refund')
- description: What this intent does
- required_slots: Information the agent needs to fulfill this intent (with their sources)
- workflow: Step-by-step process the agent will follow to fulfill this intent
- rules: All rules including precondition checks, business logic, conditional logic, and invalid input tests (e.g., rules for missing required fields, validation checks, business logic)
- requires_confirmation: Whether the agent should ask for confirmation before fulfilling this intent
- outcomes: Possible outcomes - use the actual return values from the tools used in this intent's workflow

Return a JSON array of intents:
```json
[
  {{
    "name": "string",
    "description": "string",
    "required_slots": [
        {{
        "slot_name": "entity_name_in_snake_case",
        "source": "{source_options}"
        }}
    ],
    "workflow": ["string"],
    "rules": [
        {{
        "description": "string",
        "conditions": ["conditions to check"],
        "actions": ["what to do if conditions are met"]
        }}
    ],
    "requires_confirmation": boolean,
    "outcomes": [
        {{
        "outcome_name": "string",
        "description": "string"
        }}
    ]
  }}
]
```
"""

AGENT_IDENTITY_EXTRACTION_PROMPT = """Extract the agent's name and role from this system prompt.

System Prompt:
{system_prompt}

Respond with a JSON object:
{{
  "name": "string",
  "role": "string"
}}"""
