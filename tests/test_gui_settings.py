# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock
import keyring  # --- FIX: Import the keyring library ---

# Import the class and constants we need to test
from gui_settings import SettingsWindow, SERVICE_NAME


# To solve the GUI initialization errors, we create a minimal, non-GUI version
# of the SettingsWindow. It contains only the logic we need to test.
class TestSettings(SettingsWindow):
    def __init__(self):
        # We override the __init__ method to *not* call the GUI toolkit's __init__.
        # Instead, we just create mock versions of the UI widgets our logic needs.
        self.braze_api_key_entry = MagicMock()
        self.transifex_api_token_entry = MagicMock()
        self.braze_endpoint_entry = MagicMock()
        self.transifex_org_slug_entry = MagicMock()
        self.transifex_project_slug_entry = MagicMock()
        self.backup_path_entry = MagicMock()
        self.backup_checkbox = MagicMock()
        self.log_level_menu = MagicMock()
        # We also call the real load_settings logic from the parent class.
        super().load_settings()


@pytest.fixture
def settings_logic(mocker):
    """
    This fixture provides an instance of our logic-only TestSettings class
    and mocks the external keyring library.
    """
    # Mock the external keyring library functions
    mocker.patch("keyring.get_password", return_value=None)
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.delete_password")
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")

    # Return an instance of our simple, logic-only test class
    return TestSettings()


def test_load_settings(settings_logic):
    """Verify that settings are correctly loaded from keyring."""
    # ARRANGE: Configure the mock keyring to return specific values
    keyring.get_password.side_effect = [
        "test_braze_key",
        "test_tx_token",
        "https://rest.braze.com",
        "my_org",
        "my_proj",
        "/my/backup/path",
        "Debug",
        "0",
    ]

    # ACT: Call the real load_settings method on our test object
    settings_logic.load_settings()

    # ASSERT
    settings_logic.braze_api_key_entry.insert.assert_called_with(0, "test_braze_key")
    settings_logic.log_level_menu.set.assert_called_with("Debug")
    settings_logic.backup_checkbox.deselect.assert_called_once()


def test_save_settings(settings_logic):
    """Verify that values from the UI entries are correctly saved to keyring."""
    settings_logic.braze_api_key_entry.get.return_value = "saved_braze_key"
    settings_logic.backup_checkbox.get.return_value = 1

    settings_logic.save_settings()

    keyring.set_password.assert_any_call(
        SERVICE_NAME, "braze_api_key", "saved_braze_key"
    )
    keyring.set_password.assert_any_call(SERVICE_NAME, "backup_enabled", "1")


def test_save_settings_deletes_empty_keys(settings_logic):
    """Verify that if a setting is empty, it is deleted from keyring."""
    settings_logic.braze_api_key_entry.get.return_value = "a_real_key"
    settings_logic.transifex_api_token_entry.get.return_value = ""

    settings_logic.save_settings()

    keyring.delete_password.assert_any_call(SERVICE_NAME, "transifex_api_token")


def test_reset_settings(settings_logic):
    """Verify that resetting calls delete_password for all known keys."""
    # Because our new __init__ calls load_settings, we reset the mock first
    settings_logic.load_settings = MagicMock()

    settings_logic.confirm_and_reset()

    assert keyring.delete_password.call_count == 8
    settings_logic.load_settings.assert_called_once()
