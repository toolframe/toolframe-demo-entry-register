# Toolframe Entry Register

This package is an ordinary business plugin example for Toolframe. It owns an
`entries` table through the host's scoped `toolframe.sql` service and
publishes the `entry-register.entries` service, a native dashboard page, one
read-only MCP list tool, and a usage document.

## Run the example

The native CLI installs this package and its providers as one template:

```sh
uvx toolframe --home ./my-app init --template entry-register
uvx toolframe --home ./my-app serve
```

In another terminal, run `uvx toolframe --home ./my-app open` for the local sign-in
link. No source checkout or manually assembled wheelhouse is required.

The business plugin is headless by default. Its runtime dependency is only
`toolframe-sdk>=0.4,<0.5`, so the service and MCP descriptor can be imported in a
clean environment without Streamlit. Install the optional UI extra when the
native page is needed:

```shell
uv pip install 'toolframe-demo-entry-register[ui]==0.4.1'
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

The application template uses SQLite 0.4.1 and Dashboard Auth 0.2.1. It starts
with public Dashboard and MCP access for the demo; first-password creation enables
protected Dashboard access with closed behavior during authentication outages.
MCP has its own policy and can be protected independently with a compatible MCP
auth provider. Use the access-password page to review each entrance before
adapting the demo for private records.

## Structured logging

The [business service](src/toolframe_demo_entry_register/service.py) uses the SDK's
`self.log` context logger. List operations log the row count and requested limit
at `INFO`. Create and update operations log the entry ID and version only after
the transaction commits. A stale or missing update logs `WARNING` with the entry
ID and expected version. Entry labels, values and SQL are excluded.

Use `extra` for event fields and `bind` for labels shared by related events:

```python
log = self.log.bind(entry_id=entry_id)
log.info("Entry updated", extra={"version": entry["version"]})
```

Toolframe adds plugin identity, the actual calling function/file/line, current
service and method, and active trace/span IDs. The
[Dashboard page](src/toolframe_demo_entry_register/page.py) uses `context.log`
at `DEBUG` for its displayed row count; the SDK adds page ownership automatically.
Health checks do not emit business events.

Core owns logging configuration. Local structured output is available without
OpenTelemetry. To export logs from a runtime with telemetry support, set these
variables before starting Core, replacing the collector address as needed:

```shell
export TOOLFRAME_TRACING_ENABLED=true
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export TOOLFRAME_LOGS_LEVEL=DEBUG
```

`DEBUG` includes Dashboard render events and automatic SDK call logs. `INFO`
omits those debug events. The plugin does not configure handlers or exporters
and does not use `print` for logging.

## Validation and releases

[CI and publishing](docs/ci.md) describes the isolated local validation command,
GitHub Actions triggers, pinned test dependencies, and the settings required for
manual PyPI publishing. Validation includes all plugin/page tests,
distribution metadata, packaged assets, and a fresh wheel installation.

For release validation and Trusted Publisher setup, see [releasing](docs/releasing.md).

## License

This example plugin and its application templates are licensed under the
[MIT License](LICENSE).

## PostgreSQL storage

Version 0.4 supports the PostgreSQL provider with an explicit migration variant
and `INSERT … RETURNING id` through SDK 0.4. Use SQLite provider 0.4 or PostgreSQL
provider 0.2 with the matching SDK. SQLite migration SQL and existing data are
preserved. Provision the `entry-register` store before enabling PostgreSQL.

For development hooks and contribution rules, see [Contributing](CONTRIBUTING.md).
