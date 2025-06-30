# tests/test_sync_logic.py

import pytest
import json
from unittest.mock import MagicMock

import sync_logic
from logger import AppLogger


@pytest.fixture
def mock_logger():
    return AppLogger(lambda msg: print(msg), level="Debug")


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


def test_sync_logic_main_happy_path(mocker, mock_config, mock_logger):
    mock_braze_list_templates_response = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "email_123", "template_name": "Test Email 1"}
            ]
        }
    )
    mock_braze_list_blocks_response = MagicMock(
        json=lambda: {
            "content_blocks": [
                {"content_block_id": "block_456", "name": "Test Block 1"}
            ]
        }
    )
    mock_braze_email_info_response = MagicMock(
        json=lambda: {
            "subject": "Test Subject",
            "body": "<p>Test Body</p>",
            "preheader": "Test Preheader",
        }
    )
    mock_braze_block_info_response = MagicMock(
        json=lambda: {"content": "Test Content Block Body"}
    )
    mock_tx_get_resource_response = MagicMock(status_code=404)

    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_templates_response,
            mock_braze_email_info_response,
            mock_tx_get_resource_response,
            mock_braze_list_blocks_response,
            mock_braze_block_info_response,
            mock_tx_get_resource_response,
        ],
    )
    mock_post = mocker.patch("requests.post", return_value=MagicMock(status_code=202))
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    assert mock_post.call_count == 4
    create_email_payload = json.loads(mock_post.call_args_list[0].kwargs["data"])
    assert create_email_payload["data"]["attributes"]["slug"] == "email_123"


def test_sync_logic_main_stops_if_backup_fails(mocker, mock_config, mock_logger):
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    mock_get = mocker.patch("requests.get")
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)
    mock_get.assert_not_called()


def test_sync_logic_handles_keyerror_from_api(mocker, mock_config, caplog):
    mock_config["BACKUP_ENABLED"] = False
    mock_bad_response = MagicMock(json=lambda: {"message": "success"})
    mocker.patch("requests.get", return_value=mock_bad_response)
    mock_post = mocker.patch("requests.post")

    # --- START OF FIX ---
    # The second argument must be a callable function. caplog will automatically
    # capture the output of the print calls inside the lambda.
    sync_logic.sync_logic_main(mock_config, lambda msg: print(msg))
    # --- END OF FIX ---

    assert "FATAL" in caplog.text
    assert "The expected field" in caplog.text
    assert "'templates'" in caplog.text
    mock_post.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
        {"subject": "  ", "body": None, "preheader": ""},
    ],
)
def test_upload_skips_if_no_content(mocker, mock_config, mock_logger, empty_content):
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
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    assert mock_post.call_count == 1
    create_resource_call = mock_post.call_args_list[0]
    assert create_resource_call.args[0].endswith("/resources")
