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
        """Defines styles for supported Markdown elements."""
        self.textbox.tag_config("h2", spacing1=15, spacing3=5)
        self.textbox.tag_config("h3", spacing1=10, spacing3=5)
        self.textbox.tag_config("link", foreground="cornflowerblue", underline=True)
        self.textbox.tag_bind(
            "link", "<Enter>", lambda e: self.textbox.configure(cursor="hand2")
        )
        self.textbox.tag_bind(
            "link", "<Leave>", lambda e: self.textbox.configure(cursor="")
        )
        self.textbox.tag_config("list", lmargin1=20, lmargin2=40)

    def _get_user_content(self, full_content: str) -> str:
        """Extracts the end-user specific section from the README."""
        try:
            user_section = re.search(
                r"## For End-Users(.*?)---", full_content, re.DOTALL
            )
            if user_section:
                return user_section.group(1).strip()
            return "Help section not found."
        except Exception:
            return "Help section not found."

    def _parse_and_insert(self, text_block: str):
        """Parses a block of markdown text and inserts it with formatting."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for line in text_block.split("\n"):
            line_tag = self._get_line_tag(line)
            clean_line = line.replace("### ", "").replace("## ", "").strip("**")

            if line_tag == "list" and line.strip().startswith("- "):
                clean_line = "• " + clean_line.lstrip("- ")

            parts = re.split(r"(\[.*?\]\(.*?\))", clean_line)

            for part in filter(None, parts):
                if part.startswith("[") and part.endswith(")"):
                    match = re.match(r"\[(.*?)\]\((.*?)\)", part)
                    if match:
                        text, url = match.groups()
                        link_id = f"link-{secrets.token_hex(4)}"
                        self.textbox.insert("end", text, ("link", link_id))
                        self.textbox.tag_bind(
                            link_id, "<Button-1>", lambda e, u=url: webbrowser.open(u)
                        )
                        continue

                self.textbox.insert("end", part, line_tag)

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
