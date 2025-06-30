# tests/test_sync_logic.py

import pytest
from unittest.mock import MagicMock

import sync_logic


def no_op_callback(message):
    pass


@pytest.fixture
def mock_config():
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


# --- NEW TEST ---
def test_backup_disabled(mocker, mock_config):
    """Verify that the backup function is not called when disabled in config."""
    mock_config["BACKUP_ENABLED"] = False
    mock_backup_func = mocker.patch("sync_logic.perform_tmx_backup")
    mocker.patch(
        "requests.get", return_value=MagicMock(json=lambda: {})
    )  # Stop sync after backup check

    sync_logic.sync_logic_main(mock_config, no_op_callback)

    mock_backup_func.assert_not_called()


# --- NEW TEST ---
def test_resource_name_no_update_needed(mocker, mock_config):
    """Verify a resource name is NOT updated if it already matches."""
    mock_config["BACKUP_ENABLED"] = False
    mock_braze_list = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "email_123", "template_name": "Matching Name"}
            ]
        }
    )
    mock_braze_info = MagicMock(json=lambda: {"subject": "Test"})
    # Mock the Transifex GET request to return a 200 OK with the same name
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
    mock_patch = mocker.patch("requests.patch")  # This is what we are checking
    mocker.patch("requests.post")  # Mock post to prevent upload error

    sync_logic.sync_logic_main(mock_config, no_op_callback)

    mock_patch.assert_not_called()


def test_sync_main_stops_if_backup_fails(mocker, mock_config):
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    mock_get = mocker.patch("requests.get")
    sync_logic.sync_logic_main(mock_config, no_op_callback)
    mock_get.assert_not_called()


def test_sync_logic_halts_on_unexpected_backup_response(mocker, mock_config):
    mock_config["BACKUP_ENABLED"] = True
    malformed_response = MagicMock(json=lambda: {"unexpected_key": "some_value"})
    mocker.patch("requests.post", return_value=malformed_response)
    mock_get = mocker.patch("requests.get")
    logged_messages = []

    def log_callback(msg):
        logged_messages.append(msg)

    sync_logic.sync_logic_main(mock_config, log_callback)
    full_log = "\n".join(logged_messages)
    assert "Sync halted due to backup failure" in full_log
    mock_get.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
    ],
)
def test_upload_skips_if_no_content(mocker, mock_config, empty_content):
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
