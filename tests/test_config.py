# tests/test_config.py

import pytest
from pathlib import Path

from app import App
from constants import (
    DEFAULT_BACKUP_PATH_NAME,
    DEFAULT_LOG_LEVEL,
    DEFAULT_BACKUP_ENABLED,
    DEFAULT_AUTO_UPDATE_ENABLED,
)


@pytest.fixture
def mock_app_for_config(mocker):
    """Mocks the App class just for testing config logic."""
    mocker.patch.object(App, "__init__", lambda s: None)
    app_instance = App()
    return app_instance


def test_get_current_config_applies_defaults(mock_app_for_config, mocker):
    """
    Verify that get_current_config returns correct default values when
    no settings are found in the keychain.
    """
    # ARRANGE: Mock keyring to return None for all settings.
    mocker.patch("keyring.get_password", return_value=None)

    # ACT
    config = mock_app_for_config.get_current_config()

    # ASSERT
    # Check that the default values from constants.py are applied correctly.
    expected_backup_path = str(Path.home() / DEFAULT_BACKUP_PATH_NAME)
    assert config["BACKUP_PATH"] == expected_backup_path
    assert config["LOG_LEVEL"] == DEFAULT_LOG_LEVEL
    assert config["BACKUP_ENABLED"] is DEFAULT_BACKUP_ENABLED
    assert config["AUTO_UPDATE_ENABLED"] is DEFAULT_AUTO_UPDATE_ENABLED
