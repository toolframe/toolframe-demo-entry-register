# Entry Register

Entry Register is a small ordinary business plugin. It owns one SQL store and
exposes the `entry-register.entries` service. The service accepts trimmed text
labels up to 80 characters and finite numeric values, including zero and
negative numbers.

The dashboard lists the newest 1,000 rows, displays their count and total, and
provides create and edit forms. The MCP resource is read-only and lists at most
100 rows with a default of 50. Use the dashboard for changes.

Updates use compare-and-set semantics. The caller sends the row's observed
`version`; a successful update increments that version once. A missing row or a
stale version returns `entry_register_version_conflict`, with guidance to
refresh before trying again.

The plugin receives the scoped `toolframe.sql` service from the host.
It never opens a database path itself, and its initial schema is applied by the
host's explicit migration lifecycle.
