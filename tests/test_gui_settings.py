# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock
import keyring

# We import the original class only to access its methods, not to create it
from gui_settings import SettingsWindow, SERVICE_NAME


# --- A NEW, ROBUST TESTING STRATEGY ---
# This class is a plain Python object that contains the logic from SettingsWindow
# but does NOT inherit from any GUI class. This isolates the logic completely.
class SettingsLogicContainer:
    # Copy the methods we want to test from the original class
    save_settings = SettingsWindow.save_settings
    load_settings = SettingsWindow.load_settings
    confirm_and_reset = SettingsWindow.confirm_and_reset


@pytest.fixture
def settings_logic(mocker):
    """
    This fixture provides an instance of our logic-only container class
    and mocks the external keyring library and UI widgets.
    """
    # Mock the external library functions
    mocker.patch("keyring.get_password", return_value=None)
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.delete_password")
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")

    # Create an instance of our simple, logic-only test class
    logic_container = SettingsLogicContainer()

    # Attach mock UI widgets to the instance for the methods to use
    logic_container.braze_api_key_entry = MagicMock()
    logic_container.transifex_api_token_entry = MagicMock()
    logic_container.braze_endpoint_entry = MagicMock()
    logic_container.transifex_org_slug_entry = MagicMock()
    logic_container.transifex_project_slug_entry = MagicMock()
    logic_container.backup_path_entry = MagicMock()
    logic_container.backup_checkbox = MagicMock()
    logic_container.log_level_menu = MagicMock()

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
    ]

    settings_logic.load_settings()

    settings_logic.braze_api_key_entry.insert.assert_called_with(0, "key")
    settings_logic.backup_checkbox.select.assert_called_once()


def test_save_settings(settings_logic):
    """Verify that values from the UI entries are correctly saved to keyring."""
    settings_logic.braze_api_key_entry.get.return_value = "saved_braze_key"
    settings_logic.backup_checkbox.get.return_value = 1

    settings_logic.save_settings()

    keyring.set_password.assert_any_call(SERVICE_NAME, "backup_enabled", "1")


def test_save_settings_backup_disabled(settings_logic):
    """Test saving when the backup checkbox is disabled."""
    settings_logic.backup_checkbox.get.return_value = 0

    settings_logic.save_settings()

    keyring.set_password.assert_any_call(SERVICE_NAME, "backup_enabled", "0")


def test_save_settings_deletes_empty_keys(settings_logic):
    """Verify that if a setting is empty, it is deleted from keyring."""
    settings_logic.braze_api_key_entry.get.return_value = ""

    settings_logic.save_settings()

    keyring.delete_password.assert_any_call(SERVICE_NAME, "braze_api_key")


def test_reset_settings(settings_logic):
    """Verify that resetting calls delete_password for all known keys."""
    # Add the load_settings method back as a mock to check if it's called
    settings_logic.load_settings = MagicMock()

    settings_logic.confirm_and_reset()

    assert keyring.delete_password.call_count == 8
    settings_logic.load_settings.assert_called_once()
