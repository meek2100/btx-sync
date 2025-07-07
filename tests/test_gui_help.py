# tests/test_gui_help.py

import pytest
from unittest.mock import MagicMock
from gui_help import HelpWindow

# A sample README content to use for all tests in this file
SAMPLE_README = """
# Project Title

Some intro text.

---
## How It Works

This is how the application functions.

---
## For End-Users

### Usage

- Step one for usage.
- Step two for usage.

### Secure Automatic Updates

This app has **secure** updates. Go to the [Releases Page](https://github.com/meek2100/btx-sync/releases).

---
## For Developers

Some developer info.
"""


@pytest.fixture
def mock_help_window(mocker):
    """Mocks the HelpWindow to test its internal logic without a GUI."""
    mocker.patch.object(HelpWindow, "__init__", lambda s, *a, **kw: None)
    help_window = HelpWindow(None)
    help_window.textbox = MagicMock()
    # Mock the _get_user_content to isolate the parsing logic
    mocker.patch.object(help_window, "_get_user_content", return_value=SAMPLE_README)
    return help_window


def test_get_user_content_extraction(mock_help_window):
    """Verify that only the correct user-facing sections are extracted."""
    # ACT
    extracted_content = mock_help_window._get_user_content(SAMPLE_README)
    # ASSERT
    assert "## How It Works" in extracted_content
    assert "### Usage" in extracted_content
    assert "### Secure Automatic Updates" in extracted_content
    assert "## For Developers" not in extracted_content


def test_parse_and_insert_applies_tags(mock_help_window):
    """Verify that the parser correctly applies formatting tags."""
    # ACT
    mock_help_window._parse_and_insert(SAMPLE_README)
    # ASSERT
    # Check that insert was called with the correct tags for each line type
    mock_help_window.textbox.insert.assert_any_call("end", "How It Works\n", "h2")
    mock_help_window.textbox.insert.assert_any_call("end", "Usage\n", "h3")
    mock_help_window.textbox.insert.assert_any_call(
        "end", "• Step one for usage.\n", "list"
    )
    # Check that the part with multiple inline styles was handled
    mock_help_window.textbox.insert.assert_any_call("end", "This app has ", ("list",))
    mock_help_window.textbox.insert.assert_any_call("end", "secure", ("list", "bold"))
    mock_help_window.textbox.insert.assert_any_call(
        "end", " updates. Go to the ", ("list",)
    )
    mock_help_window.textbox.insert.assert_any_call(
        "end", "Releases Page", ("list", "link", "link-releases")
    )
