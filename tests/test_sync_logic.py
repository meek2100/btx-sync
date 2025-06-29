# tests/test_sync_logic.py

import pytest
import json
import requests
from unittest.mock import MagicMock

# Import the main function we want to test and its dependencies
import sync_logic
from logger import AppLogger

# --- Pytest Fixtures ---
# Fixtures are reusable setup functions for your tests.


@pytest.fixture
def mock_logger():
    """Provides a mock logger that we can inspect."""
    # A simple lambda that does nothing, to satisfy the log_callback requirement.
    return AppLogger(lambda msg: print(msg), level="Debug")


@pytest.fixture
def mock_config():
    """Provides a consistent mock configuration dictionary for all tests."""
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


# --- Unit Tests for the Main Sync Logic ---


def test_sync_logic_main_happy_path(mocker, mock_config, mock_logger):
    """
    Tests the entire sync workflow by mocking all external API calls.
    This acts as an integration-style unit test for the whole module.
    """
    # 1. SETUP MOCKS for the entire sequence of API calls

    mock_braze_list_response = MagicMock()
    mock_braze_list_response.json.return_value = {
        "templates": [
            {"email_template_id": "email_123", "template_name": "Test Email 1"}
        ],
        "content_blocks": [{"content_block_id": "block_456", "name": "Test Block 1"}],
    }

    mock_braze_email_info_response = MagicMock()
    mock_braze_email_info_response.json.return_value = {
        "subject": "Test Subject",
        "body": "<p>Test Body</p>",
        "preheader": "Test Preheader",
    }

    mock_braze_block_info_response = MagicMock()
    mock_braze_block_info_response.json.return_value = {
        "content": "Test Content Block Body"
    }

    mock_tx_get_resource_response = MagicMock(status_code=404)

    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,
            mock_braze_email_info_response,
            mock_tx_get_resource_response,
            mock_braze_list_response,
            mock_braze_block_info_response,
            mock_tx_get_resource_response,
        ],
    )

    mock_post_response = MagicMock(status_code=202)
    mock_post = mocker.patch("requests.post", return_value=mock_post_response)

    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    # 2. RUN THE FUNCTION
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. ASSERTIONS
    assert mock_post.call_count == 4

    create_email_payload = json.loads(mock_post.call_args_list[0].kwargs["data"])
    assert create_email_payload["data"]["attributes"]["slug"] == "email_123"

    upload_email_payload = json.loads(mock_post.call_args_list[1].kwargs["data"])
    assert "Test Subject" in upload_email_payload["data"]["attributes"]["content"]

    create_block_payload = json.loads(mock_post.call_args_list[2].kwargs["data"])
    assert create_block_payload["data"]["attributes"]["slug"] == "block_456"

    upload_block_payload = json.loads(mock_post.call_args_list[3].kwargs["data"])
    assert (
        "Test Content Block Body"
        in upload_block_payload["data"]["attributes"]["content"]
    )


def test_sync_logic_main_stops_if_backup_fails(mocker, mock_config, mock_logger):
    """
    Verify that if backup is enabled and fails, the main sync does not proceed.
    """
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)
    mock_get = mocker.patch("requests.get")
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)
    mock_get.assert_not_called()


def test_sync_logic_main_handles_braze_api_failure(mocker, mock_config, mock_logger):
    """
    Verify that if the first API call to Braze fails, the sync stops gracefully.
    """
    mocker.patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("API Network Error"),
    )
    mock_config["BACKUP_ENABLED"] = False
    mock_post = mocker.spy(requests, "post")
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)
    mock_post.assert_not_called()


def test_updates_resource_name_when_name_differs(mocker, mock_config, mock_logger):
    """
    Verify that if a resource exists but has a different name, a PATCH request is made.
    """
    mock_braze_list_response = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "email_123", "template_name": "New Name"}
            ],
            "content_blocks": [],
        }
    )
    mock_braze_email_info_response = MagicMock(json=lambda: {"subject": "Test Subject"})
    mock_tx_get_resource_response = MagicMock(
        status_code=200, json=lambda: {"data": {"attributes": {"name": "Old Name"}}}
    )

    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,
            mock_braze_email_info_response,
            mock_tx_get_resource_response,
            MagicMock(json=lambda: {"content_blocks": []}),
        ],
    )

    mocker.patch("requests.post")
    mock_patch = mocker.patch("requests.patch")
    mock_patch.return_value.raise_for_status.return_value = None
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    mock_patch.assert_called_once()
    sent_payload = json.loads(mock_patch.call_args.kwargs["data"])
    assert sent_payload["data"]["attributes"]["name"] == "New Name"


def test_tmx_backup_handles_job_failure(mocker, mock_config, mock_logger):
    """
    Verify the TMX backup function handles a 'failed' status from Transifex.
    """
    mock_post_response = MagicMock(json=lambda: {"data": {"id": "test_job_id"}})
    mocker.patch("requests.post", return_value=mock_post_response)
    mock_get_response_failed = MagicMock(
        status_code=200, json=lambda: {"data": {"attributes": {"status": "failed"}}}
    )
    mocker.patch("requests.get", return_value=mock_get_response_failed)

    result = sync_logic.perform_tmx_backup(mock_config, {}, mock_logger)
    assert result is False


def test_upload_skips_if_no_content(mocker, mock_config, mock_logger):
    """
    FIXED: Verify that the upload function doesn't make a POST request if the content dict is empty.
    """
    # 1. Setup Mocks
    mock_braze_list_response = MagicMock(
        json=lambda: {
            "templates": [
                {"email_template_id": "email_123", "template_name": "Empty Template"}
            ],
            "content_blocks": [],
        }
    )
    mock_braze_info_response = MagicMock(
        json=lambda: {"subject": "", "body": None, "preheader": "  "}
    )

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

    # 2. RUN THE FUNCTION
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. ASSERTIONS
    assert mock_post.call_count == 1
    create_resource_call = mock_post.call_args_list[0]
    # FIX: Check the positional 'url' argument instead of the keyword argument.
    assert create_resource_call.args[0].endswith("/resources")


def test_tmx_backup_timeout(mocker, mock_config, mock_logger):
    """
    Verify that the TMX backup polling correctly times out.
    """
    mocker.patch(
        "requests.post",
        return_value=MagicMock(json=lambda: {"data": {"id": "test_job_id"}}),
    )
    mocker.patch(
        "requests.get",
        return_value=MagicMock(
            json=lambda: {"data": {"attributes": {"status": "pending"}}}
        ),
    )
    mocker.patch(
        "time.time", side_effect=[100, 101, 102, 103, 104, 500]
    )  # Last call exceeds timeout

    result = sync_logic.perform_tmx_backup(mock_config, {}, mock_logger)
    assert result is False


def test_tmx_backup_polling_fails_on_http_error(mocker, mock_config, mock_logger):
    """
    FIXED: Verify that the TMX backup function handles a network error during polling.
    """
    # 1. Setup mocks
    mocker.patch(
        "requests.post",
        return_value=MagicMock(json=lambda: {"data": {"id": "test_job_id"}}),
    )

    # FIX: Create a mock response object and attach it to the exception
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    mock_error_response.text = "Internal Server Error"
    http_error = requests.exceptions.HTTPError("Network Error")
    http_error.response = mock_error_response
    mocker.patch("requests.get", side_effect=http_error)

    # 2. Run the function
    result = sync_logic.perform_tmx_backup(mock_config, {}, mock_logger)

    # 3. Assertions
    assert result is False


def test_create_or_update_fails_on_get_error(mocker, mock_config, mock_logger):
    """
    Verify the main logic halts if checking for a resource fails.
    """
    mock_config["BACKUP_ENABLED"] = False
    mocker.patch(
        "requests.get",
        side_effect=[
            MagicMock(
                json=lambda: {
                    "templates": [
                        {
                            "email_template_id": "email_123",
                            "template_name": "Test Email 1",
                        }
                    ]
                }
            ),
            MagicMock(json=lambda: {"subject": "Test Subject"}),
            requests.exceptions.RequestException("API Down"),  # Fail on TX check
        ],
    )
    mock_post = mocker.spy(requests, "post")

    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    mock_post.assert_not_called()
