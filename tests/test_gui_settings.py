# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock

# The class we want to test
from gui_settings import SettingsWindow

# The service name constant used by the settings window
from config import SERVICE_NAME


@pytest.fixture
def mock_settings_window(mocker):
    """
    Mocks all GUI components and external libraries (like keyring)
    to test the SettingsWindow logic in isolation.
    """
    # 1. Mock the entire keyring library
    mock_keyring = {
        "get_password": mocker.patch("keyring.get_password", return_value=None),
        "set_password": mocker.patch("keyring.set_password"),
        "delete_password": mocker.patch("keyring.delete_password"),
    }

    # 2. Mock tkinter popups
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")

    # 3. Patch the base class __init__ to prevent a real window from being created
    mocker.patch("customtkinter.CTkToplevel.__init__", return_value=None)
    mocker.patch("gui_settings.resource_path")

    # 4. Create an instance of our class
    window = SettingsWindow()

    # --- START OF FIX ---
    # 5. The patch in step 3 prevents the underlying tk object from being created.
    #    We add a mock `tk` object to the instance to prevent AttributeErrors
    #    when methods like `self.title()` are called in the real __init__.
    window.tk = MagicMock()
    # --- END OF FIX ---

    # 6. Replace the widgets with mocks that we can control and inspect.
    window.braze_api_key_entry = MagicMock()
    window.transifex_api_token_entry = MagicMock()
    window.braze_endpoint_entry = MagicMock()
    window.transifex_org_slug_entry = MagicMock()
    window.transifex_project_slug_entry = MagicMock()
    window.backup_path_entry = MagicMock()
    window.backup_checkbox = MagicMock()
    window.log_level_menu = MagicMock()

    # Attach the mocked keyring for easy access in tests
    window.mock_keyring = mock_keyring

    return window


def test_load_settings(mock_settings_window):
    """
    Verify that settings are correctly loaded from keyring into the UI entries.
    """
    mock_get = mock_settings_window.mock_keyring["get_password"]
    mock_get.side_effect = [
        "test_braze_key",
        "test_tx_token",
        "https://rest.braze.com",
        "my_org",
        "my_proj",
        "/my/backup/path",
        "Debug",
        "0",
    ]
    mock_settings_window.load_settings()
    mock_settings_window.braze_api_key_entry.insert.assert_called_with(
        0, "test_braze_key"
    )
    mock_settings_window.transifex_api_token_entry.insert.assert_called_with(
        0, "test_tx_token"
    )
    mock_settings_window.log_level_menu.set.assert_called_with("Debug")
    mock_settings_window.backup_checkbox.deselect.assert_called_once()


def test_save_settings(mock_settings_window):
    """
    Verify that values from the UI entries are correctly saved to keyring.
    """
    mock_settings_window.braze_api_key_entry.get.return_value = "saved_braze_key"
    mock_settings_window.transifex_api_token_entry.get.return_value = "saved_tx_token"
    mock_settings_window.backup_checkbox.get.return_value = 1
    mock_settings_window.log_level_menu.get.return_value = "Normal"

    mock_settings_window.save_settings()

    mock_set = mock_settings_window.mock_keyring["set_password"]
    mock_set.assert_any_call(SERVICE_NAME, "braze_api_key", "saved_braze_key")
    mock_set.assert_any_call(SERVICE_NAME, "backup_enabled", "1")


def test_save_settings_deletes_empty_keys(mock_settings_window):
    """
    Verify that if a setting is empty, it is deleted from keyring instead of saved.
    """
    mock_settings_window.braze_api_key_entry.get.return_value = "a_real_key"
    mock_settings_window.transifex_api_token_entry.get.return_value = ""

    mock_settings_window.save_settings()

    mock_set = mock_settings_window.mock_keyring["set_password"]
    mock_delete = mock_settings_window.mock_keyring["delete_password"]
    mock_set.assert_any_call(SERVICE_NAME, "braze_api_key", "a_real_key")
    mock_delete.assert_any_call(SERVICE_NAME, "transifex_api_token")


def test_reset_settings(mock_settings_window, mocker):
    """
    Verify that resetting calls delete_password for all known keys.
    """
    keys_to_delete = [
        "braze_api_key",
        "transifex_api_token",
        "braze_endpoint",
        "transifex_org",
        "transifex_project",
        "backup_path",
        "log_level",
        "backup_enabled",
    ]
    mocker.spy(mock_settings_window, "load_settings")

    mock_settings_window.confirm_and_reset()

    mock_delete = mock_settings_window.mock_keyring["delete_password"]
    assert mock_delete.call_count == len(keys_to_delete)
    for key in keys_to_delete:
        mock_delete.assert_any_call(SERVICE_NAME, key)
    assert mock_settings_window.load_settings.call_count == 1
