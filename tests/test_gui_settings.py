# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock
import keyring
import requests

from gui_settings import SettingsWindow, SERVICE_NAME


class SettingsLogicContainer:
    save_settings = SettingsWindow.save_settings
    load_settings = SettingsWindow.load_settings
    confirm_and_reset = SettingsWindow.confirm_and_reset
    browse_directory = SettingsWindow.browse_directory
    test_connections = SettingsWindow.test_connections
    _test_braze_connection = SettingsWindow._test_braze_connection
    _test_transifex_connection = SettingsWindow._test_transifex_connection


@pytest.fixture
def settings_logic(mocker):
    """
    This fixture provides an instance of our logic-only container class
    and mocks the external keyring library and UI widgets.
    """
    mocker.patch("keyring.get_password", return_value=None)
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.delete_password")
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")
    mocker.patch("tkinter.filedialog.askdirectory")

    logic_container = SettingsLogicContainer()

    logic_container.braze_api_key_entry = MagicMock()
    logic_container.transifex_api_token_entry = MagicMock()
    logic_container.braze_endpoint_entry = MagicMock()
    logic_container.transifex_org_slug_entry = MagicMock()
    logic_container.transifex_project_slug_entry = MagicMock()
    logic_container.backup_path_entry = MagicMock()
    logic_container.backup_checkbox = MagicMock()
    logic_container.log_level_menu = MagicMock()
    logic_container.update_checkbox = MagicMock()

    return logic_container


def test_load_settings(settings_logic):
    """Verify that settings are correctly loaded from keyring."""
    keyring.get_password.side_effect = [
        "key",
        "token",
        "endpoint",
        "org",
        "proj",
        "/path",
        "Normal",
        "1",
        "1",
    ]
    settings_logic.load_settings()
    settings_logic.braze_api_key_entry.insert.assert_called_with(0, "key")
    settings_logic.backup_checkbox.select.assert_called_once()
    settings_logic.update_checkbox.select.assert_called_once()


def test_load_settings_with_disabled_options(settings_logic):
    """Verify that disabled settings are correctly loaded."""
    keyring.get_password.side_effect = ["", "", "", "", "", "", "Debug", "0", "0"]
    settings_logic.load_settings()
    settings_logic.backup_checkbox.deselect.assert_called_once()
    settings_logic.update_checkbox.deselect.assert_called_once()
    settings_logic.log_level_menu.set.assert_called_with("Debug")


def test_save_settings(settings_logic):
    """Verify that values from the UI entries are correctly saved to keyring."""
    settings_logic.braze_api_key_entry.get.return_value = "saved_braze_key"
    settings_logic.backup_checkbox.get.return_value = 1
    settings_logic.update_checkbox.get.return_value = 1
    settings_logic.save_settings()
    keyring.set_password.assert_any_call(SERVICE_NAME, "backup_enabled", "1")
    keyring.set_password.assert_any_call(SERVICE_NAME, "auto_update_enabled", "1")


def test_save_settings_deletes_empty_keys(settings_logic):
    """Verify that if a setting is empty, it is deleted from keyring."""
    settings_logic.braze_api_key_entry.get.return_value = ""
    settings_logic.save_settings()
    keyring.delete_password.assert_any_call(SERVICE_NAME, "braze_api_key")


def test_reset_settings(settings_logic):
    """Verify that resetting calls delete_password for all known keys."""
    settings_logic.load_settings = MagicMock()
    settings_logic.confirm_and_reset()
    assert keyring.delete_password.call_count == 9
    settings_logic.load_settings.assert_called_once()


def test_browse_directory(settings_logic, mocker):
    """Verify that Browse for a directory updates the entry field."""
    # The variable assignment is removed from the next line
    mocker.patch("tkinter.filedialog.askdirectory", return_value="/new/test/path")

    settings_logic.browse_directory()

    settings_logic.backup_path_entry.delete.assert_called_once_with(0, "end")
    settings_logic.backup_path_entry.insert.assert_called_once_with(0, "/new/test/path")


def test_confirm_and_reset_cancelled(settings_logic, mocker):
    """Verify that if user cancels the reset, no keys are deleted."""
    mocker.patch(
        "tkinter.messagebox.askyesno", return_value=False
    )  # Simulate user clicking "No"
    settings_logic.confirm_and_reset()
    keyring.delete_password.assert_not_called()


def test_test_braze_connection_success(settings_logic, mocker):
    """Verify that a successful Braze connection returns a SUCCESS status."""
    mocker.patch("requests.Session.get").return_value = MagicMock(
        status_code=200, raise_for_status=lambda: None
    )
    status, msg = settings_logic._test_braze_connection("key", "endpoint")
    assert status == "SUCCESS"


def test_test_braze_connection_failure(settings_logic, mocker):
    """Verify that a failed Braze connection returns a FAILED status."""
    mock_response = MagicMock(status_code=401)
    mocker.patch("requests.Session.get").side_effect = requests.exceptions.HTTPError(
        response=mock_response
    )
    status, msg = settings_logic._test_braze_connection("key", "endpoint")
    assert status == "FAILED"


def test_test_transifex_connection_success(settings_logic, mocker):
    """Verify that a successful Transifex connection returns a SUCCESS status."""
    mocker.patch("requests.Session.get").return_value = MagicMock(
        status_code=200, raise_for_status=lambda: None
    )
    status, msg = settings_logic._test_transifex_connection("token", "org", "proj")
    assert status == "SUCCESS"


def test_test_transifex_connection_failure(settings_logic, mocker):
    """Verify that a failed Transifex connection returns a FAILED status."""
    mock_response = MagicMock(status_code=404)
    mocker.patch("requests.Session.get").side_effect = requests.exceptions.HTTPError(
        response=mock_response
    )
    status, msg = settings_logic._test_transifex_connection("token", "org", "proj")
    assert status == "FAILED"
