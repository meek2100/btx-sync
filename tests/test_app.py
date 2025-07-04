# tests/test_app.py

import pytest
from unittest.mock import MagicMock, call

from app import App


@pytest.fixture
def mock_app(mocker):
    """Creates a mock instance of the App class for testing."""
    mocker.patch.object(App, "__init__", lambda s: None)

    app_instance = App()

    app_instance.run_button = MagicMock()
    app_instance.status_label = MagicMock()
    app_instance.log_box = MagicMock()
    app_instance.get_current_config = MagicMock()
    app_instance.load_config_for_sync = MagicMock()
    app_instance.log_message = MagicMock()
    app_instance.update_readiness_status = MagicMock()
    app_instance.settings_window = None
    app_instance.wait_window = MagicMock()  # Mock the wait_window method

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
    """Verify the status label includes '(Debug)' when log level is set to Debug."""
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
    """Verify that sync_thread_target updates the UI and calls the main sync logic."""
    mock_app.load_config_for_sync.return_value = {"some": "config"}
    mock_sync_logic = mocker.patch("app.sync_logic_main")

    App.sync_thread_target(mock_app)

    expected_calls = [
        call(state="disabled", text="Syncing..."),
        call(state="normal", text="Run Sync"),
    ]
    mock_app.run_button.configure.assert_has_calls(expected_calls)
    mock_sync_logic.assert_called_once_with({"some": "config"}, mock_app.log_message)
    mock_app.update_readiness_status.assert_called_once()


def test_sync_thread_target_handles_no_config(mock_app, mocker):
    """Verify that sync_thread_target logs an error if config is missing."""
    mock_app.load_config_for_sync.return_value = None
    mock_sync_logic = mocker.patch("app.sync_logic_main")

    App.sync_thread_target(mock_app)

    mock_sync_logic.assert_not_called()
    mock_app.log_message.assert_any_call("--- CONFIGURATION ERROR ---")


def test_open_settings_focuses_existing_window(mock_app):
    """Verify that if the settings window already exists, it is focused."""
    mock_app.settings_window = MagicMock()
    mock_app.settings_window.winfo_exists.return_value = True

    App.open_settings(mock_app)

    mock_app.settings_window.focus.assert_called_once()


def test_open_settings_creates_new_window(mock_app, mocker):
    """Verify that a new settings window is created if one does not exist."""
    # ARRANGE
    mock_app.settings_window = None
    mock_settings_window_class = mocker.patch("app.SettingsWindow")

    # ACT
    App.open_settings(mock_app)

    # ASSERT
    # Check that a new SettingsWindow was created
    mock_settings_window_class.assert_called_once_with(mock_app)
    # Check that the window was made modal and waited on
    mock_settings_window_class.return_value.grab_set.assert_called_once()
    mock_app.wait_window.assert_called_once_with(
        mock_settings_window_class.return_value
    )
    # Check that the status was updated after the window closed
    mock_app.update_readiness_status.assert_called_once()
