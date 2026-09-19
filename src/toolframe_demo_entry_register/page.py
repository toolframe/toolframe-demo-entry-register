"""Native Streamlit page for the Entry Register."""

from __future__ import annotations

from typing import Any

from toolframe_sdk import PageContext, PluginError


def _show_error(error: PluginError) -> None:
    import streamlit as st

    if error.code == "entry_register_version_conflict":
        st.error(f"{error.message} Refresh the page and try again.")
    else:
        st.error(error.message)


def _entry_label(entries: list[dict[str, Any]], entry_id: int) -> str:
    for entry in entries:
        if entry["id"] == entry_id:
            return f"{entry['id']}: {entry['label']}"
    return str(entry_id)


def render(context: PageContext) -> None:
    """Render the complete Entry Register dashboard through the SDK page facade."""

    import streamlit as st

    service = context.services.require("entry-register.entries", version=1)
    result = service.call("list_entries", {"limit": 1000})
    entries = result["entries"]
    total = sum(float(entry["value"]) for entry in entries)

    st.title("Entry Register")

    def refresh_editor():
        for key in list(st.session_state):
            if key.startswith("entry-register-edit-"):
                del st.session_state[key]

    st.button("Refresh entries", on_click=refresh_editor)
    count_column, total_column = st.columns(2)
    count_column.metric("Entries", len(entries))
    total_column.metric("Displayed total", f"{total:.2f}")
    if entries:
        st.dataframe(entries, hide_index=True, width="stretch")
    else:
        st.info("No entries yet. Create an entry below.")

    with st.form("entry-register-create"):
        st.subheader("Create entry")
        label = st.text_input("Label", key="entry-register-create-label")
        value = st.number_input("Value", key="entry-register-create-value", value=0.0)
        submitted = st.form_submit_button("Add entry")
        if submitted:
            try:
                service.call("create_entry", {"label": label, "value": value})
            except PluginError as error:
                _show_error(error)
            else:
                st.success("Entry created.")
                st.rerun()

    if not entries:
        return

    st.subheader("Edit entry")
    entry_ids = [entry["id"] for entry in entries]
    selected_id = st.selectbox(
        "Entry",
        entry_ids,
        format_func=lambda entry_id: _entry_label(entries, entry_id),
        key="entry-register-edit-selection",
    )
    selected = next(entry for entry in entries if entry["id"] == selected_id)
    snapshot_key = "entry-register-edit-snapshot"
    if (
        snapshot_key not in st.session_state
        or st.session_state[snapshot_key]["id"] != selected_id
    ):
        st.session_state[snapshot_key] = dict(selected)
    # Form submission reruns the script: retain the version actually shown to this
    # session, even if the new list query observes somebody else's newer write.
    selected = st.session_state[snapshot_key]
    widget_generation = f"{selected['id']}-{selected['version']}"
    with st.form("entry-register-edit"):
        label = st.text_input(
            "Label",
            value=selected["label"],
            key=f"entry-register-edit-label-{widget_generation}",
        )
        value = st.number_input(
            "Value",
            value=float(selected["value"]),
            key=f"entry-register-edit-value-{widget_generation}",
        )
        submitted = st.form_submit_button("Save changes")
        if submitted:
            if label.strip() == selected["label"] and value == selected["value"]:
                st.error("Change the label or value before saving.")
            else:
                try:
                    service.call(
                        "update_entry",
                        {
                            "entry_id": selected["id"],
                            "expected_version": selected["version"],
                            "label": label,
                            "value": value,
                        },
                    )
                except PluginError as error:
                    _show_error(error)
                else:
                    st.success("Entry updated.")
                    st.session_state.pop(snapshot_key, None)
                    st.rerun()


__all__ = ["render"]
