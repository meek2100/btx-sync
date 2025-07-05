# tests/test_app.py

import pytest
from unittest.mock import MagicMock

from app import App, cleanup_old_updates


@pytest.fixture
def mock_app(mocker):
    """Creates a mock instance of the App class for testing."""
    mocker.patch.object(App, "__init__", lambda s: None)
    app_instance = App()
    app_instance.cancel_event = MagicMock()
    app_instance.cancel_button = MagicMock()
    app_instance.run_button = MagicMock()
    app_instance.status_label = MagicMock()
    app_instance.log_box = MagicMock()
    app_instance.get_current_config = MagicMock()
    app_instance.log_message = MagicMock()
    app_instance.update_readiness_status = MagicMock()
    app_instance.settings_window = None
    app_instance.update_status_label = MagicMock()
    app_instance._update_status_label_gui = MagicMock()
    app_instance.force_update_check = MagicMock()
    # Add mocks for update-related attributes
    app_instance.new_update_info = MagicMock()
    app_instance.update_button = MagicMock()
    return app_instance


def test_app_readiness_config_required(mock_app):
    """Verify the 'Run Sync' button is disabled if API keys are missing."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": None,
        "TRANSIFEX_API_TOKEN": "token",
        "LOG_LEVEL": "Normal",
    }
    App.update_readiness_status(mock_app)
    mock_app.run_button.configure.assert_called_with(state="disabled")


def test_app_readiness_is_ready(mock_app):
    """Verify the 'Run Sync' button is enabled when config is present."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": "key",
        "TRANSIFEX_API_TOKEN": "token",
        "LOG_LEVEL": "Normal",
    }
    App.update_readiness_status(mock_app)
    mock_app.run_button.configure.assert_called_with(state="normal")


def test_app_readiness_shows_debug_mode(mock_app):
    """Verify the status label includes '(Debug)' when log level is Debug."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": "key",
        "TRANSIFEX_API_TOKEN": "token",
        "LOG_LEVEL": "Debug",
    }
    App.update_readiness_status(mock_app)
    mock_app.status_label.configure.assert_called_with(text="Ready (Debug)")


def test_start_sync_thread_starts_thread(mock_app, mocker):
    """Verify that start_sync_thread creates and starts a new thread."""
    mock_thread_class = mocker.patch("threading.Thread")
    mock_app.sync_thread_target = MagicMock()
    App.start_sync_thread(mock_app)
    mock_thread_class.assert_called_once_with(
        target=mock_app.sync_thread_target, daemon=True
    )
    mock_thread_class.return_value.start.assert_called_once()


def test_sync_thread_target_ui_updates(mock_app, mocker):
    """Verify that sync_thread_target updates UI and calls sync logic."""
    valid_config = {"BRAZE_API_KEY": "key", "TRANSIFEX_API_TOKEN": "token"}
    mock_app.get_current_config.return_value = valid_config
    mock_sync_logic = mocker.patch("app.sync_logic_main")
    App.sync_thread_target(mock_app)
    mock_app.run_button.pack_forget.assert_called_once()
    mock_app.cancel_button.pack.assert_called_once()
    mock_sync_logic.assert_called_once_with(
        valid_config,
        mock_app.log_message,
        mock_app.cancel_event,
        mock_app.update_status_label,
    )


def test_sync_thread_target_handles_no_config(mock_app, mocker):
    """Verify that sync_thread_target logs an error if config is missing."""
    invalid_config = {"BRAZE_API_KEY": "", "TRANSIFEX_API_TOKEN": ""}
    mock_app.get_current_config.return_value = invalid_config
    mock_sync_logic = mocker.patch("app.sync_logic_main")
    App.sync_thread_target(mock_app)
    mock_sync_logic.assert_not_called()
    mock_app.log_message.assert_any_call("--- CONFIGURATION ERROR ---")


def test_open_settings_focuses_existing_window(mock_app):
    """Verify that if the settings window exists, it is focused."""
    mock_app.settings_window = MagicMock()
    mock_app.settings_window.winfo_exists.return_value = True
    App.open_settings(mock_app)
    mock_app.settings_window.focus.assert_called_once()


def test_open_settings_creates_new_window(mock_app, mocker):
    """Verify that a new settings window is created if one does not exist."""
    mock_app.settings_window = None
    mock_app.wait_window = MagicMock()
    mock_settings_window_class = mocker.patch("app.SettingsWindow")
    App.open_settings(mock_app)
    mock_settings_window_class.assert_called_once_with(mock_app)
    mock_app.wait_window.assert_called_once()


def test_cleanup_old_updates(mocker):
    """Verify that leftover .old files from previous updates are deleted."""
    mock_install_dir = MagicMock()
    mock_file1 = MagicMock(name="old_file1.exe.old")
    mock_file2 = MagicMock(name="old_file2.dll.old")
    mock_install_dir.glob.return_value = [mock_file1, mock_file2]
    mocker.patch("app.Path").return_value.parent = mock_install_dir
    cleanup_old_updates()
    assert mock_file1.unlink.call_count == 1
    assert mock_file2.unlink.call_count == 1


def test_force_update_check_starts_thread(mock_app, mocker):
    """Verify that force_update_check starts the update check in a thread."""
    mock_thread_class = mocker.patch("threading.Thread")
    mock_check_for_updates = mocker.patch("app.check_for_updates")
    App.force_update_check(mock_app)
    mock_app.log_message.assert_called_once_with(
        "\n--- Manual update check initiated ---"
    )
    mock_thread_class.assert_called_once_with(
        target=mock_check_for_updates, args=(mock_app,), daemon=True
    )
    mock_thread_class.return_value.start.assert_called_once()


def test_threaded_apply_success(mock_app):
    """Verify the update process calls tufup download and install."""
    App.threaded_apply(mock_app)
    mock_app.new_update_info.download.assert_called_once()
    mock_app.new_update_info.install.assert_called_once_with(restart=True)
    mock_app.log_message.assert_any_call("Download complete. Preparing to install...")


def test_threaded_apply_failure(mock_app):
    """Verify UI is reset correctly if the update download fails."""
    # ARRANGE
    error_message = "Download failed"
    mock_app.new_update_info.download.side_effect = Exception(error_message)

    # ACT
    App.threaded_apply(mock_app)

    # ASSERT
    log_call = f"[ERROR] An unexpected error occurred during update: {error_message}"
    mock_app.log_message.assert_any_call(log_call)
    mock_app.update_button.configure.assert_called_with(
        state="normal", text="Install Now"
    )
    mock_app.new_update_info.install.assert_not_called()
