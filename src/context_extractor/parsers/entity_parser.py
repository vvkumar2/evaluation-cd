from ..schemas.entity_schema import (
    EntitySchema,
    EntitySchemaList,
    EntityField,
)


def parse_entity_schema(entity_data: dict) -> EntitySchemaList:
    return EntitySchemaList(
        entities=[
            _parse_single_entity(entity) for entity in entity_data["entities"]
        ]
    )


def _parse_single_entity(entity: dict) -> EntitySchema:
    """Parse single entity with fields."""
    name = entity.get("name", "unknown")
    description = entity.get("description", "")
    fields = _parse_fields(entity.get("fields", []))

    return EntitySchema(
        name=name,
        description=description,
        fields=fields,
    )


def _parse_fields(fields_data: list | dict) -> list[EntityField]:
    """Parse entity fields."""
    fields = []

    if isinstance(fields_data, dict):
        for field_name, field_schema in fields_data.items():
            field = _parse_field(field_name, field_schema)
            fields.append(field)
    elif isinstance(fields_data, list):
        for field_def in fields_data:
            field = _parse_field(
                field_def.get("name", "unknown"),
                field_def,
            )
            fields.append(field)

    return fields


def _parse_field(name: str, schema: dict | str) -> EntityField:
    """Parse entity field."""
    if isinstance(schema, str):
        field_type = schema
        field_schema = {"type": field_type}
    else:
        field_schema = schema
        field_type = field_schema.get("type", "string")

    description = field_schema.get("description", f"Field: {name}")
    required = field_schema.get("required", False)
    enum = field_schema.get("enum")

    return EntityField(
        name=name,
        type=field_type,
        description=description,
        required=required,
        enum=enum,
    )
