"""Serializable definition for the Entry Register plugin."""

from __future__ import annotations

from importlib.resources import files

from toolframe_sdk import (
    AuthorizationSpec,
    MethodSpec,
    Migration,
    PluginDefinition,
    Requirement,
    Resource,
    ScopeSpec,
    ServiceSpec,
    StoreSchema,
)

SERVICE_NAME = "entry-register.entries"
_PACKAGE = "toolframe_demo_entry_register"
_ROW_PROPERTIES = {
    "id": {"type": "integer", "minimum": 1},
    "label": {"type": "string"},
    "value": {"type": "number"},
    "version": {"type": "integer", "minimum": 1},
    "created_at": {"type": "string"},
    "updated_at": {"type": "string"},
}
_ROW_SCHEMA = {
    "type": "object",
    "properties": _ROW_PROPERTIES,
    "required": list(_ROW_PROPERTIES),
    "additionalProperties": False,
}
_LIST_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {"type": "array", "items": _ROW_SCHEMA},
        "count": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1},
        "nextAction": {"type": "string"},
    },
    "required": ["entries", "count", "limit", "nextAction"],
    "additionalProperties": False,
}
_LABEL_SCHEMA = {"type": "string"}  # The business service validates after trimming.
_VALUE_SCHEMA = {"type": "number"}


def _list_input(*, default: int, maximum: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": maximum,
                "default": default,
            }
        },
        "additionalProperties": False,
    }


_MUTATION_ROW_OUTPUT = _ROW_SCHEMA
_MIGRATION_SQL = (
    files(_PACKAGE).joinpath("migrations", "0001_init.sql").read_text(encoding="utf-8")
)


plugin = PluginDefinition(
    id="entry-register",
    factory="toolframe_demo_entry_register.service:EntryRegister",
    authorization=AuthorizationSpec(
        scopes={
            "entry-register.read": ScopeSpec(title="Read entries"),
            "entry-register.write": ScopeSpec(title="Create and edit entries"),
        }
    ),
    requires={
        "sql": Requirement(service="toolframe.sql", version=1),
    },
    services={
        SERVICE_NAME: ServiceSpec(
            methods={
                "list_entries": MethodSpec(
                    audience="business",
                    required_scopes=("entry-register.read",),
                    public_api=True,
                    description="List newest entries for the dashboard.",
                    input_schema=_list_input(default=1000, maximum=1000),
                    output_schema=_LIST_OUTPUT_SCHEMA,
                    read_only=True,
                ),
                "list_entries_tool": MethodSpec(
                    audience="business",
                    required_scopes=("entry-register.read",),
                    description="List newest entries through the read-only MCP tool.",
                    input_schema=_list_input(default=50, maximum=100),
                    output_schema=_LIST_OUTPUT_SCHEMA,
                    read_only=True,
                ),
                "create_entry": MethodSpec(
                    audience="business",
                    required_scopes=("entry-register.write",),
                    description="Create an entry.",
                    input_schema={
                        "type": "object",
                        "properties": {"label": _LABEL_SCHEMA, "value": _VALUE_SCHEMA},
                        "required": ["label", "value"],
                        "additionalProperties": False,
                    },
                    output_schema=_MUTATION_ROW_OUTPUT,
                ),
                "update_entry": MethodSpec(
                    audience="business",
                    required_scopes=("entry-register.write",),
                    description="Update an entry using optimistic concurrency.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "entry_id": {"type": "integer", "minimum": 1},
                            "expected_version": {
                                "type": "integer",
                                "minimum": 1,
                            },
                            "label": _LABEL_SCHEMA,
                            "value": _VALUE_SCHEMA,
                        },
                        "required": [
                            "entry_id",
                            "expected_version",
                            "label",
                            "value",
                        ],
                        "additionalProperties": False,
                    },
                    output_schema=_MUTATION_ROW_OUTPUT,
                ),
            }
        )
    },
    resources=(
        Resource(
            id="main",
            kind="dashboard.page",
            title="Entry Register",
            required_scopes=("entry-register.read",),
            data={
                "entrypoint": "toolframe_demo_entry_register.page:render",
                "order": 10,
            },
        ),
        Resource(
            id="list_entries",
            kind="mcp.tool",
            title="List entries",
            data={
                "service": SERVICE_NAME,
                "method": "list_entries_tool",
                "description": "List the newest Entry Register rows for read-only inspection.",
                "input_schema": _list_input(default=50, maximum=100),
                "output_schema": _LIST_OUTPUT_SCHEMA,
            },
        ),
        Resource(
            id="usage",
            kind="llms.document",
            title="Entry Register",
            data={"package": _PACKAGE, "path": "docs/usage.md"},
        ),
    ),
    store=StoreSchema(
        revision="v1",
        migrations=(
            Migration(
                revision="v1",
                sql=_MIGRATION_SQL,
                dialects={
                    "postgresql": files(_PACKAGE)
                    .joinpath("migrations", "0001_init.postgresql.sql")
                    .read_text()
                },
            ),
        ),
    ),
)


__all__ = ["SERVICE_NAME", "plugin"]
