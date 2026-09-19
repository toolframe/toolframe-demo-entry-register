from __future__ import annotations

import time
from contextlib import contextmanager

import pytest
from toolframe_sdk import PluginError, RuntimeContext, call_context
from toolframe_storage_sqlite.plugin import ADMIN_SERVICE, SQL_SERVICE, SqliteProvider

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
        alias = SQL_SERVICE if params["alias"] == "storage" else params["alias"]
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
            plugin_id="storage-sqlite",
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
