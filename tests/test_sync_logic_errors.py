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


def mock_progress_callback(current, total):
    pass


def mock_status_callback(message):
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
    mock_config["BACKUP_ENABLED"] = False
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"message": "success"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    logged_messages = []
    sync_logic_main(
        mock_config,
        logged_messages.append,
        threading.Event(),
        mock_progress_callback,
        mock_status_callback,
    )
    full_log = "".join(logged_messages)
    assert "--- Sync Complete! ---" in full_log
    assert "Missing key" not in full_log


def test_sync_handles_generic_exception(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    mock_session.request.side_effect = TypeError("An unexpected type error")
    logged_messages = []
    sync_logic_main(
        mock_config,
        logged_messages.append,
        threading.Event(),
        mock_progress_callback,
        mock_status_callback,
    )
    full_log = "".join(logged_messages)
    assert "An unexpected error occurred: An unexpected type error" in full_log


def test_backup_handles_request_exception_during_polling(mock_config):
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
    mock_config["BACKUP_ENABLED"] = False
    mock_response = MagicMock(status_code=500, text="<HTML>Error</HTML>")
    mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    err = requests.exceptions.HTTPError(response=mock_response)
    mock_session.request.side_effect = err
    logged_messages = []
    sync_logic_main(
        mock_config,
        logged_messages.append,
        threading.Event(),
        mock_progress_callback,
        mock_status_callback,
    )
    full_log = "".join(logged_messages)
    assert "Response Content: <HTML>Error</HTML>" in full_log


def test_backup_handles_unexpected_content_type(mock_config, mocker):
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_tmx_session.get.return_value = MagicMock(
        status_code=200, headers={"Content-Type": "text/html"}
    )
    logger = AppLogger(no_op_callback)
    result = perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )
    assert result is False


def test_backup_skips_if_path_not_defined(mock_config):
    mock_config["BACKUP_PATH"] = ""
    logged_messages = []
    logger = AppLogger(logged_messages.append)
    result = perform_tmx_backup(mock_config, MagicMock(), logger, threading.Event())
    assert result is True
    assert any("Backup path is not defined" in msg for msg in logged_messages)


def test_sync_skips_items_with_missing_ids(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [
        {"template_name": "Missing ID"},
        {"email_template_id": "id_123", "template_name": "Valid Template"},
    ]
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
        MagicMock(status_code=200, json=lambda: {"subject": "Test"}),
    ]
    mock_session.get.return_value = MagicMock(status_code=404)
    sync_logic_main(
        mock_config,
        no_op_callback,
        threading.Event(),
        mock_progress_callback,
        mock_status_callback,
    )
    detail_call_args = [
        c.args[1] for c in mock_session.request.call_args_list if "info" in c.args[1]
    ]
    assert len(detail_call_args) == 1
    assert "email_template_id=id_123" in detail_call_args[0]


def test_rate_limiting_is_handled(mock_session, mock_config, mocker):
    """
    Verify the client waits and retries when a 429 status code is received.
    """
    mock_config["BACKUP_ENABLED"] = False
    mock_sleep = mocker.patch("time.sleep")

    mock_response_429 = MagicMock(status_code=429, headers={"Retry-After": "5"})
    error_429 = requests.exceptions.HTTPError(response=mock_response_429)

    mock_success_templates = MagicMock(status_code=200, json=lambda: {"templates": []})
    mock_success_blocks = MagicMock(
        status_code=200, json=lambda: {"content_blocks": []}
    )

    mock_session.request.side_effect = [
        error_429,
        mock_success_templates,
        mock_success_blocks,
    ]

    sync_logic_main(
        mock_config,
        no_op_callback,
        threading.Event(),
        mock_progress_callback,
        mock_status_callback,
    )

    mock_sleep.assert_called_once_with(5)
    assert mock_session.request.call_count == 3
