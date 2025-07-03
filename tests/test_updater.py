# tests/test_updater.py

import pytest
from unittest.mock import MagicMock

from app import check_for_updates


@pytest.fixture
def mock_tufup_client(mocker):
    """Mocks the tufup Client class."""
    mock_client_instance = MagicMock()
    mocker.patch("app.Client", return_value=mock_client_instance)
    return mock_client_instance


def test_update_found_and_applied(mock_tufup_client):
    """Verify that if an update is found, it is downloaded and installed."""
    mock_update = MagicMock(version="2.0.0")
    mock_tufup_client.check_for_updates.return_value = mock_update
    mock_tufup_client.download_and_apply_update.return_value = True
    logged_messages = []

    check_for_updates(logged_messages.append, {"LOG_LEVEL": "Normal"})

    full_log = "\n".join(logged_messages)
    assert "Update 2.0.0 found" in full_log

    # Update the assertion to include the new `confirm=False` argument
    mock_tufup_client.download_and_apply_update.assert_called_once_with(
        target=mock_update, confirm=False
    )


def test_no_update_found(mock_tufup_client):
    """Verify that if no update is found, the correct message is logged."""
    mock_tufup_client.check_for_updates.return_value = None
    logged_messages = []

    check_for_updates(logged_messages.append, {"LOG_LEVEL": "Normal"})

    assert "Application is up to date." in "\n".join(logged_messages)


def test_update_download_fails(mock_tufup_client):
    """Verify that if an update download fails, an error is logged."""
    mock_update = MagicMock(version="2.0.0")
    mock_tufup_client.check_for_updates.return_value = mock_update
    # Configure the correct method to return False for failure
    mock_tufup_client.download_and_apply_update.return_value = False
    logged_messages = []

    check_for_updates(logged_messages.append, {"LOG_LEVEL": "Normal"})

    assert "[ERROR] Update download or installation failed." in "\n".join(
        logged_messages
    )


def test_check_for_updates_uses_prerelease_channel(mock_tufup_client):
    """
    Verify that the check_for_updates function enables the pre-release channel.
    """
    logged_messages = []
    check_for_updates(logged_messages.append, {"LOG_LEVEL": "Normal"})
    mock_tufup_client.check_for_updates.assert_called_once_with(pre="a")
