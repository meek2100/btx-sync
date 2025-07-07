# tests/test_gui_help.py

import pytest
from gui_help import HelpWindow

# Sample README content for testing
SAMPLE_README = """
# btx sync

Some general info.

## How It Works

This is how it works.

---
## For End-Users

### Installation

Install steps here.

### Usage

Usage steps here.

---
## For Developers

Developer steps here.

### Secure Automatic Updates

Update info here.
"""


@pytest.fixture
def mock_help_window(mocker):
    """Mocks the full initialization of the HelpWindow for logic testing."""
    mocker.patch.object(HelpWindow, "__init__", lambda s, *a, **kw: None)
    help_window = HelpWindow(None)
    return help_window


def test_get_user_content_extraction(mock_help_window):
    """Verify that only the correct user-facing sections are extracted."""
    # ACT
    extracted_sections = mock_help_window._get_user_content(SAMPLE_README)

    # ASSERT
    # Check that the extracted content contains the correct headings
    content_str = "".join(extracted_sections)
    assert "### Usage" in content_str
    assert "## How It Works" in content_str
    assert "### Secure Automatic Updates" in content_str

    # Check that excluded sections are not present
    assert "## For Developers" not in content_str
    assert "### Installation" not in content_str
