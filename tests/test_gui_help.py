# tests/test_gui_help.py

import pytest
from unittest.mock import MagicMock, call
from gui_help import HelpWindow

SAMPLE_README = """
# btx sync
---
## For End-Users

### Usage
- Step one for usage.
- Go to the [Releases Page](https://github.com/meek2100/btx-sync/releases).
---
## For Developers
Developer info.
"""


@pytest.fixture
def mock_help_window(mocker):
    """Mocks the HelpWindow to test its internal logic without a GUI."""
    mocker.patch.object(HelpWindow, "__init__", lambda s, *a, **kw: None)
    help_window = HelpWindow(None)
    help_window.textbox = MagicMock()
    return help_window


def test_get_user_content_extraction(mock_help_window):
    """Verify that only the correct user-facing sections are extracted."""
    extracted_content = mock_help_window._get_user_content(SAMPLE_README)
    assert "### Usage" in extracted_content
    assert "## For Developers" not in extracted_content


def test_parse_and_insert_applies_tags(mock_help_window):
    """Verify that the parser correctly applies formatting tags."""
    test_content = "## Title\n- A list item.\n[A link](http://test.com)"

    mock_help_window._parse_and_insert(test_content)

    calls = mock_help_window.textbox.insert.call_args_list

    # Check for heading and list tags
    assert call("end", "Title", "h2") in calls
    assert call("end", "• A list item.", "list") in calls

    # Check that link text is inserted with the correct tag
    assert any(
        c.args[0] == "end" and c.args[1] == "A link" and "link" in c.args[2]
        for c in calls
    )
