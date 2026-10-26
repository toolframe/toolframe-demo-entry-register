# Structured logging

The [business service](../src/toolframe_demo_entry_register/service.py) uses the SDK's
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
[Dashboard page](../src/toolframe_demo_entry_register/page.py) uses `context.log`
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
