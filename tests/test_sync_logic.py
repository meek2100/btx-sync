# tests/test_sync_logic.py

import pytest
import json
from unittest.mock import MagicMock

# Import the main function we want to test
from sync_logic import sync_logic_main
from logger import AppLogger

# --- Pytest Fixtures ---


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
        "BACKUP_ENABLED": False,  # Disable backup for this unit test for simplicity
        "LOG_LEVEL": "Debug",
    }


# --- Unit Test for the Main Sync Logic ---


def test_sync_logic_main_happy_path(mocker, mock_config, mock_logger):
    """
    Tests the entire sync workflow by mocking all API calls.
    This acts as an integration-style unit test for the whole module.
    """
    # 1. SETUP MOCKS for the entire sequence of API calls

    # Mock for Braze 'list' calls
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
    mock_tx_get_resource_response = MagicMock()
    mock_tx_get_resource_response.status_code = 404

    # Use side_effect to return different responses for different `requests.get` calls
    mocker.patch(
        "requests.get",
        side_effect=[
            mock_braze_list_response,  # Call 1: Braze list email templates
            mock_braze_email_info_response,  # Call 2: Braze get email info
            mock_tx_get_resource_response,  # Call 3: Transifex check resource (fails, so we will create it)
            mock_braze_list_response,  # Call 4: Braze list content blocks
            mock_braze_block_info_response,  # Call 5: Braze get block info
            mock_tx_get_resource_response,  # Call 6: Transifex check resource (fails, so we will create it)
        ],
    )

    # Mock all POST requests (for creating resources and uploading strings)
    mock_post_response = MagicMock(status_code=202)  # Simulate success
    mock_post = mocker.patch("requests.post", return_value=mock_post_response)

    # 2. RUN THE FUNCTION
    sync_logic_main(mock_config, mock_logger.log_callback)

    # 3. ASSERTIONS
    # Verify the sequence of calls and their parameters

    # Check that we tried to create the email resource in Transifex
    create_resource_call = mock_post.call_args_list[0]
    create_resource_payload = json.loads(create_resource_call.kwargs["data"])
    assert create_resource_payload["data"]["attributes"]["slug"] == "email_123"
    assert create_resource_payload["data"]["attributes"]["name"] == "Test Email 1"

    # Check that we tried to upload the email strings
    upload_strings_call = mock_post.call_args_list[1]
    upload_strings_payload = json.loads(upload_strings_call.kwargs["data"])
    assert upload_strings_payload["data"]["attributes"]["content"] == json.dumps(
        {
            "subject": "Test Subject",
            "preheader": "Test Preheader",
            "body": "<p>Test Body</p>",
        }
    )

    # Check that we tried to create the content block resource
    create_block_resource_call = mock_post.call_args_list[2]
    create_block_resource_payload = json.loads(
        create_block_resource_call.kwargs["data"]
    )
    assert create_block_resource_payload["data"]["attributes"]["slug"] == "block_456"

    # Check that we tried to upload the content block strings
    upload_block_strings_call = mock_post.call_args_list[3]
    upload_block_strings_payload = json.loads(upload_block_strings_call.kwargs["data"])
    assert upload_block_strings_payload["data"]["attributes"]["content"] == json.dumps(
        {"content": "Test Content Block Body"}
    )
