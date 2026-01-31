import json
from ..schemas.prompt_schema import (
    SystemPromptExtraction,
    Intent,
    IntentRule,
    IntentOutcome,
    IntentRequiredSlot,
    GlobalRule,
    Refusal,
)
from ..schemas.tool_schema import ToolSchemaList

class SystemPromptParser:
    """Extracts intents, rules, and refusals from system prompts using LLM analysis."""

    def __init__(self, client=None):
        """Initialize parser with optional LLM client."""
        self.client = client

    def extract_intents(
        self,
        system_prompt: str,
        tools: ToolSchemaList = None,
    ) -> list[Intent]:
        """Use LLM to identify goals and tasks the agent can help with."""
        prompt = self._build_intent_extraction_prompt(system_prompt, tools)
        response = self._call_llm(prompt)
        intents = self._parse_intent_response(response)
        return intents

    def extract_global_rules(
        self,
        system_prompt: str,
        intents: list[Intent],
    ) -> list[GlobalRule]:
        """Use LLM to identify rules that apply across multiple intents."""
        prompt = self._build_global_rule_extraction_prompt(system_prompt, intents)
        response = self._call_llm(prompt)
        rules = self._parse_global_rule_response(response)
        return rules

    def extract_refusals(
        self,
        system_prompt: str,
    ) -> list[Refusal]:
        """Use LLM to identify requests and behaviors the agent should refuse."""
        prompt = self._build_refusal_extraction_prompt(system_prompt)
        response = self._call_llm(prompt)
        refusals = self._parse_refusal_response(response)
        return refusals

    def parse_system_prompt(
        self,
        system_prompt: str,
        tools: ToolSchemaList = None,
    ) -> SystemPromptExtraction:
        """Extract all business logic from system prompt: identity, intents, rules, and refusals."""
        intents = self.extract_intents(system_prompt, tools)
        global_rules = self.extract_global_rules(system_prompt, intents)
        refusals = self.extract_refusals(system_prompt)
        agent_name, agent_role = self._extract_agent_identity(system_prompt)

        return SystemPromptExtraction(
            agent_name=agent_name,
            agent_role=agent_role,
            intents=intents,
            global_rules=global_rules,
            refusals=refusals,
        )

    def _build_intent_extraction_prompt(
        self,
        system_prompt: str,
        tools: ToolSchemaList = None,
    ) -> str:
        """Build LLM prompt for intent extraction."""
        tools_context = ""
        tool_names_list = []
        if tools:
            tools_context = "\n\nAvailable Tools:\n"
            for tool in tools.tools:
                tools_context += f"- {tool.name}: {tool.description}\n"
                tool_names_list.append(tool.name)

        source_options = "user_input"
        if tool_names_list:
            source_options += " | " + " | ".join(tool_names_list)

        return f"""Extract all intents from this system prompt. An intent is a goal or task the agent can help with.

System Prompt:
{system_prompt}
{tools_context}

For each intent, extract:
- name: Intent name (e.g., 'process_refund', 'check_order_status')
- description: What this intent does
- trigger_examples: 3-5 example customer messages that would trigger this intent
- required_slots: Information the agent needs to fulfill this intent (with their sources)
- workflow: Step-by-step process for handling this intent
- rules: Specific rules that apply to this intent
- requires_confirmation: Whether the agent should ask for confirmation
- outcomes: Possible outcomes - use the actual return values from the tools used in this intent's workflow

Respond with a JSON array of intent objects with this structure:
{{
  "name": "string",
  "description": "string",
  "trigger_examples": ["string"],
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
      "conditions": ["string"],
      "actions": ["string"]
    }}
  ],
  "requires_confirmation": boolean,
  "outcomes": [
    {{
      "outcome_name": "string",
      "description": "string",
      "triggering_conditions": ["string"]
    }}
  ]
}}"""

    def _build_global_rule_extraction_prompt(
        self,
        system_prompt: str,
        intents: list[Intent],
    ) -> str:
        """Build LLM prompt for global rule extraction."""
        intent_names = [i.name for i in intents]

        return f"""Extract global rules from this system prompt. Global rules apply across multiple intents.

System Prompt:
{system_prompt}

Available Intents: {', '.join(intent_names)}

For each rule, extract:
- name: Rule name
- description: What the rule enforces
- applies_to: Which intents this rule applies to
- behavior: How to enforce this rule

Respond with a JSON array of rule objects with this structure:
{{
  "name": "string",
  "description": "string",
  "applies_to": ["string"],
  "behavior": "string"
}}"""

    def _build_refusal_extraction_prompt(self, system_prompt: str) -> str:
        """Build LLM prompt for refusal extraction."""
        return f"""Extract things the agent should refuse to do from this system prompt.

System Prompt:
{system_prompt}

For each refusal, extract:
- reason: Why the agent refuses
- trigger_patterns: Patterns or requests that trigger the refusal
- response: How the agent should respond to the refusal

Respond with a JSON array of refusal objects with this structure:
{{
  "reason": "string",
  "trigger_patterns": ["string"],
  "response": "string"
}}"""

    def _extract_agent_identity(self, system_prompt: str) -> tuple[str, str]:
        """Use LLM to extract agent's name and role."""
        prompt = f"""Extract the agent's name and role from this system prompt.

System Prompt:
{system_prompt}

Respond with a JSON object:
{{
  "name": "string",
  "role": "string"
}}"""

        response = self._call_llm(prompt)

        try:
            data = json.loads(response)
            name = data.get("name", "Agent")
            role = data.get("role", "AI Assistant")
            return name, role
        except (json.JSONDecodeError, TypeError):
            return "Agent", "AI Assistant"

    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON from response, handling markdown code blocks."""
        if not self.client:
            return "{}"

        try:
            # Try to use OpenAI client format
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = response.choices[0].message.content

            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()

            return content
        except Exception:
            # Fallback
            return "{}"

    def _parse_intent_response(self, response: str) -> list[Intent]:
        """Parse JSON response from LLM and convert to Intent objects."""
        intents = []

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    # Parse rules
                    rules = []
                    for rule_def in item.get("rules", []):
                        rule = IntentRule(
                            description=rule_def.get("description", ""),
                            conditions=rule_def.get("conditions", []),
                            actions=rule_def.get("actions", []),
                        )
                        rules.append(rule)

                    # Parse outcomes
                    outcomes = []
                    for outcome_def in item.get("outcomes", []):
                        outcome = IntentOutcome(
                            outcome_name=outcome_def.get("outcome_name", ""),
                            description=outcome_def.get("description", ""),
                            triggering_conditions=outcome_def.get(
                                "triggering_conditions", []
                            ),
                        )
                        outcomes.append(outcome)

                    required_slots = []
                    for slot_def in item.get("required_slots", []):
                        if isinstance(slot_def, dict):
                            slot = IntentRequiredSlot(
                                slot_name=slot_def.get("slot_name", "unknown"),
                                source=slot_def.get("source", "user_input"),
                            )
                            required_slots.append(slot)

                    intent = Intent(
                        name=item.get("name", "unknown"),
                        description=item.get("description", ""),
                        trigger_examples=item.get("trigger_examples", []),
                        required_slots=required_slots,
                        workflow=item.get("workflow", []),
                        rules=rules,
                        requires_confirmation=item.get("requires_confirmation", False),
                        outcomes=outcomes,
                    )
                    intents.append(intent)
        except (json.JSONDecodeError, TypeError):
            pass

        return intents

    def _parse_global_rule_response(self, response: str) -> list[GlobalRule]:
        """Parse JSON response from LLM and convert to GlobalRule objects."""
        rules = []

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    rule = GlobalRule(
                        name=item.get("name", "unknown"),
                        description=item.get("description", ""),
                        applies_to=item.get("applies_to", []),
                        behavior=item.get("behavior", ""),
                    )
                    rules.append(rule)
        except (json.JSONDecodeError, TypeError):
            pass

        return rules

    def _parse_refusal_response(self, response: str) -> list[Refusal]:
        """Parse JSON response from LLM and convert to Refusal objects."""
        refusals = []

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    refusal = Refusal(
                        reason=item.get("reason", ""),
                        trigger_patterns=item.get("trigger_patterns", []),
                        response=item.get("response", ""),
                    )
                    refusals.append(refusal)
        except (json.JSONDecodeError, TypeError):
            pass

        return refusals
