# tests/test_app.py

import pytest
from unittest.mock import MagicMock

# The class we want to test
from app import App


@pytest.fixture
def mock_app(mocker):
    """
    This fixture creates a mock instance of the main App class
    without running its full GUI initialization.
    """
    # Prevent the real __init__ from running and creating a GUI window
    mocker.patch.object(App, "__init__", lambda s: None)

    app_instance = App()

    # Add mock UI components that the methods expect to find
    app_instance.run_button = MagicMock()
    app_instance.status_label = MagicMock()

    # Mock the get_current_config method to control test inputs
    app_instance.get_current_config = MagicMock()

    return app_instance


def test_app_readiness_config_required(mock_app):
    """
    Verify the 'Run Sync' button is disabled if API keys are missing.
    """
    # ARRANGE
    # --- FIX: Configure the mock on the 'mock_app' instance ---
    # We mock the entire config dictionary that the method uses.
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": None,
        "TRANSIFEX_API_TOKEN": None,
        "LOG_LEVEL": "Normal",
    }

    # ACT
    mock_app.update_readiness_status()

    # ASSERT
    # Check that the button was disabled and the status label was updated
    mock_app.run_button.configure.assert_called_with(state="disabled")
    mock_app.status_label.configure.assert_called_with(text="Configuration required")


def test_app_readiness_is_ready(mock_app):
    """
    Verify the 'Run Sync' button is enabled when config is present.
    """
    # ARRANGE
    # --- FIX: Configure the mock on the 'mock_app' instance ---
    mock_app.get_current_config.return_value = {
        "BRAZE_API_KEY": "a_valid_key",
        "TRANSIFEX_API_TOKEN": "a_valid_token",
        "LOG_LEVEL": "Normal",
    }

    # ACT
    mock_app.update_readiness_status()

    # ASSERT
    mock_app.run_button.configure.assert_called_with(state="normal")
    mock_app.status_label.configure.assert_called_with(text="Ready")
