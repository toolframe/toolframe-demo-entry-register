# Toolframe Entry Register

This package is an ordinary business plugin example for Toolframe. It owns an
`entries` table through the host's scoped `toolframe.storage.sql` service and
publishes the `entry-register.entries` service, a native dashboard page, one
read-only MCP list tool, and a usage document.

The business plugin is headless by default. Its runtime dependency is only
`toolframe-sdk==0.2.0`, so the service and MCP descriptor can be imported in a
clean environment without Streamlit. Install the optional UI extra when the
native page is needed:

```shell
uv pip install 'toolframe-demo-entry-register[ui]==0.2.1'
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
the `toolframe.storage.sql` binding intact.

The dashboard owns create and edit interactions. It shows at most 1,000 newest
rows and totals the rows it displays. The MCP resource is read-only, defaults
to 50 rows, and accepts limits through 100. Entry updates use compare-and-set:
the observed row version must still match, then the service increments it once.
Missing and stale rows return `entry_register_version_conflict`; refresh the
dashboard before retrying. Labels are trimmed and must be nonempty and no more
than 80 characters. Values are finite numbers and may be negative or zero.

The page and service declare `entry-register.read` and `entry-register.write`.
Read-only visitors see the list and totals without create/edit forms. Core checks
the same scopes on every new call. The MCP list tool, llms document and explicitly
published `POST /api/entry-register/entry-register.entries/list_entries` remain
public; create/update are not published at the public API entrance. The template
starts in public mode with local password management available.
