# gui_help.py

import customtkinter
import webbrowser
import re
from pathlib import Path
from utils import resource_path


class HelpWindow(customtkinter.CTkToplevel):
    """
    A Toplevel window that displays a formatted, user-focused help document
    by parsing the project's README.md file.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Help")
        self.geometry("700x550")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.textbox = customtkinter.CTkTextbox(self, wrap="word", corner_radius=0)
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self._configure_tags()
        self._load_and_display_readme()

        self.close_button = customtkinter.CTkButton(
            self, text="Close", command=self.destroy
        )
        self.close_button.grid(row=1, column=0, pady=10)

    def _configure_tags(self):
        """Defines the styles for Markdown elements."""
        try:
            self.textbox.tag_config("h2", font=("", 16, "bold"), spacing1=10)
            self.textbox.tag_config("h3", font=("", 14, "bold"), spacing1=8)
            self.textbox.tag_config("bold", font=("", 12, "bold"))
        except Exception:
            self.textbox.tag_config("h2", spacing1=10, spacing3=5)
            self.textbox.tag_config("h3", spacing1=8, spacing3=4)

        self.textbox.tag_config("link", foreground="cornflowerblue", underline=True)
        self.textbox.tag_bind(
            "link", "<Enter>", lambda e: self.textbox.configure(cursor="hand2")
        )
        self.textbox.tag_bind(
            "link", "<Leave>", lambda e: self.textbox.configure(cursor="")
        )
        self.textbox.tag_config("list", lmargin1=20, lmargin2=40)
        self.textbox.tag_config("h_spacing", spacing3=10)

    def _get_user_content(self, full_content: str) -> str:
        """
        Extracts and combines relevant sections from the README for in-app help.
        """
        content_parts = []
        sections_to_extract = [
            ("Usage", "### Usage"),
            ("How It Works", "## How It Works"),
            ("Secure Automatic Updates", "### Secure Automatic Updates"),
        ]

        for title, heading in sections_to_extract:
            try:
                # FIX: Use a more robust regex to find content for each section individually
                # This pattern finds the content between one heading and the next
                pattern = re.compile(
                    f"^{re.escape(heading)}(.*?)(?=\n##|\n---|\Z)",
                    re.DOTALL | re.MULTILINE,
                )
                match = pattern.search(full_content)
                if match:
                    section_content = match.group(1).strip()
                    # Re-add a consistent heading level for display
                    content_parts.append(f"## {title}\n{section_content}")
            except IndexError:
                continue

        if not content_parts:
            return "## Help Not Found\nCould not parse help content from README.md."

        return "\n\n---\n\n".join(content_parts)

    def _parse_and_insert(self, text_block: str):
        """Parses a block of markdown text and inserts it with formatting."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for line in text_block.split("\n"):
            stripped_line = line.strip()

            # Skip empty lines to prevent extra space
            if not stripped_line:
                self.textbox.insert("end", "\n")
                continue

            # 1. Determine block-level tags (headings, lists)
            tag_to_apply = []
            if stripped_line.startswith("### "):
                display_text = stripped_line.replace("### ", "")
                tag_to_apply.append("h3")
            elif stripped_line.startswith("## "):
                display_text = stripped_line.replace("## ", "")
                tag_to_apply.append("h2")
                tag_to_apply.append("h_spacing")
            elif stripped_line.startswith("- "):
                display_text = "• " + stripped_line[2:]
                tag_to_apply.append("list")
            elif re.match(r"^\d+\.\s", stripped_line):
                display_text = "  " + stripped_line
                tag_to_apply = ["list"]
            else:
                display_text = line  # Preserve indentation for paragraphs

            # 2. Insert the line with block tag
            self.textbox.insert("end", display_text + "\n", tuple(tag_to_apply))

            # 3. Apply inline tags to the line we just inserted
            current_line_index = self.textbox.index("end-2l")
            self._apply_inline_tags(current_line_index, display_text)

        self.textbox.configure(state="disabled")

    def _apply_inline_tags(self, line_start_index: str, line_content: str):
        """Finds and applies inline tags to a given line of text."""
        for match in reversed(
            list(re.finditer(r"(\[.*?\]\(.*?\))|(\*\*.*?\*\*)", line_content))
        ):
            part = match.group(0)
            start_char, end_char = match.span()

            start_index = f"{line_start_index}+{start_char}c"
            end_index = f"{line_start_index}+{end_char}c"

            # Handle Links: [text](url)
            link_match = re.fullmatch(r"\[(.*?)\]\((.*?)\)", part)
            if link_match:
                text, url = link_match.groups()
                self.textbox.delete(start_index, end_index)
                self.textbox.insert(start_index, text, "link")
                self.textbox.tag_bind(
                    "link", "<Button-1>", lambda e, u=url: webbrowser.open(u)
                )
                continue

            # Handle Bold: **text**
            bold_match = re.fullmatch(r"\*\*(.*?)\*\*", part)
            if bold_match:
                text = bold_match.group(1)
                self.textbox.delete(start_index, end_index)
                self.textbox.insert(start_index, text, "bold")

    def _load_and_display_readme(self):
        """Loads, parses, and displays the final formatted help content."""
        try:
            readme_path = Path(resource_path("README.md"))
            if not readme_path.exists():
                self.textbox.insert("1.0", "Help file (README.md) not found.")
                return

            full_content = readme_path.read_text(encoding="utf-8")
            user_content = self._get_user_content(full_content)
            self._parse_and_insert(user_content)

        except Exception as e:
            self.textbox.insert("1.0", f"Error loading help file:\n\n{e}")
        finally:
            self.textbox.configure(state="disabled")
