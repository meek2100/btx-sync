# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock
import keyring

from gui_settings import SettingsWindow, SERVICE_NAME


class TestSettings(SettingsWindow):
    def setup_method(self):
        """This setup method replaces the __init__ to avoid pytest warnings."""
        self.braze_api_key_entry = MagicMock()
        self.transifex_api_token_entry = MagicMock()
        self.braze_endpoint_entry = MagicMock()
        self.transifex_org_slug_entry = MagicMock()
        self.transifex_project_slug_entry = MagicMock()
        self.backup_path_entry = MagicMock()
        self.backup_checkbox = MagicMock()
        self.log_level_menu = MagicMock()
        super().load_settings()


@pytest.fixture
def settings_logic(mocker):
    """
    This fixture provides an instance of our logic-only TestSettings class
    and mocks the external keyring library.
    """
    mocker.patch("keyring.get_password", return_value=None)
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.delete_password")
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")
    settings = TestSettings()
    settings.setup_method()
    return settings


def test_load_settings(settings_logic):
    """Verify that settings are correctly loaded from keyring."""
    settings_logic.backup_checkbox.reset_mock()
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
    settings_logic.backup_checkbox.get.return_value = 0  # Test backup disabled
    settings_logic.save_settings()
    keyring.set_password.assert_any_call(SERVICE_NAME, "backup_enabled", "0")


def test_save_settings_deletes_empty_keys(settings_logic):
    """Verify that if a setting is empty, it is deleted from keyring."""
    settings_logic.braze_api_key_entry.get.return_value = ""
    settings_logic.save_settings()
    keyring.delete_password.assert_any_call(SERVICE_NAME, "braze_api_key")


def test_reset_settings(settings_logic):
    """Verify that resetting calls delete_password for all known keys."""
    settings_logic.load_settings = MagicMock()
    settings_logic.confirm_and_reset()
    assert keyring.delete_password.call_count == 8
    settings_logic.load_settings.assert_called_once()
