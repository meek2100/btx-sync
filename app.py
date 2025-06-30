# app.py
import customtkinter
import keyring
import threading
import tkinter  # Use this for tkinter.Menu and tkinter.TclError

from pathlib import Path
from PIL import Image
from customtkinter import CTkImage

# Import from our other modules
from config import SERVICE_NAME
from gui_settings import SettingsWindow
from sync_logic import sync_logic_main
from utils import resource_path


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Braze-Transifex Sync Tool")
        self.geometry("800x600")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.control_frame = customtkinter.CTkFrame(self, height=50)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.run_button = customtkinter.CTkButton(
            self.control_frame, text="Run Sync", command=self.start_sync_thread
        )
        self.run_button.pack(side="left", padx=10, pady=5)

        # ADDED: Load the icon image for the button
        self.more_icon = CTkImage(
            light_image=Image.open(
                resource_path("assets/dots_dark.png")
            ),  # Dark icon on light background
            dark_image=Image.open(
                resource_path("assets/dots_light.png")
            ),  # Light icon on dark background
            size=(20, 20),
        )

        # MODIFIED: Changed the settings button into a "more options" icon button
        self.more_button = customtkinter.CTkButton(
            self.control_frame,
            text="",
            image=self.more_icon,
            width=28,
            height=28,
            fg_color="transparent",
            border_width=0,
            command=self.show_more_menu,  # This command now opens the pop-up
        )
        self.more_button.pack(side="right", padx=10, pady=5)

        self.status_label = customtkinter.CTkLabel(self.control_frame, text="Ready")
        self.status_label.pack(side="left", padx=10)

        self.log_box = customtkinter.CTkTextbox(
            self, state="disabled", font=("Courier New", 12)
        )
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- Pop-up Menu Definition ---
        # ADDED: This creates the pop-up menu that is shown on button click.
        self.more_menu = tkinter.Menu(self, tearoff=0)
        self.more_menu.add_command(label="Settings", command=self.open_settings)
        self.more_menu.add_command(label="Help", command=self.show_help_popup)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="Exit", command=self.destroy)
        # --- End of Pop-up Menu ---

        # Add Right-Click Context Menu for the log box
        self.right_click_menu = tkinter.Menu(
            self.log_box, tearoff=0, background="#2B2B2B", foreground="white"
        )
        self.right_click_menu.add_command(label="Copy", command=self.copy_log_text)
        self.right_click_menu.add_separator()
        self.right_click_menu.add_command(
            label="Select All", command=self.select_all_log_text
        )

        self.log_box.bind("<Button-3>", self.show_right_click_menu)

        self.settings_window = None

    # ADDED: This new method displays the pop-up menu below the "more" button
    def show_more_menu(self):
        """Displays the 'more options' pop-up menu."""
        x = self.more_button.winfo_rootx()
        y = self.more_button.winfo_rooty() + self.more_button.winfo_height()
        self.more_menu.tk_popup(x, y)

    # ADDED: This is a placeholder for a future Help dialog
    def show_help_popup(self):
        """Displays a simple help message box."""
        tkinter.messagebox.showinfo(
            "Help",
            "This is the Braze-Transifex Sync Tool.\n\n"
            "1. Click the '...' button and go to Settings to enter your API keys.\n"
            "2. Click 'Run Sync' to begin the process.\n\n"
            "For more details, please see the README file.",
        )

    def show_right_click_menu(self, event):
        """Displays the right-click menu at the cursor's position."""
        self.right_click_menu.tk_popup(event.x_root, event.y_root)

    def copy_log_text(self):
        """Copies the selected text from the log box to the clipboard."""
        try:
            selected_text = self.log_box.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except tkinter.TclError:
            pass  # Handles case where no text is selected

    def select_all_log_text(self):
        """Selects all text in the log box."""
        self.log_box.tag_add("sel", "1.0", "end")
        return "break"  # Prevents default right-click behavior

    def log_message(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def sync_thread_target(self):
        self.run_button.configure(state="disabled", text="Syncing...")
        self.status_label.configure(text="Running...")

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        config = self.load_config_for_sync()
        if not config:
            self.log_message("--- CONFIGURATION ERROR ---")
            self.log_message("Could not load all necessary API keys and settings.")
            self.log_message("Please open Settings and save your credentials.")
        else:
            sync_logic_main(config, self.log_message)

        self.run_button.configure(state="normal", text="Run Sync")
        self.status_label.configure(text="Ready")
        self.log_message("\n")

    def start_sync_thread(self):
        thread = threading.Thread(target=self.sync_thread_target)
        thread.daemon = True
        thread.start()

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
            self.settings_window.grab_set()
        else:
            self.settings_window.focus()

    def load_config_for_sync(self):
        """Loads all necessary configuration from the system keychain."""
        try:
            config = {}
            # Load all values from keyring, providing defaults where necessary
            config["BRAZE_API_KEY"] = keyring.get_password(
                SERVICE_NAME, "braze_api_key"
            )
            config["TRANSIFEX_API_TOKEN"] = keyring.get_password(
                SERVICE_NAME, "transifex_api_token"
            )
            config["BRAZE_REST_ENDPOINT"] = (
                keyring.get_password(SERVICE_NAME, "braze_endpoint")
                or "https://rest.iad-05.braze.com"
            )
            config["TRANSIFEX_ORGANIZATION_SLUG"] = (
                keyring.get_password(SERVICE_NAME, "transifex_org") or "control4"
            )
            config["TRANSIFEX_PROJECT_SLUG"] = (
                keyring.get_password(SERVICE_NAME, "transifex_project") or "braze"
            )
            config["BACKUP_PATH"] = keyring.get_password(
                SERVICE_NAME, "backup_path"
            ) or str(Path.home() / "Downloads")
            config["LOG_LEVEL"] = (
                keyring.get_password(SERVICE_NAME, "log_level") or "Normal"
            )

            # Load boolean, defaulting to True ("1") if not found
            backup_enabled_str = (
                keyring.get_password(SERVICE_NAME, "backup_enabled") or "1"
            )
            config["BACKUP_ENABLED"] = backup_enabled_str == "1"

            # Check that essential keys were found
            if all([config["BRAZE_API_KEY"], config["TRANSIFEX_API_TOKEN"]]):
                return config

            # If essential keys are missing, return None to trigger error message
            return None

        except Exception as e:
            self.log_message(f"Error loading configuration from keychain: {e}")
            return None


if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")

    app = App()
    app.mainloop()
