# gui_help.py

import customtkinter
import webbrowser
import re
from pathlib import Path
from utils import resource_path
import secrets


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
        self.close_button.grid(row=1, column=0, pady=(10, 10))

    def _configure_tags(self):
        """Defines the styles for Markdown elements."""
        try:
            # Use fonts for styling where supported
            self.textbox.tag_config("h2", font=("", 16, "bold"), spacing3=5)
            self.textbox.tag_config("h3", font=("", 13, "bold"), spacing3=4)
            self.textbox.tag_config("bold", font=("", 12, "bold"))
        except Exception:
            # Fallback to spacing if font tags are not supported
            self.textbox.tag_config("h2", spacing1=10)
            self.textbox.tag_config("h3", spacing1=8)

        self.textbox.tag_config("link", foreground="cornflowerblue", underline=True)
        self.textbox.tag_bind(
            "link", "<Enter>", lambda e: self.textbox.configure(cursor="hand2")
        )
        self.textbox.tag_bind(
            "link", "<Leave>", lambda e: self.textbox.configure(cursor="")
        )
        self.textbox.tag_config("list", lmargin1=20, lmargin2=40)
        self.textbox.tag_config("separator", spacing1=10, spacing3=10)

    def _get_user_content(self, full_content: str) -> str:
        """Extracts and combines relevant sections from the README."""
        # Use regex to robustly find sections between headings
        usage_match = re.search(r"### Usage(.*?)---", full_content, re.DOTALL)
        how_it_works_match = re.search(
            r"## How It Works(.*?)---", full_content, re.DOTALL
        )
        updates_match = re.search(
            r"### Secure Automatic Updates(.*?)(?=\n##|\Z)", full_content, re.DOTALL
        )

        # Build the final content string from the extracted sections
        parts = []
        if usage_match:
            parts.append("## Usage\n" + usage_match.group(1).strip())
        if how_it_works_match:
            parts.append("## How It Works\n" + how_it_works_match.group(1).strip())
        if updates_match:
            parts.append(
                "## Secure Automatic Updates\n" + updates_match.group(1).strip()
            )

        if not parts:
            return "## Help Not Found\nCould not parse help content from README.md."

        return "\n\n---\n\n".join(parts)

    def _parse_and_insert(self, text_block: str):
        """Parses a block of markdown text and inserts it with formatting."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for line in text_block.split("\n"):
            line_tag = self._get_line_tag(line)

            # Split line by markdown for inline formatting
            parts = re.split(r"(\[.*?\]\(.*?\))|(\*\*.*?\*\*)", line)

            for part in filter(None, parts):
                final_tags = (line_tag,) if line_tag else ()

                # Handle Links: [text](url)
                if part.startswith("[") and part.endswith(")"):
                    match = re.match(r"\[(.*?)\]\((.*?)\)", part)
                    if match:
                        text, url = match.groups()
                        link_id = f"link-{secrets.token_hex(4)}"
                        self.textbox.insert("end", text, final_tags + ("link", link_id))
                        self.textbox.tag_bind(
                            link_id, "<Button-1>", lambda e, u=url: webbrowser.open(u)
                        )
                        continue

                # Handle Bold: **text**
                elif part.startswith("**") and part.endswith("**"):
                    text = part.strip("*")
                    self.textbox.insert("end", text, final_tags + ("bold",))
                    continue

                # Handle plain text
                self.textbox.insert(
                    "end",
                    part.replace("### ", "").replace("## ", "").replace("- ", "• "),
                    final_tags,
                )

            self.textbox.insert("end", "\n")

        self.textbox.configure(state="disabled")

    def _get_line_tag(self, line: str) -> str | None:
        """Determines the primary tag for a line of markdown."""
        stripped = line.strip()
        if stripped.startswith("## "):
            return "h2"
        if stripped.startswith("### "):
            return "h3"
        if stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            return "list"
        if stripped == "---":
            return "separator"
        return None

    def _load_and_display_readme(self):
        """Loads, parses, and displays the final formatted help content."""
        try:
            readme_path = Path(resource_path("README.md"))
            if not readme_path.exists():
                self._parse_and_insert("## Help file not found.")
                return

            full_content = readme_path.read_text(encoding="utf-8")
            user_content = self._get_user_content(full_content)
            self._parse_and_insert(user_content)

        except Exception as e:
            self._parse_and_insert(f"## Error\nCould not load help file:\n\n{e}")
        finally:
            self.textbox.configure(state="disabled")
