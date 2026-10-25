# Entry Register application recipe

`templates/entry-register.toml` in the wheel owns the application composition.
`examples/toolframe.toml` is the same recipe for operators who manage a composition
directly. Core's named `entry-register` initializer resolves the ranges below and
saves exact sources, artifact hashes and environment locks. Subsequent plugin
publications do not change an existing application's selection. Explicit
`plugin update ID` selects again within the retained recipe range; reload activates
the staged candidate without replacing the business owner's identity or store.

## Supported dependency lines

| Distribution | Recipe range | Contract used by this recipe |
| --- | --- | --- |
| `toolframe-sql-sqlite` | `>=0.4.1,<0.5` | `toolframe.sql` service version 1, retained stores and the SDK 0.4 storage interface. |
| `toolframe-streamlit-dashboard` | `>=0.5.1,<0.6` | Native SDK pages, scoped page calls and management presentation. |
| `toolframe-fastmcp` | `>=0.3.1,<0.4` | SDK-owned MCP tools and authenticated stateful Streamable HTTP, including bounded idle sessions. |
| `toolframe-llms-txt` | `>=0.3.0,<0.4` | Explicitly owned `llms.document` resources. |
| `toolframe-demo-entry-register` | `>=0.4.2,<0.5` | The `entries` store, versioned entry updates, page/tool declarations and this range-based recipe. |
| `toolframe-auth` | `>=0.3.1,<0.4` | Managed access credentials, sessions and the retained Auth store. |
| `toolframe-dashboard-auth` | `>=0.2.1,<0.3` | Password and access-policy pages, including closed behavior during provider outages. |

These are the recipe's supported provider lines. The minima include the fixes and
interfaces needed by the composition. The ceilings limit automatic selection to
those lines because the providers do not currently publish a compatibility promise
covering all of their own subsequent 0.x versions. Admitting another minor line
requires reviewing its configuration, service and resource contracts and verifying
the installed composition. Patch releases within a declared line do not require
another template edit.

The SDK's separate `>=0.4.0,<1` promise describes the SDK versions a plugin can use;
it does not widen the application recipe's requirement on that plugin. Likewise,
`toolframe-fastmcp` is the Toolframe provider distribution, while the third-party
`fastmcp` library is a dependency selected by that provider's own metadata. This
recipe does not install that library directly or constrain unrelated workers.

Core keeps backend environments isolated. The native page and Dashboard Auth use
their `ui` extras in the Dashboard cohort, where shared dependencies must agree.
Selection also checks Core's chosen SDK, Python and platform. An incompatible
newer release may be skipped for an older compatible release inside the range;
an unsatisfiable range is an initialization error.

Local TOML initialization preserves the supplied sources. Explicit pins and
local/Git/wheel sources remain explicit choices. For offline operation, provide
the selected wheels and all required dependency resources locally; missing
resources must fail without using sibling checkouts. Core documents the full
[initialization and update contract](https://github.com/toolframe/toolframe-core/blob/main/docs/application-templates.md).
