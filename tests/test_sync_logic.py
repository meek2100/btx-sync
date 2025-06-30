# tests/test_sync_logic.py

import pytest
import requests
import json
from unittest.mock import MagicMock, call

import sync_logic
from logger import AppLogger


def no_op_callback(message):
    """A callback function that does nothing, used to satisfy the log_callback argument."""
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


def test_fetch_braze_list_pagination(mocker, mock_config):
    """Verify that the fetch_braze_list function correctly handles pagination."""
    mock_config["BACKUP_ENABLED"] = False
    page1 = {"templates": [{"email_template_id": "id1"}] * 100}
    page2 = {"templates": [{"email_template_id": "id2"}] * 50}
    page3 = {"templates": []}

    mock_get = mocker.patch(
        "requests.get",
        side_effect=[
            MagicMock(json=lambda: page1),
            MagicMock(json=lambda: page2),
            MagicMock(json=lambda: page3),
            MagicMock(json=lambda: {"content_blocks": []}),
        ],
    )
    mocker.patch("requests.post")

    sync_logic.sync_logic_main(mock_config, no_op_callback)

    expected_calls = [
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100",
            headers={"Authorization": "Bearer test_braze_key"},
        ),
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100&offset=100",
            headers={"Authorization": "Bearer test_braze_key"},
        ),
        call(
            "https://rest.mock.braze.com/templates/email/list?limit=100&offset=150",
            headers={"Authorization": "Bearer test_braze_key"},
        ),
        call(
            "https://rest.mock.braze.com/content_blocks/list?limit=100",
            headers={"Authorization": "Bearer test_braze_key"},
        ),
    ]
    mock_get.assert_has_calls(expected_calls, any_order=False)


def test_sync_main_stops_if_backup_fails(mocker, mock_config):
    """Verify that if backup is enabled and fails, the main sync does not proceed."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    mock_get = mocker.patch("requests.get")
    sync_logic.sync_logic_main(mock_config, no_op_callback)
    mock_get.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(mocker, mock_config):
    """Verify the sync halts if the backup process raises a KeyError from a bad response."""
    mock_config["BACKUP_ENABLED"] = True
    malformed_response = MagicMock(json=lambda: {"unexpected_key": "some_value"})
    mocker.patch("requests.post", return_value=malformed_response)
    mock_get = mocker.patch("requests.get")
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    sync_logic.sync_logic_main(mock_config, log_callback)
    full_log = "\n".join(logged_messages)
    assert "Sync halted due to backup failure" in full_log
    mock_get.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
    ],
)
def test_upload_skips_if_no_content(mocker, mock_config, empty_content):
    """Verify that no content is uploaded if all translatable fields are empty."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    mock_braze_list_response = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "email_123", "template_name": "Empty Template"}
            ]
        }
    )
    mock_braze_info_response = MagicMock(json=lambda: empty_content)
    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,
            mock_braze_info_response,
            MagicMock(status_code=404),
            MagicMock(json=lambda: {"content_blocks": []}),
        ],
    )
    mock_post = mocker.patch("requests.post")
    sync_logic.sync_logic_main(mock_config, no_op_callback)
    assert mock_post.call_count == 1


def test_backup_disabled(mocker, mock_config):
    """Verify that the backup function is not called when disabled in config."""
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mocker.patch("requests.get", return_value=MagicMock(json=lambda: {}))
    sync_logic.sync_logic_main(mock_config, no_op_callback)
    mock_backup_func.assert_not_called()


def test_resource_name_no_update_needed(mocker, mock_config):
    """Verify a resource name is NOT updated if it already matches."""
    mock_config["BACKUP_ENABLED"] = False
    mock_braze_list = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "e123", "template_name": "Matching Name"}
            ]
        }
    )
    mock_braze_info = MagicMock(json=lambda: {"subject": "Test"})
    mock_tx_get = MagicMock(
        status_code=200,
        json=lambda: {"data": {"attributes": {"name": "Matching Name"}}},
    )
    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list,
            mock_braze_info,
            mock_tx_get,
            MagicMock(json=lambda: {}),
        ],
    )
    mock_patch = mocker.patch("requests.patch")
    mocker.patch("requests.post")
    sync_logic.sync_logic_main(mock_config, no_op_callback)
    mock_patch.assert_not_called()


def test_perform_tmx_backup_success(mocker, mock_config):
    """Test the complete successful flow of a TMX backup."""
    mock_post = MagicMock(json=lambda: {"data": {"id": "job_123"}})
    mock_status = MagicMock(
        json=lambda: {
            "data": {
                "attributes": {"status": "completed"},
                "links": {"download": "url"},
            }
        }
    )
    mock_download = MagicMock(content=b"<tmx>content</tmx>")
    mocker.patch("requests.post", return_value=mock_post)
    mocker.patch("requests.get", side_effect=[mock_status, mock_download])
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("pathlib.Path.mkdir")
    result = sync_logic.perform_tmx_backup(mock_config, {}, AppLogger(no_op_callback))
    assert result is True
    assert requests.get.call_count == 2


def test_sync_handles_httperror(mocker, mock_config):
    """Test that the main sync logic catches and logs an HTTPError."""
    mock_config["BACKUP_ENABLED"] = False
    http_error = requests.exceptions.HTTPError("401 Unauthorized")
    mock_response = MagicMock(status_code=401, text="Invalid API Key")
    mock_response.json.return_value = {"error": "Invalid API Key"}
    http_error.response = mock_response
    http_error.request = MagicMock(url="http://mock.braze.com/api")
    mocker.patch("requests.get", side_effect=http_error)
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    sync_logic.sync_logic_main(mock_config, log_callback)
    full_log = "\n".join(logged_messages)
    assert "[FATAL] An API error occurred." in full_log
    assert "Status Code: 401" in full_log


def test_sync_handles_connection_error(mocker, mock_config):
    """Test that the main sync logic catches and logs a ConnectionError."""
    mock_config["BACKUP_ENABLED"] = False
    mocker.patch(
        "requests.get", side_effect=requests.exceptions.ConnectionError("Network down")
    )
    logged_messages = []

    def log_callback(message):
        logged_messages.append(message)

    sync_logic.sync_logic_main(mock_config, log_callback)
    full_log = "\n".join(logged_messages)
    assert "[FATAL] A network connection error occurred." in full_log


def test_perform_tmx_backup_job_fails(mocker, mock_config):
    """Test the TMX backup flow when Transifex reports a failed job."""
    mocker.patch(
        "requests.post",
        return_value=MagicMock(json=lambda: {"data": {"id": "job_123"}}),
    )
    mock_status_response = MagicMock(
        json=lambda: {"data": {"attributes": {"status": "failed"}}}
    )
    mocker.patch("requests.get", return_value=mock_status_response)
    result = sync_logic.perform_tmx_backup(mock_config, {}, AppLogger(no_op_callback))
    assert result is False


def test_perform_tmx_backup_timeout(mocker, mock_config):
    """Verify that the TMX backup polling correctly times out."""
    # ARRANGE
    mocker.patch(
        "requests.post",
        return_value=MagicMock(json=lambda: {"data": {"id": "job_123"}}),
    )
    # Mock the status check to always return 'pending'
    mocker.patch(
        "requests.get",
        return_value=MagicMock(
            json=lambda: {"data": {"attributes": {"status": "pending"}}}
        ),
    )
    # Mock time.time to simulate a timeout
    mocker.patch(
        "time.time", side_effect=[100, 101, 102, 103, 104, 500]
    )  # Last call exceeds timeout
    mocker.patch("time.sleep")  # Prevent test from actually sleeping

    # ACT
    result = sync_logic.perform_tmx_backup(mock_config, {}, AppLogger(no_op_callback))

    # ASSERT
    assert result is False


def test_upload_source_content_success(mocker, mock_config):
    """Verify that a successful upload calls the Transifex API correctly."""
    # ARRANGE
    mock_config["BACKUP_ENABLED"] = False
    # Mock the list call to return one template
    mock_braze_list = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "e123", "template_name": "Test Template"}
            ]
        }
    )
    # Mock the details call to return content
    mock_braze_info = MagicMock(json=lambda: {"subject": "Hello", "body": "World"})
    # Mock the Transifex resource check
    mock_tx_get = MagicMock(status_code=404)
    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list,
            mock_braze_info,
            mock_tx_get,
            MagicMock(json=lambda: {}),
        ],
    )

    # This is the call we are verifying
    mock_post = mocker.patch("requests.post")

    # ACT
    sync_logic.sync_logic_main(mock_config, no_op_callback)

    # ASSERT
    # The first POST creates the resource, the second uploads the content.
    assert mock_post.call_count == 2
    # Check the payload of the second call
    upload_call_args = mock_post.call_args_list[1]
    upload_payload = json.loads(upload_call_args.kwargs["data"])

    assert upload_payload["data"]["type"] == "resource_strings_async_uploads"
    assert '"subject": "Hello"' in upload_payload["data"]["attributes"]["content"]
