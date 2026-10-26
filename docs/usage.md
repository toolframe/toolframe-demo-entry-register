# Entry Register behavior and composition

The business plugin is headless by default. Its runtime dependency is only
`toolframe-sdk>=0.4.0,<1`, so the service and MCP descriptor can be imported in a
clean environment without Streamlit. Install the optional UI extra when the
native page is needed:

```shell
uv pip install 'toolframe-demo-entry-register[ui]==0.4.2'
```

Build a clean wheel from this directory with:

```shell
uv build --no-sources --wheel
```

The wheel contains the declared migration, usage document, and composition
template. The host applies the migration during its store lifecycle; the
plugin does not open a database path or run runtime DDL.

Copy `src/toolframe_demo_entry_register/templates/entry-register.toml` or
`examples/toolframe.toml` into an application home as `toolframe.toml`, then
replace the documented application UUID and name. The template uses the
published distributions for storage, dashboard, MCP, llms.txt, auth, Dashboard
auth, and this
plugin. A local development composition can point the entry plugin at a
checkout with a source such as
`path:../toolframe-demo-entry-register`; keep the other provider bindings and
the `toolframe.sql` binding intact.

The dashboard owns create and edit interactions. It shows at most 1,000 newest
rows and totals the rows it displays. The MCP resource is read-only, defaults
to 50 rows, and accepts limits through 100. Entry updates use compare-and-set:
the observed row version must still match, then the service increments it once.
Missing and stale rows return `entry_register_version_conflict`; refresh the
dashboard before retrying. Labels are trimmed and must be nonempty and no more
than 80 characters. Values are finite numbers and may be negative or zero.

The page and service declare `entry-register.read` and `entry-register.write`.
Read-only visitors see the list and totals without create/edit forms. Core checks
the same scopes on every new call. The llms document and explicitly published
`POST /api/entry-register/entry-register.entries/list_entries` remain public;
create/update are not published at the public API entrance.

The application recipe declares compatible dependency ranges, with SQLite 0.4.1,
`toolframe-fastmcp` 0.3.1 and Dashboard Auth 0.2.1 as minimums. Core resolves the
latest compatible stable selection and saves exact sources and locks before the
first serve. Existing applications retain those versions until explicit update.
See the [recipe contract](../docs/recipe.md) for all bounds and offline behavior.

The demo starts with public Dashboard and MCP access; first-password creation enables
protected Dashboard access with closed behavior during authentication outages.
MCP has its own policy and can be protected independently with a compatible MCP
auth provider. Use the access-password page to review each entrance before
adapting the demo for private records.

## PostgreSQL storage

Version 0.4 supports the PostgreSQL provider with an explicit migration variant
and `INSERT … RETURNING id` through SDK 0.4. Use SQLite provider 0.4 or PostgreSQL
provider 0.2 with the matching SDK. SQLite migration SQL and existing data are
preserved. Provision the `entry-register` store before enabling PostgreSQL.
