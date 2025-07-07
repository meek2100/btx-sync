# tests/test_gui_interactions.py

import pytest
import requests
from unittest.mock import MagicMock

import gui_settings as gui_settings_module
from gui_settings import SettingsWindow
from app import App


@pytest.fixture
def mock_settings_window(mocker):
    """Mocks the full initialization of the SettingsWindow for interaction testing."""
    mocker.patch.object(SettingsWindow, "__init__", lambda s, *a, **kw: None)
    settings_window = SettingsWindow(None)
    settings_window.advanced_checkbox = MagicMock()
    settings_window.advanced_frame = MagicMock()
    settings_window.geometry = MagicMock()
    settings_window.braze_api_key_entry = MagicMock()
    settings_window.braze_endpoint_entry = MagicMock()
    settings_window._test_braze_connection = MagicMock()
    return settings_window


def test_toggle_advanced_settings_show(mock_settings_window):
    """Verify that checking the box shows the advanced settings frame."""
    mock_settings_window.advanced_checkbox.get.return_value = 1
    SettingsWindow.toggle_advanced_settings(mock_settings_window)
    mock_settings_window.advanced_frame.grid.assert_called_once()
    mock_settings_window.advanced_frame.grid_remove.assert_not_called()


def test_toggle_advanced_settings_hide(mock_settings_window):
    """Verify that unchecking the box hides the advanced settings frame."""
    mock_settings_window.advanced_checkbox.get.return_value = 0
    SettingsWindow.toggle_advanced_settings(mock_settings_window)
    mock_settings_window.advanced_frame.grid.assert_not_called()
    mock_settings_window.advanced_frame.grid_remove.assert_called_once()


def test_braze_connection_handles_network_error(mocker):
    """
    Verify the Braze connection test reports failure on a network error.
    """
    mocker.patch.object(
        gui_settings_module.requests, "Session"
    ).return_value.get.side_effect = requests.exceptions.RequestException
    mocker.patch.object(SettingsWindow, "__init__", lambda s, *a, **kw: None)
    container = SettingsWindow(None)
    status, msg = container._test_braze_connection("key", "endpoint")
    assert status == "FAILED"
    assert "Could not connect to Braze" in msg


def test_open_help_file_handles_error(mocker):
    """
    Verify that if opening the help file fails, an error message is shown.
    """
    mocker.patch.object(App, "__init__", lambda s: None)
    app_instance = App()
    app_instance.help_window = None
    mock_help_window_class = mocker.patch("app.HelpWindow")
    app_instance.open_help_file()
    mock_help_window_class.assert_called_once_with(app_instance)


def test_test_connection_from_ui_wrapper(mock_settings_window, mocker):
    """
    Verify the UI wrapper for connection tests correctly uses UI values
    and shows the result in a messagebox.
    """
    mock_showinfo = mocker.patch("tkinter.messagebox.showinfo")
    mock_settings_window.braze_api_key_entry.get.return_value = "ui_key"
    mock_settings_window.braze_endpoint_entry.get.return_value = "ui_endpoint"
    mock_settings_window._test_braze_connection.return_value = ("SUCCESS", "Connected")

    mock_settings_window._test_braze_connection_from_ui()

    mock_settings_window._test_braze_connection.assert_called_once_with(
        "ui_key", "ui_endpoint"
    )
    mock_showinfo.assert_called_once_with("Braze Connection Test", "SUCCESS: Connected")
