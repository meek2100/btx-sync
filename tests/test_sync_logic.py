# tests/test_sync_logic.py

import pytest
import requests
import json
import threading
from unittest.mock import MagicMock, call

from sync_logic import sync_logic_main, perform_tmx_backup
from logger import AppLogger


@pytest.fixture(autouse=True)
def mock_time_sleep(mocker):
    mocker.patch("time.sleep")


def no_op_callback(message):
    pass


def mock_progress_callback(message):
    pass


@pytest.fixture
def mock_config(tmp_path):
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
    mock_session_instance = MagicMock()
    mocker.patch("requests.Session", return_value=mock_session_instance)
    return mock_session_instance


def test_fetch_braze_list_pagination(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    page1 = {
        "templates": [
            {"email_template_id": f"id_{i}", "template_name": f"t_{i}"}
            for i in range(100)
        ]
    }
    page2 = {
        "templates": [
            {"email_template_id": f"id_{i + 100}", "template_name": f"t_{i + 100}"}
            for i in range(50)
        ]
    }
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2),
        *[MagicMock(status_code=200, json=lambda: {"subject": "Test"})] * 150,
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.get.return_value = MagicMock(status_code=404)
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    expected_calls = [
        call(
            "GET",
            "https://rest.mock.braze.com/templates/email/list?limit=100",
            timeout=30,
        ),
        call(
            "GET",
            "https://rest.mock.braze.com/templates/email/list?limit=100&offset=100",
            timeout=30,
        ),
    ]
    mock_session.request.assert_has_calls(expected_calls)


def test_sync_main_stops_if_backup_fails(mocker, mock_session, mock_config):
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_session.request.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(
    mocker, mock_session, mock_config
):
    mocker.patch("sync_logic.perform_tmx_backup", side_effect=ValueError("test error"))
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    assert any("An unexpected error occurred" in msg for msg in logged_messages)
    mock_session.request.assert_not_called()


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
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: empty_content),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.get.return_value = MagicMock(status_code=404)
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    assert mock_session.post.call_count == 1
    assert "resources" in mock_session.post.call_args.args[0]


def test_backup_disabled(mocker, mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mock_session.request.return_value = MagicMock(json=lambda: {})
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_backup_func.assert_not_called()


def test_resource_name_no_update_needed(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Matching"}]
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Test"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": {"attributes": {"name": "Matching"}}},
    )
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_session.patch.assert_not_called()


def test_resource_name_is_updated_when_mismatched(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "New Name"}]
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Test"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.get.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"attributes": {"name": "Old Name"}}}
    )
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_session.patch.assert_called_once()


def test_perform_tmx_backup_success(mocker, mock_config):
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_file_response = MagicMock(
        status_code=200, content=b"<tmx></tmx>", headers={"Content-Type": "text/xml"}
    )
    mock_file_response.json.side_effect = json.JSONDecodeError("Not JSON", "{}", 0)
    mock_tmx_session.get.return_value = mock_file_response
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("pathlib.Path.mkdir")
    logger = AppLogger(no_op_callback)
    result = perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )
    assert result is True


def test_sync_handles_httperror(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    err = requests.exceptions.HTTPError("401 Unauthorized")
    err.response = MagicMock(status_code=401, json=lambda: {"error": "key"})
    mock_session.request.side_effect = err
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    assert "[FATAL] An API error occurred." in "".join(logged_messages)


def test_sync_handles_connection_error(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    mock_session.request.side_effect = requests.exceptions.RequestException("NW down")
    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    assert any("[FATAL] A network error occurred" in msg for msg in logged_messages)


def test_perform_tmx_backup_job_fails(mocker, mock_config):
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_session.get.return_value = MagicMock(
        status_code=200,
        headers={"Content-Type": "application/vnd.api+json"},
        json=lambda: {"data": {"attributes": {"status": "failed"}}},
    )
    logger = AppLogger(no_op_callback)
    result = perform_tmx_backup(mock_config, mock_session, logger, threading.Event())
    assert result is False


def test_perform_tmx_backup_timeout(mocker, mock_config):
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_session.get.return_value = MagicMock(
        status_code=200,
        headers={"Content-Type": "application/vnd.api+json"},
        json=lambda: {"data": {"attributes": {"status": "pending"}}},
    )
    mocker.patch("time.time", side_effect=[100, 501])
    logger = AppLogger(no_op_callback)
    result = perform_tmx_backup(mock_config, mock_session, logger, threading.Event())
    assert result is False


def test_upload_source_content_success(mock_session, mock_config):
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Test"}]
    mock_session.request.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Hello"}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.get.return_value = MagicMock(status_code=404)
    mock_session.post.side_effect = [
        MagicMock(status_code=201),
        MagicMock(status_code=202),
    ]
    sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    assert mock_session.post.call_count == 2
    upload_call = mock_session.post.call_args_list[1]
    upload_payload = json.loads(upload_call.kwargs["data"])
    assert '"subject": "Hello"' in upload_payload["data"]["attributes"]["content"]


def test_sync_cancels_during_long_process(mock_session, mock_config, mocker):
    cancel_event = threading.Event()
    templates = [
        {"email_template_id": f"id_{i}", "template_name": f"t_{i}"} for i in range(10)
    ]
    mock_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mocker.patch("requests.get").return_value = MagicMock(
        status_code=200, content=b"<tmx></tmx>"
    )
    call_count = 0

    def braze_request_router(method, url, **kwargs):
        nonlocal call_count
        if "/templates/email/list" in url:
            return MagicMock(status_code=200, json=lambda: {"templates": templates})
        elif "/templates/email/info" in url:
            call_count += 1
            if call_count > 5:
                cancel_event.set()
            return MagicMock(status_code=200, json=lambda: {"subject": "Test"})
        elif "/content_blocks/list" in url:
            return MagicMock(status_code=200, json=lambda: {"content_blocks": []})
        else:
            return MagicMock(status_code=404)

    def transifex_get_router(url, **kwargs):
        """A smart router for Transifex GET calls."""
        if "tmx_async_downloads" in url:
            return MagicMock(
                status_code=200,
                headers={"Content-Type": "application/vnd.api+json"},
                json=lambda: {
                    "data": {
                        "attributes": {"status": "completed"},
                        "links": {"download": "http://mock.url/download"},
                    }
                },
            )
        elif "/resources/" in url:
            return MagicMock(status_code=404)
        else:
            return MagicMock(status_code=404)

    mock_session.request.side_effect = braze_request_router
    mock_session.get.side_effect = transifex_get_router

    logged_messages = []
    sync_logic_main(
        mock_config, logged_messages.append, cancel_event, mock_progress_callback
    )
    full_log = "".join(logged_messages)
    assert "Sync process was cancelled by the user" in full_log
