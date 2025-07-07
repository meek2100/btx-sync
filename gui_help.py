# gui_help.py

import customtkinter
from pathlib import Path
from utils import resource_path


class HelpWindow(customtkinter.CTkToplevel):
    """
    A Toplevel window that displays the application's help content from
    the README.md file.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Help")
        self.geometry("700x550")
        self.iconbitmap(resource_path("assets/icon.ico"))

        # Create a textbox to display the help content
        self.textbox = customtkinter.CTkTextbox(self, wrap="word")
        self.textbox.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        # Load and display the content from README.md
        self._load_content()

        # Create a close button
        self.close_button = customtkinter.CTkButton(
            self, text="Close", command=self.destroy
        )
        self.close_button.pack(side="bottom", pady=10)

    def _load_content(self):
        """
        Loads text from the README.md file and inserts it into the textbox.
        """
        try:
            readme_path = Path(resource_path("README.md"))
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8")
                self.textbox.insert("0.0", content)
            else:
                self.textbox.insert("0.0", "Help file (README.md) not found.")
        except Exception as e:
            self.textbox.insert("0.0", f"Error loading help file:\n\n{e}")

        # Make the textbox read-only after inserting content
        self.textbox.configure(state="disabled")
