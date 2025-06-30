# tests/test_app.py

import pytest
from unittest.mock import MagicMock

from app import App


@pytest.fixture
def mock_app(mocker):
    """Creates a mock instance of the App class for testing."""
    mocker.patch.object(App, "__init__", lambda s: None)
    app_instance = App()
    app_instance.run_button = MagicMock()
    app_instance.status_label = MagicMock()
    app_instance.get_current_config = MagicMock()
    app_instance.sync_thread_target = MagicMock()
    return app_instance


def test_app_readiness_config_required(mock_app):
    """Verify the 'Run Sync' button is disabled if API keys are missing."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": None,
        "LOG_LEVEL": "Normal",
    }
    mock_app.update_readiness_status()
    mock_app.run_button.configure.assert_called_with(state="disabled")
    mock_app.status_label.configure.assert_called_with(text="Configuration required")


def test_app_readiness_is_ready(mock_app):
    """Verify the 'Run Sync' button is enabled when config is present."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": "key",
        "TRANSIFEX_API_TOKEN": "token",
        "LOG_LEVEL": "Normal",
    }
    mock_app.update_readiness_status()
    mock_app.run_button.configure.assert_called_with(state="normal")
    mock_app.status_label.configure.assert_called_with(text="Ready")


def test_app_readiness_shows_debug_mode(mock_app):
    """Verify the status label includes '(Debug)' when log level is set to Debug."""
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": "key",
        "TRANSIFEX_API_TOKEN": "token",
        "LOG_LEVEL": "Debug",
    }
    mock_app.update_readiness_status()
    mock_app.run_button.configure.assert_called_with(state="normal")
    mock_app.status_label.configure.assert_called_with(text="Ready (Debug)")


def test_start_sync_thread_starts_thread(mock_app, mocker):
    """Verify that start_sync_thread creates and starts a new thread."""
    # ARRANGE
    mock_thread = mocker.patch("threading.Thread")

    # ACT
    mock_app.start_sync_thread()

    # --- FIX: Assert for the actual call and attribute setting separately ---
    # 1. Assert that the Thread was created with the correct target
    mock_thread.assert_called_once_with(target=mock_app.sync_thread_target)

    # 2. Assert that the 'daemon' attribute was set on the created instance
    assert mock_thread.return_value.daemon is True

    # 3. Assert that the thread was started
    mock_thread.return_value.start.assert_called_once()
