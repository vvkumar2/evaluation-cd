"""Validate extracted outputs against schemas."""

import json
from typing import Optional
from pathlib import Path

from ..schemas.tool_schema import EnrichedToolSchemaList
from ..schemas.entity_schema import EnrichedEntitySchemaList
from ..schemas.prompt_schema import (
    StructuredIntentRule,
    StructuredSystemPromptExtraction,
    StructuredIntent,
)


class ValidationError:
    def __init__(self, error_type: str, message: str, context: Optional[dict] = None):
        self.error_type = error_type
        self.message = message
        self.context = context or {}

    def __repr__(self):
        return f"ValidationError({self.error_type}: {self.message})"

    def to_dict(self):
        return {
            "type": self.error_type,
            "message": self.message,
            "context": self.context,
        }


class ValidationResult:
    def __init__(self, is_valid: bool, errors: list[ValidationError] = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def __repr__(self):
        return f"ValidationResult(valid={self.is_valid}, errors={len(self.errors)})"

    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
        }


class AgentTestValidator:
    """Validates that extracted tools, entities, and prompts are semantically consistent."""

    def __init__(self):
        self.tool_names = set()
        self.entity_names = set()
        self.entity_fields = {}
        self.valid_operators = {
            "eq",
            "ne",
            "lt",
            "lte",
            "gt",
            "gte",
            "in",
            "not_in",
            "exists",
            "missing",
        }

    def validate_parsed_output(
        self,
        tools: EnrichedToolSchemaList,
        entities: EnrichedEntitySchemaList,
        prompt_extraction: StructuredSystemPromptExtraction,
    ) -> ValidationResult:
        errors = []

        # Build lookup tables
        self.tool_names = {tool.name for tool in tools.tools}
        self.entity_names = {entity.name for entity in entities.entities}
        self.entity_fields = {
            entity.name: {field.name for field in entity.fields}
            for entity in entities.entities
        }

        # Validate each intent
        for intent in prompt_extraction.intents:
            errors.extend(self._validate_intent(intent))

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors)

    def _validate_intent(self, intent: StructuredIntent) -> list[ValidationError]:
        """Validate intent structure and semantic consistency."""
        errors = []

        # Build set of valid outcome names for this intent
        valid_outcomes = {outcome.outcome_name for outcome in intent.outcomes}

        # Check that all outcomes are covered by at least one rule
        outcomes_with_rules = set()

        # Validate each rule
        for rule in intent.rules:
            rule_errors = self._validate_rule(
                rule, intent.name, valid_outcomes, self.entity_fields
            )
            errors.extend(rule_errors)

            # Track which outcomes have rules
            if not any(
                e.error_type == "invalid_outcome_reference" for e in rule_errors
            ):
                outcomes_with_rules.add(rule.outcome)

        # Check outcome coverage
        uncovered_outcomes = valid_outcomes - outcomes_with_rules
        for outcome_name in uncovered_outcomes:
            errors.append(
                ValidationError(
                    "outcome_not_covered",
                    f"Outcome '{outcome_name}' in intent '{intent.name}' has no rules that lead to it",
                    {"intent_name": intent.name, "outcome": outcome_name},
                )
            )

        return errors

    def _validate_rule(
        self,
        rule: StructuredIntentRule,
        intent_name: str,
        valid_outcomes: set,
        entity_fields: dict,
    ) -> list[ValidationError]:
        """Validate a single rule."""
        errors = []

        # Check outcome reference
        if rule.outcome not in valid_outcomes:
            errors.append(
                ValidationError(
                    "invalid_outcome_reference",
                    f"Rule '{rule.id}' in intent '{intent_name}' references unknown outcome '{rule.outcome}'",
                    {
                        "intent_name": intent_name,
                        "rule_id": rule.id,
                        "outcome": rule.outcome,
                    },
                )
            )

        # Check expected_behavior is not empty
        if not rule.expected_behavior:
            errors.append(
                ValidationError(
                    "missing_required_field",
                    f"Rule '{rule.id}' in intent '{intent_name}' missing expected_behavior",
                    {"intent_name": intent_name, "rule_id": rule.id},
                )
            )

        # Validate each condition
        for condition in rule.conditions:
            cond_errors = self._validate_condition(
                condition, rule.id, intent_name, entity_fields
            )
            errors.extend(cond_errors)

        return errors

    def _validate_condition(
        self,
        condition,
        rule_id: str,
        intent_name: str,
        entity_fields: dict,
    ) -> list[ValidationError]:
        """Validate a single condition."""
        errors = []

        # Check operator validity
        if condition.operator not in self.valid_operators:
            errors.append(
                ValidationError(
                    "invalid_operator",
                    f"Condition in rule '{rule_id}' has invalid operator '{condition.operator}'",
                    {
                        "intent_name": intent_name,
                        "rule_id": rule_id,
                        "operator": condition.operator,
                    },
                )
            )

        # Validate field reference
        if condition.field:
            field_errors = self._validate_field_reference(
                condition.field, rule_id, intent_name, entity_fields
            )
            errors.extend(field_errors)

        return errors

    def _validate_field_reference(
        self,
        field_ref: str,
        rule_id: str,
        intent_name: str,
        entity_fields: dict,
    ) -> list[ValidationError]:
        """Validate that a field reference points to a real entity field or slot."""
        errors = []

        # Check if it's an entity field reference (e.g., "customer.tier")
        if "." in field_ref:
            parts = field_ref.split(".", 1)
            entity_name, field_name = parts[0], parts[1]

            # Check entity exists
            if entity_name not in entity_fields:
                errors.append(
                    ValidationError(
                        "invalid_entity_reference",
                        f"Rule '{rule_id}' references unknown entity '{entity_name}' in field '{field_ref}'",
                        {
                            "intent_name": intent_name,
                            "rule_id": rule_id,
                            "field": field_ref,
                        },
                    )
                )
            # Check field exists in entity
            elif field_name not in entity_fields[entity_name]:
                errors.append(
                    ValidationError(
                        "invalid_field_reference",
                        f"Rule '{rule_id}' references unknown field '{field_name}' in entity '{entity_name}'",
                        {
                            "intent_name": intent_name,
                            "rule_id": rule_id,
                            "field": field_ref,
                        },
                    )
                )
        # Field references without dot are slot names - we don't validate those here since slots are intent-specific

        return errors

    def write_validation_errors(
        self, validation_result: ValidationResult, output_path: Path
    ) -> None:
        """Write validation errors to a JSON file alongside the main output."""
        if not validation_result.errors:
            return

        # Create error output path (e.g., "extraction.yml" -> "extraction_errors.json")
        error_path = output_path.parent / f"{output_path.stem}_errors.json"

        with open(error_path, "w") as f:
            json.dump(validation_result.to_dict(), f, indent=2)

    def fix_validation_errors(
        self,
        tools: EnrichedToolSchemaList,
        entities: EnrichedEntitySchemaList,
        prompt_extraction: StructuredSystemPromptExtraction,
    ) -> tuple[
        EnrichedToolSchemaList,
        EnrichedEntitySchemaList,
        StructuredSystemPromptExtraction,
    ]:
        """Attempt to fix common validation errors (currently a placeholder for future enhancement)."""
        return tools, entities, prompt_extraction
