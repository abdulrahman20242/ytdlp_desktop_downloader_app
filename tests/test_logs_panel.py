from ui.logs_panel import LogsPanel


def test_append_log_inserts_message_into_textbox(tk_root):
    panel = LogsPanel(tk_root)
    panel.append_log("Starting download...")
    panel.append_log("Download completed.")

    content = panel._textbox.get("0.0", "end")
    assert "Starting download..." in content
    assert "Download completed." in content


def test_clear_removes_all_log_content(tk_root):
    panel = LogsPanel(tk_root)
    panel.append_log("Some logs to clear")
    panel._clear()

    content = panel._textbox.get("0.0", "end").strip()
    assert content == ""


def test_toggle_collapses_and_restores_textbox_and_button_text(tk_root):
    panel = LogsPanel(tk_root)
    assert panel._visible is True
    assert panel._toggle_btn.cget("text") == "▼ السجلات"

    # First toggle: collapses textbox
    panel._toggle()
    assert panel._visible is False
    assert panel._toggle_btn.cget("text") == "▲ السجلات"

    # Second toggle: restores textbox
    panel._toggle()
    assert panel._visible is True
    assert panel._toggle_btn.cget("text") == "▼ السجلات"


def test_set_natural_height_updates_geometry_and_propagate(tk_root):
    panel = LogsPanel(tk_root)
    panel.set_natural_height(120)
    assert panel.cget("height") > 0

    panel.set_natural_height(None)
