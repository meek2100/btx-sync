# tests/test_updater.py

import pytest
from unittest.mock import MagicMock

# Import the function and config class we want to test
from app import check_for_updates


@pytest.fixture
def mock_pyupdater_client(mocker):
    """Mocks the PyUpdater Client class."""
    # Create a mock for the Client instance that will be returned
    mock_client_instance = MagicMock()

    # Patch the Client class so that when it's instantiated, it returns our mock instance
    mocker.patch("app.Client", return_value=mock_client_instance)

    return mock_client_instance


def test_update_found_and_applied(mock_pyupdater_client):
    """
    Verify that if an update is found, it is downloaded and the app restarts.
    """
    # ARRANGE
    # Configure the mock client to return a mock update object
    mock_update = MagicMock()
    mock_pyupdater_client.update_check.return_value = mock_update

    # Configure the mock update object to simulate a successful download
    mock_update.download.return_value = True

    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    # ACT
    check_for_updates(log_callback)

    # ASSERT
    # Verify the correct sequence of logs was generated
    assert "Checking for updates..." in logged_messages
    assert "Update found, downloading..." in logged_messages
    assert (
        "Update downloaded successfully. Restarting application..." in logged_messages
    )

    # Verify the key methods were called
    mock_pyupdater_client.update_check.assert_called_once()
    mock_update.download.assert_called_once()
    mock_update.extract_restart.assert_called_once()


def test_no_update_found(mock_pyupdater_client):
    """
    Verify that if no update is found, the correct message is logged.
    """
    # ARRANGE
    # Configure the mock client to return None, simulating no available update
    mock_pyupdater_client.update_check.return_value = None

    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    # ACT
    check_for_updates(log_callback)

    # ASSERT
    assert "Application is up to date." in logged_messages
    mock_pyupdater_client.update_check.assert_called_once()


def test_update_download_fails(mock_pyupdater_client):
    """
    Verify that if an update download fails, an error is logged.
    """
    # ARRANGE
    mock_update = MagicMock()
    mock_pyupdater_client.update_check.return_value = mock_update

    # Configure the mock update object to simulate a failed download
    mock_update.download.return_value = False

    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    # ACT
    check_for_updates(log_callback)

    # ASSERT
    assert "[ERROR] Update download failed." in logged_messages
    mock_update.download.assert_called_once()
    # Verify the application does NOT try to restart
    mock_update.extract_restart.assert_not_called()
