def app():
    from toolframe_demo_entry_register.page import render

    class FakeService:
        def call(self, method, params=None, *, timeout=30):
            del timeout
            assert method == "list_entries"
            assert params == {"limit": 1000}
            return {
                "entries": [
                    {
                        "id": 1,
                        "label": "first",
                        "value": 2.5,
                        "version": 1,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "count": 1,
                "limit": 1000,
                "nextAction": "Use the human dashboard for entry changes.",
            }

    class FakeServices:
        def require(self, name, *, version=1):
            assert name == "entry-register.entries"
            assert version == 1
            return FakeService()

    class FakeContext:
        services = FakeServices()

        def can(self, scope):
            return True

    render(FakeContext())


def app_conflict():
    import streamlit as st
    from toolframe_sdk import PluginError

    from toolframe_demo_entry_register.page import render

    class FakeService:
        def call(self, method, params=None, *, timeout=30):
            del timeout
            if method == "update_entry":
                st.session_state["submitted_version"] = params["expected_version"]
                raise PluginError(
                    "entry_register_version_conflict",
                    "Entry is missing or has changed. Refresh the entries and try again.",
                )
            return {
                "entries": [
                    {
                        "id": 1,
                        "label": "first",
                        "value": 2.5,
                        "version": st.session_state.get("latest_version", 1),
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "count": 1,
                "limit": 1000,
                "nextAction": "Use the human dashboard for entry changes.",
            }

    class FakeServices:
        def require(self, name, *, version=1):
            assert name == "entry-register.entries"
            assert version == 1
            return FakeService()

    class FakeContext:
        services = FakeServices()

        def can(self, scope):
            return True

    render(FakeContext())


def test_normal_page_metrics():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(app, default_timeout=10).run()
    assert not at.exception
    assert [(metric.label, metric.value) for metric in at.metric] == [
        ("Entries", "1"),
        ("Displayed total", "2.50"),
    ]


def test_page_rejects_unchanged_edit():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(app, default_timeout=10).run()
    next(button for button in at.button if button.label == "Save changes").click().run()
    assert [error.value for error in at.error] == [
        "Change the label or value before saving."
    ]


def test_page_shows_conflict_refresh_guidance():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(app_conflict, default_timeout=10).run()
    at.text_input[1].set_value("changed")
    next(button for button in at.button if button.label == "Save changes").click().run()
    assert len(at.error) == 1
    assert "Refresh the page and try again." in at.error[0].value


def test_edit_retains_version_shown_before_concurrent_update():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(app_conflict, default_timeout=10).run()
    at.session_state["latest_version"] = 2
    at.text_input[1].set_value("changed")
    next(button for button in at.button if button.label == "Save changes").click().run()
    assert at.session_state["submitted_version"] == 1
    assert "Refresh" in at.error[0].value


def test_read_only_scope_keeps_metrics_without_mutation_controls():
    import inspect

    from streamlit.testing.v1 import AppTest

    source = inspect.getsource(app).replace("return True", "return False")
    ui = AppTest.from_string(source + "\napp()\n").run()
    assert not ui.exception
    assert len(ui.metric) == 2
    assert not any(
        button.label in {"Add entry", "Save changes"} for button in ui.button
    )
