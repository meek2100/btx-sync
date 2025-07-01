# tests/test_sync_logic.py

import pytest
import requests
import threading
from unittest.mock import MagicMock

import sync_logic
from logger import AppLogger


def no_op_callback(message):
    """A callback function that does nothing."""
    pass


@pytest.fixture
def mock_config(tmp_path):
    """Provides a mock config."""
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


def test_fetch_braze_list_pagination(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    page1 = {"templates": [{"email_template_id": "id1"}] * 100}
    page2 = {"templates": [{"email_template_id": "id2"}] * 50}
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())


def test_sync_main_stops_if_backup_fails(mocker, mock_session, mock_config):
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_session.get.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(
    mocker, mock_session, mock_config
):
    mock_config["BACKUP_ENABLED"] = True
    mocker.patch("sync_logic.perform_tmx_backup", side_effect=ValueError("test error"))
    logged_messages = []
    sync_logic.sync_logic_main(mock_config, logged_messages.append, threading.Event())
    assert any("An unexpected error occurred" in msg for msg in logged_messages)
    mock_session.get.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
    ],
)
def test_upload_skips_if_no_content(mocker, mock_session, mock_config, empty_content):
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    templates = [{"email_template_id": "e123", "template_name": "Empty"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: empty_content),
        MagicMock(status_code=404),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())


def test_backup_disabled(mocker, mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mock_session.get.return_value = MagicMock(json=lambda: {})
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_backup_func.assert_not_called()


def test_resource_name_no_update_needed(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Matching"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Test"}),
        MagicMock(
            status_code=200,
            json=lambda: {"data": {"attributes": {"name": "Matching"}}},
        ),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_session.patch.assert_not_called()


def test_perform_tmx_backup_success(mocker, mock_config):
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        json=lambda: {"data": {"id": "job1"}}
    )
    mock_tmx_session.get.return_value = MagicMock(content=b"<tmx></tmx>")
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("pathlib.Path.mkdir")
    logger = AppLogger(no_op_callback)
    sync_logic.perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )


def test_sync_handles_httperror(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    err = requests.exceptions.HTTPError("401 Unauthorized")
    err.response = MagicMock(status_code=401, json=lambda: {"error": "key"})
    mock_session.get.side_effect = err
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())


def test_sync_handles_connection_error(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = requests.exceptions.ConnectionError("NW down")
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())


def test_perform_tmx_backup_job_fails(mocker, mock_config):
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(json=lambda: {"data": {"id": "job1"}})
    mock_session.get.return_value = MagicMock(
        json=lambda: {"data": {"attributes": {"status": "failed"}}}
    )
    logger = AppLogger(no_op_callback)
    sync_logic.perform_tmx_backup(mock_config, mock_session, logger, threading.Event())


def test_perform_tmx_backup_timeout(mocker, mock_config):
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(json=lambda: {"data": {"id": "job1"}})
    mock_session.get.return_value = MagicMock(
        json=lambda: {"data": {"attributes": {"status": "pending"}}}
    )
    mocker.patch("time.sleep")
    mocker.patch("time.time", side_effect=[100, 501])
    logger = AppLogger(no_op_callback)
    sync_logic.perform_tmx_backup(mock_config, mock_session, logger, threading.Event())


def test_upload_source_content_success(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Test"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Hello"}),
        MagicMock(status_code=404),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
