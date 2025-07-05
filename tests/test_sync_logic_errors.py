# tests/test_sync_logic_errors.py

import pytest
import requests
import threading
from unittest.mock import MagicMock

from sync_logic import sync_logic_main, perform_tmx_backup
from logger import AppLogger


def no_op_callback(message):
    pass


def mock_progress_callback(message):
    pass


@pytest.fixture
def mock_config(tmp_path):
    """Provides a standard mock config for tests in this file."""
    return {
        "BRAZE_API_KEY": "test_braze_key",
        "BRAZE_REST_ENDPOINT": "https://rest.mock.braze.com",
        "TRANSIFEX_API_TOKEN": "test_tx_token",
        "TRANSIFEX_ORGANIZATION_SLUG": "test_org",
        "TRANSIFEX_PROJECT_SLUG": "test_project",
        "BACKUP_ENABLED": True,
        "BACKUP_PATH": str(tmp_path),
        "LOG_LEVEL": "Debug",
    }


@pytest.fixture
def mock_session(mocker):
    """Mocks requests.Session and returns the mock instance."""
    mock_session_instance = MagicMock()
    mocker.patch("requests.Session", return_value=mock_session_instance)
    return mock_session_instance


def test_sync_robust_to_missing_templates_key(mock_session, mock_config):
    """
    Verify sync completes successfully when the 'templates' key is missing,
    as the production code uses .get() which is safe.
    """
    mock_config["BACKUP_ENABLED"] = False
    # This response is missing the 'templates' key. The second is for content_blocks.
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"message": "success"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    full_log = "".join(logged_messages)
    # The sync should finish normally, not log a fatal key error.
    assert "--- Sync Complete! ---" in full_log
    assert "Missing key" not in full_log


def test_sync_handles_generic_exception(mock_session, mock_config):
    """
    Verify the main sync function's final 'except' block catches
    unexpected errors.
    """
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = TypeError("An unexpected type error")
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    full_log = "".join(logged_messages)
    # FIX: The assertion must match the string representation of the exception.
    assert "An unexpected error occurred: An unexpected type error" in full_log


def test_backup_handles_request_exception_during_polling(mock_config):
    """
    Verify backup process fails gracefully if a network error occurs during
    status polling.
    """
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_tmx_session.get.side_effect = requests.exceptions.RequestException(
        "Network Down"
    )
    logger = AppLogger(no_op_callback)
    result = perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )
    assert result is False
