# tests/test_gui_settings.py

import pytest
from unittest.mock import MagicMock

from pytest_mock import mocker

# The class we want to test
from gui_settings import SettingsWindow

# The service name constant used by the settings window
from config import SERVICE_NAME


# This is a pytest fixture. It's a reusable setup function that runs
# before each test that requests it. Its job is to create a clean,
# mocked environment for testing the SettingsWindow logic without a real GUI.
@pytest.fixture
def mock_settings_window(mocker):
    """
    Mocks all GUI components and external libraries (like keyring)
    to test the SettingsWindow logic in isolation.
    """
    # 1. Mock the entire keyring library to prevent tests from accessing
    #    the actual system keychain.
    mock_keyring = {
        "get_password": mocker.patch("keyring.get_password", return_value=None),
        "set_password": mocker.patch("keyring.set_password"),
        "delete_password": mocker.patch("keyring.delete_password"),
    }

    # 2. Mock the tkinter messagebox so that confirmation dialogs don't pop up
    #    during tests. We'll make it automatically return True for 'yes'.
    mocker.patch("tkinter.messagebox.askyesno", return_value=True)
    mocker.patch("tkinter.messagebox.showinfo")

    # 3. We need to create an instance of SettingsWindow, but we don't want
    #    to initialize its real GUI components (CTk). So, we patch the base
    #    class it inherits from.
    mocker.patch("customtkinter.CTkToplevel.__init__", return_value=None)
    mocker.patch("gui_settings.resource_path")  # Patch resource_path call for icon

    # 4. Create an instance of our class. Its __init__ method will run,
    #    creating all the mocked widgets.
    window = SettingsWindow()

    # 5. Since the widgets are created inside __init__, we need to replace them
    #    with mocks that we can control and inspect.
    window.braze_api_key_entry = MagicMock()
    window.transifex_api_token_entry = MagicMock()
    window.braze_endpoint_entry = MagicMock()
    window.transifex_org_slug_entry = MagicMock()
    window.transifex_project_slug_entry = MagicMock()
    window.backup_path_entry = MagicMock()
    window.backup_checkbox = MagicMock()
    window.log_level_menu = MagicMock()

    # Attach the mocked keyring to the window object for easy access in tests
    window.mock_keyring = mock_keyring

    return window


def test_load_settings(mock_settings_window):
    """
    Verify that settings are correctly loaded from keyring into the UI entries.
    """
    # ARRANGE: Configure the mock keyring to return specific values for each key.
    mock_get = mock_settings_window.mock_keyring["get_password"]
    mock_get.side_effect = [
        "test_braze_key",
        "test_tx_token",
        "https://rest.braze.com",
        "my_org",
        "my_proj",
        "/my/backup/path",
        "Debug",
        "0",  # Backup disabled
    ]

    # ACT: Call the method to load settings.
    mock_settings_window.load_settings()

    # ASSERT: Check that the `insert` method of each UI entry was called with
    # the correct value returned from our mocked keyring.
    mock_settings_window.braze_api_key_entry.insert.assert_called_with(
        0, "test_braze_key"
    )
    mock_settings_window.transifex_api_token_entry.insert.assert_called_with(
        0, "test_tx_token"
    )
    mock_settings_window.braze_endpoint_entry.insert.assert_called_with(
        0, "https://rest.braze.com"
    )
    mock_settings_window.transifex_org_slug_entry.insert.assert_called_with(0, "my_org")
    mock_settings_window.transifex_project_slug_entry.insert.assert_called_with(
        0, "my_proj"
    )
    mock_settings_window.backup_path_entry.insert.assert_called_with(
        0, "/my/backup/path"
    )
    mock_settings_window.log_level_menu.set.assert_called_with("Debug")
    mock_settings_window.backup_checkbox.deselect.assert_called_once()


def test_save_settings(mock_settings_window):
    """
    Verify that values from the UI entries are correctly saved to keyring.
    """
    # ARRANGE: Configure the `.get()` method of our mock UI widgets to return values.
    mock_settings_window.braze_api_key_entry.get.return_value = "saved_braze_key"
    mock_settings_window.transifex_api_token_entry.get.return_value = "saved_tx_token"
    mock_settings_window.backup_path_entry.get.return_value = "/new/path"
    mock_settings_window.backup_checkbox.get.return_value = 1  # Checked
    mock_settings_window.log_level_menu.get.return_value = "Normal"

    # ACT: Call the method to save settings.
    mock_settings_window.save_settings()

    # ASSERT: Check that `set_password` was called with the correct service name,
    # key, and the value we configured in the arrange step.
    mock_set = mock_settings_window.mock_keyring["set_password"]
    mock_set.assert_any_call(SERVICE_NAME, "braze_api_key", "saved_braze_key")
    mock_set.assert_any_call(SERVICE_NAME, "transifex_api_token", "saved_tx_token")
    mock_set.assert_any_call(SERVICE_NAME, "backup_path", "/new/path")
    mock_set.assert_any_call(SERVICE_NAME, "backup_enabled", "1")
    mock_set.assert_any_call(SERVICE_NAME, "log_level", "Normal")


def test_save_settings_deletes_empty_keys(mock_settings_window):
    """
    Verify that if a setting is empty, it is deleted from keyring instead of saved.
    """
    # ARRANGE: Provide a value for one key but an empty string for another.
    mock_settings_window.braze_api_key_entry.get.return_value = "a_real_key"
    mock_settings_window.transifex_api_token_entry.get.return_value = ""  # Empty

    # ACT: Call the method to save settings.
    mock_settings_window.save_settings()

    # ASSERT: Check that `set_password` was called for the real key, and
    # `delete_password` was called for the empty one.
    mock_set = mock_settings_window.mock_keyring["set_password"]
    mock_delete = mock_settings_window.mock_keyring["delete_password"]

    mock_set.assert_any_call(SERVICE_NAME, "braze_api_key", "a_real_key")
    mock_delete.assert_any_call(SERVICE_NAME, "transifex_api_token")


def test_reset_settings(mock_settings_window):
    """
    Verify that resetting calls delete_password for all known keys.
    """
    # ARRANGE: The fixture already mocked the confirmation box to return 'yes'.
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
    # Spy on the load_settings method to ensure it gets called after resetting.
    mocker.spy(mock_settings_window, "load_settings")

    # ACT: Call the reset function.
    mock_settings_window.confirm_and_reset()

    # ASSERT: Check that `delete_password` was called for every key.
    mock_delete = mock_settings_window.mock_keyring["delete_password"]
    assert mock_delete.call_count == len(keys_to_delete)
    for key in keys_to_delete:
        mock_delete.assert_any_call(SERVICE_NAME, key)

    # Assert that the UI is refreshed by calling load_settings again.
    assert mock_settings_window.load_settings.call_count == 1
