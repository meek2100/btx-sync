# tests/test_sync_logic.py

import pytest
from unittest.mock import MagicMock

import sync_logic


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


def test_sync_logic_handles_keyerror_from_api(mocker, mock_config, caplog):
    """
    Verify that if a KeyError occurs during the sync, a fatal error is logged.
    """
    # ARRANGE:
    mock_config["BACKUP_ENABLED"] = False
    # To accurately test the 'except KeyError' block in sync_logic_main, we
    # patch the inner function 'fetch_braze_list' and force it to raise a
    # KeyError directly.
    mocker.patch(
        # The target must be the full path to the function *as it's seen by the module under test*
        "sync_logic.fetch_braze_list",
        side_effect=KeyError("Forced test error on purpose"),
    )

    # ACT:
    sync_logic.sync_logic_main(mock_config, lambda msg: print(msg))

    # ASSERT:
    # Check that the fatal error was logged as expected.
    assert "FATAL" in caplog.text
    assert "Received an unexpected response from an API" in caplog.text


def test_sync_logic_main_happy_path(mocker, mock_config):
    """
    Tests the main sync workflow, assuming success.
    """
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    # Mock the two calls to fetch_braze_list to return empty lists,
    # preventing the need to mock subsequent API calls.
    mocker.patch(
        "sync_logic.fetch_braze_list",
        side_effect=[
            [],  # First call for templates
            [],  # Second call for content blocks
        ],
    )
    mock_post = mocker.patch("requests.post")

    sync_logic.sync_logic_main(mock_config, lambda msg: print(msg))

    # Assert that the backup was called and no content-creation calls were made.
    assert sync_logic.perform_tmx_backup.call_count == 1
    mock_post.assert_not_called()


@pytest.mark.parametrize(
    "empty_content",
    [
        {"subject": "", "body": "", "preheader": ""},
        {"subject": None, "body": None, "preheader": None},
        {"subject": "   ", "body": "\t", "preheader": "\n"},
    ],
)
def test_upload_skips_if_no_content(mocker, mock_config, empty_content):
    """
    Verify that no content is uploaded if all translatable fields are empty.
    """
    # ARRANGE
    mocker.patch("sync_logic.perform_tmx_backup", return_value=True)
    # Mock the list call to return one template
    mocker.patch(
        "sync_logic.fetch_braze_list",
        side_effect=[
            [{"email_template_id": "email_123", "template_name": "Empty Template"}],
            [],  # Empty list for content blocks
        ],
    )
    # Mock the details call to return the parameterized empty content
    mocker.patch("sync_logic.fetch_braze_item_details", return_value=empty_content)
    # Mock Transifex calls
    mocker.patch("requests.get", return_value=MagicMock(status_code=404))
    mock_post = mocker.patch("requests.post")

    # ACT
    sync_logic.sync_logic_main(mock_config, lambda msg: print(msg))

    # ASSERT
    # A single POST call should be made to *create* the resource, but none to *upload* content.
    assert mock_post.call_count == 1
    create_resource_call = mock_post.call_args_list[0]
    # Check the URL of the only POST call made
    assert create_resource_call.args[0].endswith("/resources")
