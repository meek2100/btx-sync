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
        # Use a try...except block to handle platforms that don't support fonts
        try:
            self.textbox.tag_config("h2", font=("", 16, "bold"), spacing3=5)
            self.textbox.tag_config("h3", font=("", 13, "bold"), spacing3=4)
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
        self.textbox.tag_config("separator", spacing1=10, spacing3=10)

    def _get_user_content(self, full_content: str) -> list[str]:
        """Extracts and combines relevant sections from the README."""
        content_sections = []
        # Define sections to extract in the desired order
        sections_to_extract = [
            "## How It Works",
            "### Usage",
            "### Secure Automatic Updates",
        ]

        for heading in sections_to_extract:
            try:
                # Find content between the current heading and the next major heading
                pattern = re.compile(
                    f"^{re.escape(heading)}(.*?)(?=\n##|\n---|\Z)",
                    re.DOTALL | re.MULTILINE,
                )
                match = pattern.search(full_content)
                if match:
                    section_content = f"{heading}\n{match.group(1).strip()}"
                    content_sections.append(section_content)
            except IndexError:
                continue

        if not content_sections:
            return ["## Help Not Found\nCould not parse help content from README.md."]

        return content_sections

    def _parse_and_insert(self, text_blocks: list[str]):
        """Parses a list of markdown blocks and inserts them with formatting."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for i, block in enumerate(text_blocks):
            if i > 0:
                # Add a separator between sections
                self.textbox.insert("end", "\n---\n\n", "separator")

            for line in block.split("\n"):
                line = line.strip()
                # Determine line-level tag
                tag = None
                if line.startswith("###"):
                    line, tag = line.replace("###", "").strip(), "h3"
                elif line.startswith("##"):
                    line, tag = line.replace("##", "").strip(), "h2"
                elif line.startswith("- "):
                    line, tag = "• " + line[2:], "list"
                elif re.match(r"^\d+\.", line):
                    line, tag = "  " + line, "list"

                # Split line by inline markdown, keeping the delimiters
                parts = re.split(r"(\[.*?\]\(.*?\))|(\*\*.*?\*\*)", line)
                for part in filter(None, parts):
                    # Handle links: [text](url)
                    if part.startswith("[") and part.endswith(")"):
                        match = re.match(r"\[(.*?)\]\((.*?)\)", part)
                        if match:
                            text, url = match.groups()
                            link_id = f"link-{secrets.token_hex(4)}"
                            self.textbox.insert("end", text, ("link", link_id))
                            self.textbox.tag_bind(
                                link_id,
                                "<Button-1>",
                                lambda e, u=url: webbrowser.open(u),
                            )
                            continue

                    # Handle bold: **text**
                    elif part.startswith("**") and part.endswith("**"):
                        text = part[2:-2]
                        self.textbox.insert("end", text, "bold")
                        continue

                    # Handle plain text
                    self.textbox.insert("end", part)

                self.textbox.insert("end", "\n", tag)

        self.textbox.configure(state="disabled")

    def _load_and_display_readme(self):
        """Loads, parses, and displays the final formatted help content."""
        try:
            readme_path = Path(resource_path("README.md"))
            if not readme_path.exists():
                self._parse_and_insert(["## Help file not found."])
                return

            full_content = readme_path.read_text(encoding="utf-8")
            user_content_blocks = self._get_user_content(full_content)
            self._parse_and_insert(user_content_blocks)

        except Exception as e:
            self._parse_and_insert([f"## Error\nCould not load help file:\n\n{e}"])
        finally:
            self.textbox.configure(state="disabled")
