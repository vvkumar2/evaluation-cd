"""Step 4: Validate extracted outputs against schemas."""

from typing import Optional

from ..schemas.tool_schema import ToolSchemaOutput
from ..schemas.entity_schema import EntitySchemaOutput
from ..schemas.prompt_schema import SystemPromptExtraction, Intent


class ValidationError:
    """A validation error."""

    def __init__(self, error_type: str, message: str, context: Optional[dict] = None):
        self.error_type = error_type
        self.message = message
        self.context = context or {}

    def __repr__(self):
        return f"ValidationError({self.error_type}: {self.message})"


class ValidationResult:
    """Result of validation."""

    def __init__(self, is_valid: bool, errors: list[ValidationError] = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def __repr__(self):
        return f"ValidationResult(valid={self.is_valid}, errors={len(self.errors)})"


class AgentTestValidator:
    """Validates extracted agent information."""

    def __init__(self):
        self.tool_names = set()
        self.entity_names = set()
        self.entity_fields = {}

    def validate_parsed_output(
        self,
        tools: ToolSchemaOutput,
        entities: EntitySchemaOutput,
        prompt_extraction: SystemPromptExtraction,
    ) -> ValidationResult:
        """
        Validate extracted outputs.

        Args:
            tools: Extracted tool schemas
            entities: Extracted entity schemas
            prompt_extraction: Extracted prompt information

        Returns:
            ValidationResult with any errors found
        """
        errors = []

        # Index tools and entities for validation
        self.tool_names = {tool.name for tool in tools.tools}
        self.entity_names = {entity.name for entity in entities.entities}
        self.entity_fields = {
            entity.name: {field.name for field in entity.fields}
            for entity in entities.entities
        }

        # Validate intents
        for intent in prompt_extraction.intents:
            errors.extend(self._validate_intent(intent))

        # Validate global rules
        for rule in prompt_extraction.global_rules:
            for intent_name in rule.applies_to:
                if intent_name not in {i.name for i in prompt_extraction.intents}:
                    errors.append(
                        ValidationError(
                            "invalid_intent_reference",
                            f"Global rule '{rule.name}' references unknown intent '{intent_name}'",
                            {"rule_name": rule.name, "intent_name": intent_name},
                        )
                    )

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors)

    def _validate_intent(self, intent: Intent) -> list[ValidationError]:
        """Validate a single intent."""
        errors = []

        # Intent should have basic info
        if not intent.name:
            errors.append(
                ValidationError(
                    "missing_required_field",
                    "Intent missing name",
                )
            )

        if not intent.description:
            errors.append(
                ValidationError(
                    "missing_required_field",
                    f"Intent '{intent.name}' missing description",
                    {"intent_name": intent.name},
                )
            )

        if not intent.trigger_examples:
            errors.append(
                ValidationError(
                    "missing_required_field",
                    f"Intent '{intent.name}' missing trigger examples",
                    {"intent_name": intent.name},
                )
            )

        # Validate intent rules
        for rule in intent.rules:
            if not rule.description:
                errors.append(
                    ValidationError(
                        "missing_required_field",
                        f"Rule in intent '{intent.name}' missing description",
                        {"intent_name": intent.name},
                    )
                )

            if not rule.actions:
                errors.append(
                    ValidationError(
                        "missing_required_field",
                        f"Rule '{rule.description}' in intent '{intent.name}' missing actions",
                        {"intent_name": intent.name, "rule_description": rule.description},
                    )
                )

        # Validate outcomes
        for outcome in intent.outcomes:
            if not outcome.outcome_name:
                errors.append(
                    ValidationError(
                        "missing_required_field",
                        f"Outcome in intent '{intent.name}' missing name",
                        {"intent_name": intent.name},
                    )
                )

        return errors

    def fix_validation_errors(
        self,
        tools: ToolSchemaOutput,
        entities: EntitySchemaOutput,
        prompt_extraction: SystemPromptExtraction,
        errors: list[ValidationError],
    ) -> tuple[ToolSchemaOutput, EntitySchemaOutput, SystemPromptExtraction]:
        """
        Fix validation errors in extracted outputs.

        This is a best-effort attempt to fix common errors.

        Args:
            tools: Extracted tool schemas
            entities: Extracted entity schemas
            prompt_extraction: Extracted prompt information
            errors: Validation errors to fix

        Returns:
            Tuple of fixed outputs
        """
        # For now, just return as-is
        # More sophisticated fixing could be added based on error types

        return tools, entities, prompt_extraction
