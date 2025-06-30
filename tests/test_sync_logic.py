# tests/test_sync_logic.py

import pytest
from unittest.mock import MagicMock

import sync_logic


def no_op_callback(message):
    """A callback function that does nothing, used to satisfy the log_callback argument."""
    pass


@pytest.fixture
def mock_config():
    """Provides a consistent mock configuration for all tests."""
    return {
        "BRAZE_API_KEY": "test_braze_key",
        "BRAZE_REST_ENDPOINT": "https://rest.mock.braze.com",
        "TRANSIFEX_API_TOKEN": "test_tx_token",
        "TRANSIFEX_ORGANIZATION_SLUG": "test_org",
        "TRANSIFEX_PROJECT_SLUG": "test_project",
        "BACKUP_ENABLED": True,
        "BACKUP_PATH": "/fake/path",
        "LOG_LEVEL": "Debug",
    }


def test_sync_main_stops_if_backup_fails(mocker, mock_config):
    """Verify that if backup is enabled and fails, the main sync does not proceed."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    mock_get = mocker.patch("requests.get")

    sync_logic.sync_logic_main(mock_config, no_op_callback)

    mock_get.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(mocker, mock_config):
    """
    Verify the sync halts if the backup process raises a KeyError from a bad response.
    """
    mock_config["BACKUP_ENABLED"] = True
    malformed_response = MagicMock(json=lambda: {"unexpected_key": "some_value"})
    mocker.patch("requests.post", return_value=malformed_response)
    mock_get = mocker.patch("requests.get")

    logged_messages = []

    def log_callback(message):
        """A nested callback to capture logs in a list."""
        logged_messages.append(message)

    sync_logic.sync_logic_main(mock_config, log_callback)

    full_log = "\n".join(logged_messages)
    assert "[FATAL] An unexpected error occurred starting TMX backup job" in full_log
    assert "Sync halted due to backup failure" in full_log
    mock_get.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
        {"subject": "  ", "body": None, "preheader": ""},
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
    create_resource_call = mock_post.call_args_list[0]
    assert create_resource_call.args[0].endswith("/resources")


def test_sync_logic_main_happy_path(mocker, mock_config):
    """Tests the main sync workflow, assuming success with no items."""
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    mocker.patch(
        "requests.get",
        return_value=MagicMock(json=lambda: {"templates": [], "content_blocks": []}),
    )
    mock_post = mocker.patch("requests.post")

    sync_logic.sync_logic_main(mock_config, no_op_callback)

    sync_logic.perform_tmx_backup.assert_called_once()
    mock_post.assert_not_called()
