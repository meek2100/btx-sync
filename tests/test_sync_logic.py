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

    # Mock for Braze 'list' calls - will be called twice (emails, blocks)
    mock_braze_list_response = MagicMock()
    mock_braze_list_response.json.return_value = {
        "templates": [
            {"email_template_id": "email_123", "template_name": "Test Email 1"}
        ],
        "content_blocks": [{"content_block_id": "block_456", "name": "Test Block 1"}],
    }

    # Mock for Braze 'get template info' call
    mock_braze_email_info_response = MagicMock()
    mock_braze_email_info_response.json.return_value = {
        "subject": "Test Subject",
        "body": "<p>Test Body</p>",
        "preheader": "Test Preheader",
    }

    # Mock for Braze 'get block info' call
    mock_braze_block_info_response = MagicMock()
    mock_braze_block_info_response.json.return_value = {
        "content": "Test Content Block Body"
    }

    # Mock for Transifex 'get resource' call - simulate resource not found (404)
    mock_tx_get_resource_response = MagicMock(status_code=404)

    # Mock `requests.get` to return different values for different calls
    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,  # Call 1: Braze list email templates
            mock_braze_email_info_response,  # Call 2: Braze get email info
            mock_tx_get_resource_response,  # Call 3: Transifex check resource (fails)
            mock_braze_list_response,  # Call 4: Braze list content blocks
            mock_braze_block_info_response,  # Call 5: Braze get block info
            mock_tx_get_resource_response,  # Call 6: Transifex check resource (fails)
        ],
    )

    # Mock `requests.post` for creating/uploading
    mock_post_response = MagicMock(status_code=202)
    mock_post = mocker.patch("requests.post", return_value=mock_post_response)

    # Mock the TMX backup to make it pass without running its logic
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    # 2. RUN THE FUNCTION
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. ASSERTIONS
    # Verify the sequence of POST calls (create resource, upload strings)
    assert (
        mock_post.call_count == 4
    )  # Create Email Res, Upload Email, Create Block Res, Upload Block

    # Check the "create email resource" call
    create_email_payload = json.loads(mock_post.call_args_list[0].kwargs["data"])
    assert create_email_payload["data"]["attributes"]["slug"] == "email_123"

    # Check the "upload email strings" call
    upload_email_payload = json.loads(mock_post.call_args_list[1].kwargs["data"])
    assert "Test Subject" in upload_email_payload["data"]["attributes"]["content"]

    # Check the "create content block resource" call
    create_block_payload = json.loads(mock_post.call_args_list[2].kwargs["data"])
    assert create_block_payload["data"]["attributes"]["slug"] == "block_456"

    # Check the "upload content block strings" call
    upload_block_payload = json.loads(mock_post.call_args_list[3].kwargs["data"])
    assert (
        "Test Content Block Body"
        in upload_block_payload["data"]["attributes"]["content"]
    )


def test_sync_logic_main_stops_if_backup_fails(mocker, mock_config, mock_logger):
    """
    Verify that if backup is enabled and fails, the main sync does not proceed.
    """
    # 1. Setup mock for the backup function to return False (failure)
    mocker.patch("sync_logic.perform_tmx_backup", return_value=False)

    # Mock requests.get and see if it's ever called
    mock_get = mocker.patch("requests.get")

    # 2. Run the main function
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. Assertions
    # The sync should have halted, so no API calls to Braze should have been made.
    mock_get.assert_not_called()


def test_sync_logic_main_handles_braze_api_failure(mocker, mock_config, mock_logger):
    """
    Verify that if the first API call to Braze fails, the sync stops gracefully.
    """
    # 1. Setup mock to raise an error when fetching the Braze list
    mocker.patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("API Network Error"),
    )

    # Disable backup for this test to isolate the sync logic
    mock_config["BACKUP_ENABLED"] = False

    # Spy on the POST method to ensure we never try to create/upload to Transifex
    mock_post = mocker.spy(requests, "post")

    # 2. Run the main function
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. Assertions
    mock_post.assert_not_called()


def test_updates_resource_name_when_name_differs(mocker, mock_config, mock_logger):
    """
    FIXED: Verify that if a resource exists but has a different name,
    a PATCH request is made to update it.
    """
    # 1. Setup mocks
    mock_braze_list_response = MagicMock()
    mock_braze_list_response.json.return_value = {
        "templates": [{"email_template_id": "email_123", "template_name": "New Name"}],
        "content_blocks": [],  # No content blocks for this test
    }
    mock_braze_email_info_response = MagicMock()
    mock_braze_email_info_response.json.return_value = {"subject": "Test Subject"}

    mock_tx_get_resource_response = MagicMock(status_code=200)
    mock_tx_get_resource_response.json.return_value = {
        "data": {"attributes": {"name": "Old Name"}}
    }

    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,
            mock_braze_email_info_response,
            mock_tx_get_resource_response,
            MagicMock(json=lambda: {"content_blocks": []}),  # For the second list call
        ],
    )

    mock_post = mocker.patch("requests.post")
    mock_patch = mocker.patch("requests.patch")
    mock_patch.return_value.raise_for_status.return_value = None
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    # 2. Run the function
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. Assertions
    mock_patch.assert_called_once()
    call_args, call_kwargs = mock_patch.call_args
    sent_payload = json.loads(call_kwargs["data"])
    assert sent_payload["data"]["attributes"]["name"] == "New Name"

    # Assert that POST was called for the string UPLOAD, but not for creating a NEW resource.
    # We check the URL to distinguish between the two types of POST calls.
    upload_call_made = False
    for call in mock_post.call_args_list:
        if "resource_strings_async_uploads" in call.args[0]:
            upload_call_made = True
        else:
            # If a post call was made to any other URL (like /resources), it's a failure
            assert "resources" not in call.args[0]
    assert upload_call_made is True


def test_tmx_backup_handles_job_failure(mocker, mock_config, mock_logger):
    """
    Verify the TMX backup function handles a 'failed' status from Transifex.
    """
    # 1. Setup mocks
    mock_post_response = MagicMock()
    mock_post_response.json.return_value = {"data": {"id": "test_job_id"}}
    mocker.patch("requests.post", return_value=mock_post_response)

    mock_get_response_failed = MagicMock(status_code=200)
    mock_get_response_failed.json.return_value = {
        "data": {"attributes": {"status": "failed"}}
    }
    mocker.patch("requests.get", return_value=mock_get_response_failed)

    # 2. Run the function
    result = sync_logic.perform_tmx_backup(mock_config, {}, mock_logger)

    # 3. Assertions
    assert result is False  # The function should report failure


def test_upload_skips_if_no_content(mocker, mock_config, mock_logger):
    """
    FIXED: Verify that the upload function doesn't make a POST request if the content dict is empty.
    """
    # 1. Setup Mocks
    mock_braze_list_response = MagicMock()
    mock_braze_list_response.json.return_value = {
        "templates": [
            {"email_template_id": "email_123", "template_name": "Empty Template"}
        ],
        "content_blocks": [],
    }
    # Mock Braze info to return NO translatable fields
    mock_braze_info_response = MagicMock()
    mock_braze_info_response.json.return_value = {
        "subject": "",
        "body": None,
        "preheader": "  ",
    }  # All empty/whitespace

    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,
            mock_braze_info_response,
            MagicMock(status_code=404),  # for tx resource check
            MagicMock(json=lambda: {"content_blocks": []}),
        ],
    )

    mock_post = mocker.patch("requests.post")
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)

    # 2. RUN THE FUNCTION
    sync_logic.sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. ASSERTIONS
    # Assert that POST was called once to create the resource
    assert mock_post.call_count == 1
    create_resource_call = mock_post.call_args_list[0]
    create_resource_payload = json.loads(create_resource_call.kwargs["data"])
    assert create_resource_payload["data"]["type"] == "resources"
