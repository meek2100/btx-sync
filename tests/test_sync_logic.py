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


@pytest.fixture
def no_op_callback():
    """A callback fixture that does nothing, used to satisfy the
    log_callback argument.
    """

    def _callback(message):
        pass

    return _callback


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


@pytest.fixture
def mock_app_logger(mocker):
    """
    Mocks the AppLogger class to capture messages.
    Provides mock_logger_instance for assertions.
    """
    mock_logger_instance = MagicMock()
    mocker.patch("sync_logic.AppLogger", return_value=mock_logger_instance)
    return mock_logger_instance


# ADDED 'mocker' to arguments
def test_fetch_braze_list_pagination(mocker, mock_session, mock_config, no_op_callback):
    """Verify that the fetch_braze_list function correctly handles pagination."""
    mock_config["BACKUP_ENABLED"] = False
    page1 = {"templates": [{"email_template_id": "id1"}] * 100}
    page2 = {"templates": [{"email_template_id": "id2"}] * 50}

    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    expected_calls = [
        call("https://rest.mock.braze.com/templates/email/list?limit=100", timeout=30),
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100&offset=100",
            timeout=30,
        ),
    ]
    mock_session.get.assert_has_calls(expected_calls)


# ADDED 'mocker' to arguments
def test_sync_main_stops_if_backup_fails(
    mocker, mock_session, mock_config, no_op_callback
):
    """Verify that if backup is enabled and fails, the sync does not proceed."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_session.get.assert_not_called()


# ADDED 'mocker' and 'mock_app_logger' to arguments
def test_sync_logic_halts_on_unexpected_backup_response(
    mocker, mock_session, mock_config, no_op_callback, mock_app_logger
):
    """Verify the sync halts if the backup process fails unexpectedly."""
    mock_config["BACKUP_ENABLED"] = True
    mocker.patch("sync_logic.perform_tmx_backup", side_effect=ValueError("test error"))
    # We pass no_op_callback to main function, but check mock_app_logger
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_app_logger.fatal.assert_any_call(
        mocker.match("An unexpected error occurred: *")
    )
    mock_session.get.assert_not_called()


# ADDED 'mocker' to arguments
@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
    ],
)
def test_upload_skips_if_no_content(
    mocker, mock_session, mock_config, empty_content, no_op_callback
):
    """Verify no content is uploaded if all translatable fields are empty."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    templates = [{"email_template_id": "e123", "template_name": "Empty"}]
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates}),
        MagicMock(status_code=200, json=lambda: empty_content),
        MagicMock(status_code=404),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    assert mock_session.post.call_count == 1
    assert "resources" in mock_session.post.call_args.args[0]


# ADDED 'mocker' to arguments
def test_backup_disabled(mocker, mock_session, mock_config, no_op_callback):
    """Verify that the backup function is not called when disabled in config."""
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mock_session.get.return_value = MagicMock(json=lambda: {})
    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())
    mock_backup_func.assert_not_called()


# ADDED 'mocker' to arguments (needed for patch.object on AppLogger)
def test_resource_name_no_update_needed(
    mocker, mock_session, mock_config, no_op_callback
):
    """Verify a resource name is NOT updated if it already matches."""
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


# ADDED 'mocker' to arguments
def test_perform_tmx_backup_success(mocker, mock_config, no_op_callback):
    """Test the complete successful flow of a TMX backup."""
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_file_response = MagicMock(status_code=200, content=b"<tmx></tmx>")
    mock_file_response.json.side_effect = json.JSONDecodeError("err", "doc", 0)
    mock_tmx_session.get.return_value = mock_file_response

    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("pathlib.Path.mkdir")
    logger = AppLogger(no_op_callback)
    result = sync_logic.perform_tmx_backup(
        mock_config, mock_tmx_session, logger, threading.Event()
    )
    assert result is True


def test_sync_handles_httperror(mocker, mock_session, mock_config, mock_app_logger):
    """Test that the main sync logic catches and logs an HTTPError."""
    mock_config["BACKUP_ENABLED"] = False
    err = requests.exceptions.HTTPError("401 Unauthorized")
    err.response = MagicMock(status_code=401, json=lambda: {"error": "key"})
    mock_session.get.side_effect = err

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    mock_app_logger.fatal.assert_any_call("An API error occurred.")


def test_sync_handles_connection_error(
    mocker, mock_session, mock_config, mock_app_logger
):
    """Test that the main sync logic catches and logs a ConnectionError."""
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = requests.exceptions.ConnectionError("NW down")

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    mock_app_logger.fatal.assert_any_call(mocker.match("A network error occurred: *"))


# ADDED 'mocker' to arguments
def test_perform_tmx_backup_job_fails(mocker, mock_config, no_op_callback):
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


# ADDED 'mocker' to arguments
def test_perform_tmx_backup_timeout(mocker, mock_config, no_op_callback):
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
    mocker.patch("time.time", side_effect=[100, 501])
    logger = AppLogger(no_op_callback)
    result = sync_logic.perform_tmx_backup(
        mock_config, mock_session, logger, threading.Event()
    )
    assert result is False


# ADDED 'mocker' to arguments
def test_upload_source_content_success(
    mocker, mock_session, mock_config, no_op_callback
):
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

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    assert mock_session.post.call_count == 2
    upload_call = mock_session.post.call_args_list[1]
    upload_payload = json.loads(upload_call.kwargs["data"])
    assert '"subject": "Hello"' in upload_payload["data"]["attributes"]["content"]


# --- NEW AND CORRECTED TESTS BELOW ---


def test_perform_tmx_backup_cancellation(mocker, mock_config, no_op_callback):
    """Test the TMX backup is cancelled by user action during polling."""
    mock_tmx_session = MagicMock()
    mock_tmx_session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"data": {"id": "job1"}}
    )
    mock_time = mocker.patch("time.time")
    mock_time.side_effect = [100, 105, 110]

    cancel_event = threading.Event()
    logger = AppLogger(no_op_callback)

    def get_side_effect_with_cancel(*args, **kwargs):
        if mock_tmx_session.get.call_count == 1:
            cancel_event.set()
        return MagicMock(
            status_code=200,
            headers={"Content-Type": "application/vnd.api+json"},
            json=lambda: {"data": {"attributes": {"status": "pending"}}},
        )

    mock_tmx_session.get.side_effect = get_side_effect_with_cancel

    with pytest.raises(sync_logic.CancellationError) as excinfo:
        sync_logic.perform_tmx_backup(
            mock_config, mock_tmx_session, logger, cancel_event
        )
    assert str(excinfo.value) == "Sync process was cancelled by the user."


def test_sync_main_handles_cancellation_during_backup(
    mocker, mock_config, mock_app_logger
):
    """Verify sync logic logs cancellation and stops if backup is cancelled."""
    mock_config["BACKUP_ENABLED"] = True
    mocker.patch(
        "sync_logic.perform_tmx_backup",
        side_effect=sync_logic.CancellationError("Backup cancelled."),
    )

    cancel_event = threading.Event()
    sync_logic.sync_logic_main(mock_config, no_op_callback, cancel_event)

    mock_app_logger.info.assert_any_call(
        "--- Sync process was cancelled by the user. ---"
    )
    mock_session_instance = mocker.patch("requests.Session").return_value
    mock_session_instance.get.assert_not_called()


def test_sync_main_cancellation_during_braze_list_fetch(
    mocker, mock_session, mock_config, mock_app_logger
):
    """Verify sync logic halts when cancelled during Braze list fetching."""
    mock_config["BACKUP_ENABLED"] = False
    templates_page = {
        "templates": [{"email_template_id": f"id{i}"} for i in range(100)]
    }

    cancel_event = threading.Event()

    def braze_get_side_effect(*args, **kwargs):
        if mock_session.get.call_count == 1:
            cancel_event.set()
            raise sync_logic.CancellationError("Simulated cancellation during fetch")
        return MagicMock(status_code=200, json=lambda: templates_page)

    mock_session.get.side_effect = braze_get_side_effect

    sync_logic.sync_logic_main(mock_config, no_op_callback, cancel_event)

    mock_app_logger.info.assert_any_call(
        "--- Sync process was cancelled by the user. ---"
    )
    assert mock_session.get.call_count == 1


def test_sync_main_cancellation_during_braze_detail_fetch(
    mocker, mock_session, mock_config, mock_app_logger
):
    """Verify sync logic halts when cancelled during Braze detail fetching."""
    mock_config["BACKUP_ENABLED"] = False
    templates_list = [
        {"email_template_id": "temp_id_1", "template_name": "Template 1"},
        {"email_template_id": "temp_id_2", "template_name": "Template 2"},
    ]

    cancel_event = threading.Event()

    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": templates_list}),
        MagicMock(
            status_code=200,
            json=lambda: {"subject": "Sub1"},
        ),
    ]

    def _mock_check_for_cancel(event):
        if event.is_set():
            raise sync_logic.CancellationError("Simulated cancellation")

    mocker.patch("sync_logic.check_for_cancel", side_effect=_mock_check_for_cancel)

    # Patch AppLogger.info on the class to trigger cancellation and log
    mocker.patch.object(
        AppLogger,
        "info",
        side_effect=lambda msg: (
            "Fetching details for ID: temp_id_1" in msg
            and cancel_event.set()
            and mock_app_logger.info.real_mock(msg)
        ),
    )

    sync_logic.sync_logic_main(mock_config, no_op_callback, cancel_event)

    mock_app_logger.info.assert_any_call(
        "--- Sync process was cancelled by the user. ---"
    )
    assert mock_session.get.call_args_list[1][0][0] == (
        "https://rest.mock.braze.com/templates/email/info?email_template_id=temp_id_1"
    )
    assert not any(
        "temp_id_2" in call_args[0] for call_args in mock_session.get.call_args_list[2:]
    )


def test_sync_main_handles_empty_braze_templates_list(
    mock_session, mock_config, no_op_callback
):
    """Verify sync handles empty Braze templates list gracefully."""
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"templates": []}),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    assert mock_session.get.call_args_list[0][0][0].startswith(
        "https://rest.mock.braze.com/templates/email/list"
    )
    assert mock_session.get.call_args_list[1][0][0].startswith(
        "https://rest.mock.braze.com/content_blocks/list"
    )

    # Verify that no attempts were made to create/update Transifex resources
    post_calls = [
        c
        for c in mock_session.post.call_args_list
        if "resource_strings_async_uploads" not in str(c) and "resources" in str(c)
    ]
    assert len(post_calls) == 0
    assert mock_session.patch.call_count == 0


def test_sync_main_handles_empty_braze_content_blocks_list(
    mock_session, mock_config, no_op_callback
):
    """Verify sync handles empty Braze content blocks list gracefully."""
    mock_config["BACKUP_ENABLED"] = False
    mock_session.get.side_effect = [
        MagicMock(
            status_code=200,
            json=lambda: {
                "templates": [{"email_template_id": "e1", "template_name": "T1"}]
            },
        ),
        MagicMock(status_code=200, json=lambda: {"subject": "S1"}),
        MagicMock(status_code=404),
        MagicMock(status_code=200),
        MagicMock(status_code=200, json=lambda: {"content_blocks": []}),
    ]
    mock_session.post.return_value = MagicMock(status_code=201)

    sync_logic.sync_logic_main(mock_config, no_op_callback, threading.Event())

    assert any("e1" in str(c) for c in mock_session.get.call_args_list)
    assert mock_session.get.call_args_list[-1][0][0].startswith(
        "https://rest.mock.braze.com/content_blocks/list"
    )

    # Verify no resource operations for content blocks happened
    block_resource_posts = [
        c for c in mock_session.post.call_args_list if "content_block_id" in str(c)
    ]
    block_resource_patches = [
        c for c in mock_session.patch.call_args_list if "content_block_id" in str(c)
    ]
    assert len(block_resource_posts) == 0
    assert len(block_resource_patches) == 0
