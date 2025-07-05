# tests/test_sync_logic_errors.py

import pytest
import requests
import json
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
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"message": "success"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    full_log = "".join(logged_messages)
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


def test_sync_handles_httperror_with_non_json_response(mock_session, mock_config):
    """
    Verify that an HTTPError with a non-JSON response is handled gracefully
    and logs the raw text content.
    """
    mock_config["BACKUP_ENABLED"] = False
    mock_response = MagicMock(status_code=500)
    mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mock_response.text = "<html><body><h1>Internal Server Error</h1></body></html>"
    err = requests.exceptions.HTTPError("Server Error")
    err.response = mock_response
    err.request = MagicMock()
    mock_session.get.side_effect = err
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    full_log = "".join(logged_messages)
    assert "Response Content: <html>" in full_log


def test_backup_handles_unexpected_content_type(mock_config, mocker):
    """
    Verify backup fails if the polling status check returns an unexpected
    content type.
    """
    # ARRANGE
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    # The GET call to check the job status returns an unexpected HTML response
    mock_tmx_session.get.return_value = MagicMock(
        status_code=200, headers={"Content-Type": "text/html"}
    )
    logger = AppLogger(no_op_callback)

    # ACT
    result = perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )

    # ASSERT
    assert result is False
