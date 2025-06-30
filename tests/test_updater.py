# tests/test_updater.py

import pytest
from unittest.mock import MagicMock

# Import the function and config class we want to test
from app import check_for_updates


@pytest.fixture
def mock_pyupdater_client(mocker):
    """Mocks the PyUpdater Client class."""
    mock_client_instance = MagicMock()
    mocker.patch("app.Client", return_value=mock_client_instance)
    return mock_client_instance


def test_update_found_and_applied(mock_pyupdater_client):
    """Verify that if an update is found, it is downloaded and the app restarts."""
    mock_update = MagicMock(version="2.0.0")
    mock_pyupdater_client.update_check.return_value = mock_update
    mock_update.download.return_value = True
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    check_for_updates(log_callback)

    full_log = "\n".join(logged_messages)
    assert "Update 2.0.0 found, downloading..." in full_log
    mock_update.extract_restart.assert_called_once()


def test_no_update_found(mock_pyupdater_client):
    """Verify that if no update is found, the correct message is logged."""
    mock_pyupdater_client.update_check.return_value = None
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    check_for_updates(log_callback)

    assert "Application is up to date." in "\n".join(logged_messages)


def test_update_download_fails(mock_pyupdater_client):
    """Verify that if an update download fails, an error is logged."""
    mock_update = MagicMock(version="2.0.0")
    mock_pyupdater_client.update_check.return_value = mock_update
    mock_update.download.return_value = False
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    check_for_updates(log_callback)

    assert "[ERROR] Update download failed." in "\n".join(logged_messages)
    mock_update.extract_restart.assert_not_called()
