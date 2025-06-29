# tests/test_sync_logic.py

import pytest
import json
from unittest.mock import MagicMock, mock_open

# Import the functions and classes we want to test
from sync_logic import create_or_update_transifex_resource, perform_tmx_backup
from logger import AppLogger

# --- Pytest Fixtures ---
# Fixtures are reusable setup functions for your tests.


@pytest.fixture
def mock_logger():
    """Provides a mock logger that we can inspect."""
    # A simple lambda that does nothing, to satisfy the log_callback requirement.
    return AppLogger(lambda msg: None, level="Debug")


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
    }


# --- Unit Tests for `create_or_update_transifex_resource` ---


def test_creates_new_resource_when_404(mocker, mock_config, mock_logger):
    """
    Verify that if a resource does not exist (gets a 404),
    the function attempts to create it with a POST request.
    """
    # 1. Setup the mocks
    # Mock requests.get to return a 404 response
    mock_get_response = MagicMock()
    mock_get_response.status_code = 404
    mocker.patch("requests.get", return_value=mock_get_response)

    # Mock requests.post so we can check if it gets called
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.raise_for_status.return_value = (
        None  # Ensure it doesn't raise an error
    )

    # 2. Run the function under test
    create_or_update_transifex_resource(
        slug="new_template_id",
        name="New Template Name",
        transifex_org_slug=mock_config["TRANSIFEX_ORGANIZATION_SLUG"],
        transifex_project_slug=mock_config["TRANSIFEX_PROJECT_SLUG"],
        transifex_headers={},
        logger=mock_logger,
    )

    # 3. Assert the results
    # Check that we tried to create a new resource
    mock_post.assert_called_once()
    # Check that the payload sent in the POST request is correct
    call_args, call_kwargs = mock_post.call_args
    sent_payload = json.loads(call_kwargs["data"])
    assert sent_payload["data"]["attributes"]["slug"] == "new_template_id"
    assert sent_payload["data"]["attributes"]["name"] == "New Template Name"


def test_does_nothing_if_resource_exists_and_name_matches(
    mocker, mock_config, mock_logger
):
    """
    Verify that if a resource exists and has the correct name,
    no PATCH or POST request is made.
    """
    # 1. Setup the mocks
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {
        "data": {"attributes": {"name": "Existing Name"}}
    }
    mocker.patch("requests.get", return_value=mock_get_response)
    mock_post = mocker.patch("requests.post")
    mock_patch = mocker.patch("requests.patch")

    # 2. Run the function
    create_or_update_transifex_resource(
        slug="existing_id",
        name="Existing Name",  # The name matches what the mock returns
        transifex_org_slug=mock_config["TRANSIFEX_ORGANIZATION_SLUG"],
        transifex_project_slug=mock_config["TRANSIFEX_PROJECT_SLUG"],
        transifex_headers={},
        logger=mock_logger,
    )

    # 3. Assert the results
    mock_post.assert_not_called()
    mock_patch.assert_not_called()


# --- Unit Tests for `perform_tmx_backup` ---


def test_tmx_backup_happy_path(mocker, mock_config, mock_logger):
    """
    Verify the successful TMX backup workflow from start to finish.
    """
    # 1. Setup Mocks
    # Mock the initial POST to create the job
    mock_post_response = MagicMock()
    mock_post_response.json.return_value = {"data": {"id": "test_job_id"}}
    mock_post = mocker.patch("requests.post", return_value=mock_post_response)

    # Mock the GET requests for polling the status
    mock_get_response_pending = MagicMock(status_code=200)
    mock_get_response_pending.json.return_value = {
        "data": {"attributes": {"status": "pending"}}
    }

    mock_get_response_completed = MagicMock(status_code=200)
    mock_get_response_completed.json.return_value = {
        "data": {
            "attributes": {"status": "completed"},
            "links": {"download": "http://fake-download-url.com"},
        }
    }

    # Use side_effect to return different values on subsequent calls
    mock_get = mocker.patch(
        "requests.get",
        side_effect=[
            mock_get_response_pending,  # First poll -> pending
            mock_get_response_completed,  # Second poll -> completed
            MagicMock(content=b"tmx file content"),  # The actual download call
        ],
    )

    # Mock file system operations so we don't write a real file
    mocker.patch("pathlib.Path.mkdir")
    mock_file = mocker.patch("builtins.open", mock_open())

    # 2. Run the function
    result = perform_tmx_backup(mock_config, {}, mock_logger)

    # 3. Assertions
    assert result is True  # The function should report success
    mock_post.assert_called_once()  # Ensure we requested the backup
    assert mock_get.call_count == 3  # Polled twice, then downloaded once
    mock_file.assert_called_once()  # Ensure we tried to save the file
    # Check that we wrote the correct content to the file
    mock_file().write.assert_called_once_with(b"tmx file content")
