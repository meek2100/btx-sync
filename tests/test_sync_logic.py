# tests/test_sync_logic.py

import pytest
import requests
import json
import threading
from unittest.mock import MagicMock, call

import sync_logic
from logger import AppLogger


@pytest.fixture(autouse=True)
def mock_time_sleep(mocker):
    """Automatically mock time.sleep() for all tests to prevent long waits."""
    mocker.patch("time.sleep")


def no_op_callback(message):
    """A callback function that does nothing, used to satisfy the log_callback
    argument.
    """
    pass


def mock_progress_callback(message):
    """A mock progress callback for testing."""
    pass


@pytest.fixture
def mock_config(tmp_path):
    """Provides a mock config and uses a temporary path for backups."""
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
    """Verify that the fetch_braze_list function correctly handles pagination."""
    mock_config["BACKUP_ENABLED"] = False
    # Mocking 100 templates for page 1, and 50 for page 2
    page1_templates = [
        {"email_template_id": f"id1_{i}", "template_name": f"t1_{i}"}
        for i in range(100)
    ]
    page2_templates = [
        {"email_template_id": f"id2_{i}", "template_name": f"t2_{i}"} for i in range(50)
    ]
    page1 = {"templates": page1_templates}
    page2 = {"templates": page2_templates}

    mock_responses = [
        # 1. Pagination calls for templates
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2),
    ]
    # Add mocks for all detail and Transifex calls
    for _ in range(150):  # 100 on page 1, 50 on page 2
        mock_responses.extend(
            [
                MagicMock(status_code=200, json=lambda: {"subject": "Test"}),  # details
                MagicMock(status_code=404),  # tx resource get
            ]
        )
    # Add mock for content block list call
    mock_responses.append(
        MagicMock(status_code=200, json=lambda: {"content_blocks": []})
    )
    mock_session.get.side_effect = mock_responses
    mock_session.post.return_value = MagicMock(status_code=201)

    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )

    # FIX: Update expected calls to match the correct application logic.
    # The first call should NOT have an offset parameter.
    expected_calls = [
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100",
            timeout=30,
        ),
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100&offset=100",
            timeout=30,
        ),
    ]
    mock_session.get.assert_has_calls(expected_calls)


def test_sync_main_stops_if_backup_fails(mocker, mock_session, mock_config):
    """Verify that if backup is enabled and fails, the sync does not proceed."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_session.get.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(
    mocker, mock_session, mock_config
):
    """Verify the sync halts if the backup process fails unexpectedly."""
    mock_config["BACKUP_ENABLED"] = True
    mocker.patch("sync_logic.perform_tmx_backup", side_effect=ValueError("test error"))
    logged_messages = []
    sync_logic.sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
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
    """Verify no content is uploaded if all translatable fields are empty."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    templates = [{"email_template_id": "e123", "template_name": "Empty"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: empty_content),
        MagicMock(status_code=404),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    assert mock_session.post.call_count == 1
    assert "resources" in mock_session.post.call_args.args[0]


def test_backup_disabled(mocker, mock_session, mock_config):
    """Verify that the backup function is not called when disabled in config."""
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mock_session.get.return_value = MagicMock(json=lambda: {})
    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )
    mock_backup_func.assert_not_called()


def test_resource_name_no_update_needed(mock_session, mock_config):
    """Verify a resource name is NOT updated if it already matches."""
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Matching"}]

    # FIX: Provide a complete set of mocks for the entire process
    mock_session.get.side_effect = [
        # 1. Fetch template list
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        # 2. Fetch template details
        MagicMock(status_code=200, json=lambda: {"subject": "Test"}),
        # 3. Get Transifex resource (found, and name matches)
        MagicMock(
            status_code=200,
            json=lambda: {"data": {"attributes": {"name": "Matching"}}},
        ),
        # 4. Fetch content block list
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]

    # Mock the POST call for uploading source content
    mock_session.post.return_value = MagicMock(status_code=202)

    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )

    # The assertion remains the same: patch should not be called
    mock_session.patch.assert_not_called()


def test_perform_tmx_backup_success(mocker, mock_config):
    """Test the complete successful flow of a TMX backup."""
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    # This mock will represent the final response which is the file itself.
    # Set headers to simulate a TMX file download.
    mock_file_response = MagicMock(
        status_code=200,
        content=b"<tmx></tmx>",
        headers={"Content-Type": "text/xml"},
    )
    # Ensure .json() is not called on this response by default,
    # as we expect file content.
    mock_file_response.json.side_effect = json.JSONDecodeError("Not JSON", "{}", 0)
    mock_tmx_session.get.return_value = mock_file_response

    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("pathlib.Path.mkdir")
    logger = AppLogger(no_op_callback)
    result = sync_logic.perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )
    assert result is True


def test_sync_handles_httperror(mock_session, mock_config):
    """Test that the main sync logic catches and logs an HTTPError."""
    mock_config["BACKUP_ENABLED"] = False
    err = requests.exceptions.HTTPError("401 Unauthorized")
    err.response = MagicMock(status_code=401, json=lambda: {"error": "key"})
    mock_session.get.side_effect = err
    logged_messages = []
    sync_logic.sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    full_log = "".join(logged_messages)
    assert "[FATAL] An API error occurred." in full_log


def test_sync_handles_connection_error(mock_session, mock_config):
    """Test that the main sync logic catches and logs a ConnectionError."""
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = requests.exceptions.ConnectionError("NW down")
    logged_messages = []
    sync_logic.sync_logic_main(
        mock_config, logged_messages.append, threading.Event(), mock_progress_callback
    )
    assert any("[FATAL] A network error occurred" in msg for msg in logged_messages)


def test_perform_tmx_backup_job_fails(mocker, mock_config):
    """Test the TMX backup flow when Transifex reports a failed job."""
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
    result = sync_logic.perform_tmx_backup(
        mock_config, mock_session, logger, threading.Event()
    )
    assert result is False


def test_perform_tmx_backup_timeout(mocker, mock_config):
    """Verify that the TMX backup polling correctly times out."""
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_session.get.return_value = MagicMock(
        status_code=200,
        headers={"Content-Type": "application/vnd.api+json"},
        json=lambda: {"data": {"attributes": {"status": "pending"}}},
    )
    # Make time.time jump forward past the timeout
    mocker.patch("time.time", side_effect=[100, 501])
    logger = AppLogger(no_op_callback)
    result = sync_logic.perform_tmx_backup(
        mock_config, mock_session, logger, threading.Event()
    )
    assert result is False


def test_upload_source_content_success(mock_session, mock_config):
    """Verify that a successful upload calls the Transifex API correctly."""
    mock_config["BACKUP_ENABLED"] = False
    templates = [{"email_template_id": "e123", "template_name": "Test"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: {"subject": "Hello"}),
        MagicMock(status_code=404),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.post.side_effect = [
        MagicMock(status_code=201),
        MagicMock(status_code=202),
    ]

    sync_logic.sync_logic_main(
        mock_config, no_op_callback, threading.Event(), mock_progress_callback
    )

    assert mock_session.post.call_count == 2
    upload_call = mock_session.post.call_args_list[1]
    upload_payload = json.loads(upload_call.kwargs["data"])
    assert '"subject": "Hello"' in upload_payload["data"]["attributes"]["content"]
