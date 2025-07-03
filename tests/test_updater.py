# tests/test_updater.py

import pytest
from unittest.mock import MagicMock

# The function we are testing is now in `app`, not a separate file
from app import check_for_updates, App


@pytest.fixture
def mock_tufup_client(mocker):
    """Mocks the tufup Client class."""
    mock_client_instance = MagicMock()
    # Ensure any call to the Client constructor returns our mock instance
    mocker.patch("app.Client", return_value=mock_client_instance)
    return mock_client_instance


@pytest.fixture
def mock_app_instance(mocker):
    """
    Mocks the main App class to isolate the `check_for_updates` logic.
    We only need to mock the methods that `check_for_updates` calls directly.
    """
    # We don't need a full GUI app, just an object with the right methods
    app_instance = MagicMock(spec=App)
    # Configure the mock to return a valid config dictionary
    app_instance.get_current_config.return_value = {"LOG_LEVEL": "Normal"}
    return app_instance


def test_update_found_and_notification_shown(mock_tufup_client, mock_app_instance):
    """
    Verify that if an update is found, the app's notification method is called.
    """
    mock_update = MagicMock(version="2.0.0")
    mock_tufup_client.check_for_updates.return_value = mock_update

    # Call the function with our mocked app instance
    check_for_updates(mock_app_instance)

    # Verify that the log message was sent
    mock_app_instance.log_message.assert_any_call("Update 2.0.0 found.")

    # Verify that the notification method was called with the update info
    mock_app_instance.show_update_notification.assert_called_once_with(mock_update)


def test_no_update_found(mock_tufup_client, mock_app_instance):
    """Verify correct behavior when no update is found."""
    mock_tufup_client.check_for_updates.return_value = None

    check_for_updates(mock_app_instance)

    # Check that the log contains the "up to date" message
    mock_app_instance.log_message.assert_any_call("Application is up to date.")

    # Ensure the notification method was NOT called
    mock_app_instance.show_update_notification.assert_not_called()


def test_check_for_updates_uses_prerelease_channel(
    mock_tufup_client, mock_app_instance
):
    """
    Verify that the check_for_updates function enables the pre-release channel.
    """
    check_for_updates(mock_app_instance)
    mock_tufup_client.check_for_updates.assert_called_once_with(pre="a")
