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
    # ARRANGE
    mock_thread_class = mocker.patch("threading.Thread")
    mock_app.sync_thread_target = MagicMock()

    # ACT
    App.start_sync_thread(mock_app)

    # --- FIX: Assert that the Thread was instantiated with both target and daemon=True ---
    mock_thread_class.assert_called_once_with(
        target=mock_app.sync_thread_target, daemon=True
    )

    # Assert that the start method was called on the instance
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
