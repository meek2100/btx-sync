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
    extracted_content = mock_help_window._get_user_content(SAMPLE_README)

    # ASSERT
    # Check that the extracted content contains the correct headings in order
    assert "## Usage" in extracted_content
    assert "## How It Works" in extracted_content
    assert "## Secure Automatic Updates" in extracted_content

    # Check that excluded sections are not present
    assert "## For Developers" not in extracted_content
    assert "### Installation" not in extracted_content


def test_get_user_content_with_missing_sections(mock_help_window):
    """
    Verify that the function handles a README that is missing some sections.
    """
    # ARRANGE: Create a README that is missing the "How It Works" section
    partial_readme = SAMPLE_README.replace("## How It Works", "")

    # ACT
    extracted_content = mock_help_window._get_user_content(partial_readme)

    # ASSERT
    assert "## Usage" in extracted_content
    assert "## Secure Automatic Updates" in extracted_content
    assert "## How It Works" not in extracted_content


def test_get_user_content_not_found(mock_help_window):
    """
    Verify that a clear message is returned if no user content is found.
    """
    # ARRANGE: Provide content that doesn't have any of the target sections
    developer_only_readme = "## For Developers\nSome text."

    # ACT
    extracted_content = mock_help_window._get_user_content(developer_only_readme)

    # ASSERT
    assert "Help Not Found" in extracted_content
