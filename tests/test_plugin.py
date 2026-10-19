from __future__ import annotations

import time
from contextlib import contextmanager

import pytest
from toolframe_sdk import PluginError, RuntimeContext, call_context
from toolframe_sql_sqlite.plugin import ADMIN_SERVICE, SQL_SERVICE, SqliteProvider

from toolframe_demo_entry_register.plugin import plugin
from toolframe_demo_entry_register.service import EntryRegister


@contextmanager
def caller(
    *, owner="entry-register", generation="generation-1", root="root-1", admin=False
):
    token = call_context.set(
        {
            "application_id": "application-1",
            "owner": owner,
            "owner_generation": generation,
            "root_id": root,
            "management": admin,
            "deadline": time.time() + 30,
        }
    )
    try:
        yield
    finally:
        call_context.reset(token)


class StoragePeer:
    def __init__(self, storage):
        self.storage = storage

    async def request(self, method, params, timeout=None):
        del timeout
        if method != "service.call":
            raise AssertionError(method)
        alias = SQL_SERVICE if params["alias"] == "sql" else params["alias"]
        token = call_context.set(
            {
                "application_id": "application-1",
                "owner": "entry-register",
                "owner_generation": "generation-1",
                "root_id": "root-1",
                "deadline": time.time() + 30,
            }
        )
        try:
            return await self.storage.invoke(alias, params["method"], params["params"])
        finally:
            call_context.reset(token)


@pytest.fixture
async def service(tmp_path):
    storage = SqliteProvider(
        RuntimeContext(
            None,
            plugin_id="sql-sqlite",
            generation="storage-generation",
            state_directory=tmp_path,
        )
    )
    await storage.activate()
    with caller(admin=True):
        await storage.invoke(
            ADMIN_SERVICE,
            "ensure_store",
            {"owner": "entry-register", "schema": plugin.store.model_dump()},
        )
    context = RuntimeContext(
        StoragePeer(storage),
        plugin_id="entry-register",
        generation="generation-1",
    )
    business = EntryRegister(context)
    try:
        yield business
    finally:
        await storage.dispose()


def test_definition_has_assets_and_read_only_tool():
    assert plugin.id == "entry-register"
    assert plugin.factory == "toolframe_demo_entry_register.service:EntryRegister"
    assert plugin.store.revision == "v1"
    assert "CREATE TABLE entries" in plugin.store.migrations[0].sql
    resources = {
        (resource.kind, resource.id): resource for resource in plugin.resources
    }
    tool = resources[("mcp.tool", "list_entries")]
    assert tool.data["method"] == "list_entries_tool"
    assert tool.data["input_schema"]["properties"]["limit"]["default"] == 50
    assert tool.data["input_schema"]["properties"]["limit"]["maximum"] == 100
    assert all(
        method.read_only
        for method in plugin.services["entry-register.entries"].methods.values()
        if method is plugin.services["entry-register.entries"].methods["list_entries"]
        or method
        is plugin.services["entry-register.entries"].methods["list_entries_tool"]
    )


@pytest.mark.asyncio
async def test_create_list_and_compare_and_set(service):
    first = await service.create_entry("  first  ", 0)
    second = await service.create_entry("second", -2.5)
    assert first["label"] == "first"
    assert first["version"] == 1
    assert first["created_at"].endswith("Z")
    assert first["created_at"] == first["updated_at"]

    listed = await service.list_entries(limit=1)
    assert listed["entries"] == [second]
    assert listed["count"] == 1
    assert listed["limit"] == 1

    updated = await service.update_entry(second["id"], second["version"], "changed", 3)
    assert updated["version"] == 2
    assert updated["created_at"] == second["created_at"]
    assert updated["updated_at"].endswith("Z")
    with pytest.raises(PluginError) as conflict:
        await service.update_entry(second["id"], second["version"], "stale", 4)
    assert conflict.value.code == "entry_register_version_conflict"
    assert (await service.list_entries())["entries"][0]["label"] == "changed"


@pytest.mark.asyncio
async def test_validation_and_missing_conflict(service):
    for label in ("", "   ", "x" * 81, 1):
        with pytest.raises(PluginError) as error:
            await service.create_entry(label, 0)
        assert error.value.code == "entry_register_validation"
    for value in (True, float("inf"), float("nan"), "1"):
        with pytest.raises(PluginError) as error:
            await service.create_entry("valid", value)
        assert error.value.code == "entry_register_validation"
    with pytest.raises(PluginError) as error:
        await service.update_entry(999, 1, "valid", 0)
    assert error.value.code == "entry_register_version_conflict"


@pytest.mark.asyncio
async def test_business_logs_identify_functions_without_entry_contents(service, caplog):
    entry = await service.create_entry("private-label", 1234.56)
    await service.list_entries(limit=10)
    await service.list_entries_tool(limit=5)
    await service.update_entry(entry["id"], 1, "private-update", 6543.21)
    with pytest.raises(PluginError):
        await service.update_entry(entry["id"], 1, "private-stale", 9999.99)

    records = [r for r in caplog.records if r.name == "toolframe.plugin.entry-register"]
    assert [(r.getMessage(), r.funcName) for r in records] == [
        ("Entry created", "create_entry"),
        ("Entries listed", "list_entries"),
        ("Entries listed", "list_entries_tool"),
        ("Entry updated", "update_entry"),
        ("Entry update conflicted", "update_entry"),
    ]
    assert all(r.__dict__["toolframe.plugin.id"] == "entry-register" for r in records)
    assert all(
        r.__dict__["toolframe.plugin.generation"] == "generation-1" for r in records
    )
    assert (
        records[0].entry_id == records[3].entry_id == records[4].entry_id == entry["id"]
    )
    assert records[0].version == 1 and records[3].version == 2
    assert records[1].entry_count == records[2].entry_count == 1
    assert records[1].limit == 10 and records[2].limit == 5
    assert records[4].levelname == "WARNING" and records[4].expected_version == 1
    logged = repr([r.__dict__ for r in records])
    assert all(
        value not in logged for value in ("private-", "1234.56", "6543.21", "9999.99")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_commit_failure_does_not_log_success(
    service, caplog, monkeypatch, operation
):
    entry = await service.create_entry("before", 1)
    caplog.clear()
    request = service.context.peer.request

    async def fail_commit(method, params, timeout=None):
        if params["method"] == "commit":
            raise PluginError("storage_commit_failed", "Commit failed")
        return await request(method, params, timeout=timeout)

    monkeypatch.setattr(service.context.peer, "request", fail_commit)
    with pytest.raises(PluginError, match="Commit failed"):
        if operation == "create":
            await service.create_entry("new", 2)
        else:
            await service.update_entry(entry["id"], 1, "updated", 3)
    assert not any(
        r.getMessage() in {"Entry created", "Entry updated"} for r in caplog.records
    )
