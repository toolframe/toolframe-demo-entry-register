"""SQL-backed business service for the Entry Register."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from toolframe_sdk import Plugin, PluginError

SERVICE_NAME = "entry-register.entries"
NEXT_ACTION = "Use the human dashboard for entry changes."
_ROW_COLUMNS = "id, label, value, version, created_at, updated_at"


def _validation(message: str, *, field: str | None = None) -> PluginError:
    details = {"field": field} if field else {}
    return PluginError("entry_register_validation", message, details)


def _validate_label(label: Any) -> str:
    if not isinstance(label, str):
        raise _validation("Label must be text.", field="label")
    value = label.strip()
    if not value:
        raise _validation("Label cannot be empty.", field="label")
    if len(value) > 80:
        raise _validation("Label must be at most 80 characters.", field="label")
    return value


def _validate_value(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _validation("Value must be a finite number.", field="value")
    try:
        value = float(value)
    except ValueError, OverflowError:
        raise _validation("Value must be a finite number.", field="value") from None
    if not math.isfinite(value):
        raise _validation("Value must be a finite number.", field="value")
    return value


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _validation(f"{field} must be a positive integer.", field=field)
    return value


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _version_conflict(entry_id: int) -> PluginError:
    return PluginError(
        "entry_register_version_conflict",
        "Entry is missing or has changed. Refresh the entries and try again.",
        {"entry_id": entry_id, "guidance": "Refresh the entries and try again."},
    )


class EntryRegister(Plugin):
    """Expose Entry Register operations through the scoped SQL service."""

    async def list_entries(self, limit: int = 1000) -> dict[str, Any]:
        limit = _validate_positive_integer(limit, "limit")
        if limit > 1000:
            raise _validation("limit must be between 1 and 1000.", field="limit")
        rows = await self.context.storage().query(
            f"SELECT {_ROW_COLUMNS} FROM entries ORDER BY id DESC LIMIT ?", (limit,)
        )
        return {
            "entries": rows,
            "count": len(rows),
            "limit": limit,
            "nextAction": NEXT_ACTION,
        }

    async def list_entries_tool(self, limit: int = 50) -> dict[str, Any]:
        limit = _validate_positive_integer(limit, "limit")
        if limit > 100:
            raise _validation("limit must be between 1 and 100.", field="limit")
        rows = await self.context.storage().query(
            f"SELECT {_ROW_COLUMNS} FROM entries ORDER BY id DESC LIMIT ?", (limit,)
        )
        return {
            "entries": rows,
            "count": len(rows),
            "limit": limit,
            "nextAction": NEXT_ACTION,
        }

    async def create_entry(self, label: str, value: float) -> dict[str, Any]:
        label = _validate_label(label)
        value = _validate_value(value)
        created_at = _timestamp()
        storage = self.context.storage()
        async with storage.transaction() as transaction:
            result = await transaction.execute_returning(
                "INSERT INTO entries "
                "(label, value, version, created_at, updated_at) "
                "VALUES (?, ?, 1, ?, ?) RETURNING id",
                (label, value, created_at, created_at),
            )
            returned = result.get("rows", [])
            entry_id = returned[0].get("id") if len(returned) == 1 else None
            if not isinstance(entry_id, int) or entry_id < 1:
                raise PluginError(
                    "entry_register_storage",
                    "Storage did not return the created entry identity.",
                )
            rows = await transaction.query(
                f"SELECT {_ROW_COLUMNS} FROM entries WHERE id = ?", (entry_id,)
            )
            if not rows:
                raise PluginError(
                    "entry_register_storage",
                    "Created entry could not be read back from storage.",
                )
            return rows[0]

    async def update_entry(
        self,
        entry_id: int,
        expected_version: int,
        label: str,
        value: float,
    ) -> dict[str, Any]:
        entry_id = _validate_positive_integer(entry_id, "entry_id")
        expected_version = _validate_positive_integer(
            expected_version, "expected_version"
        )
        label = _validate_label(label)
        value = _validate_value(value)
        updated_at = _timestamp()
        storage = self.context.storage()
        async with storage.transaction() as transaction:
            result = await transaction.execute(
                "UPDATE entries SET label = ?, value = ?, version = version + 1, "
                "updated_at = ? WHERE id = ? AND version = ?",
                (label, value, updated_at, entry_id, expected_version),
            )
            if result.get("rowcount") != 1:
                raise _version_conflict(entry_id)
            rows = await transaction.query(
                f"SELECT {_ROW_COLUMNS} FROM entries WHERE id = ?", (entry_id,)
            )
            if not rows:
                raise _version_conflict(entry_id)
            return rows[0]

    async def health(self) -> dict[str, str]:
        await self.context.storage().query(
            "SELECT id FROM entries ORDER BY id DESC LIMIT 1"
        )
        return {"runtime": "ready", "business": "ready"}

    async def invoke(self, service: str, method: str, params: dict) -> Any:
        if service != SERVICE_NAME:
            raise PluginError("method_not_found", f"Unknown method {service}/{method}")
        if method == "list_entries":
            return await self.list_entries(**params)
        if method == "list_entries_tool":
            return await self.list_entries_tool(**params)
        if method == "create_entry":
            return await self.create_entry(**params)
        if method == "update_entry":
            return await self.update_entry(**params)
        raise PluginError("method_not_found", f"Unknown method {service}/{method}")


__all__ = ["SERVICE_NAME", "EntryRegister"]
