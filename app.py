# app.py

import customtkinter
import json
import keyring
import threading
import tkinter  # Use this for tkinter.Menu and tkinter.TclError

from pathlib import Path

# Import from our other modules
from config import SERVICE_NAME, CONFIG_FILE_NAME
from gui_settings import SettingsWindow
from sync_logic import sync_logic_main


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Braze-Transifex Sync Tool")
        self.geometry("800x600")
        self.iconbitmap("assets/icon.ico")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.control_frame = customtkinter.CTkFrame(self, height=50)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.run_button = customtkinter.CTkButton(
            self.control_frame, text="Run Sync", command=self.start_sync_thread
        )
        self.run_button.pack(side="left", padx=10, pady=5)

        self.settings_button = customtkinter.CTkButton(
            self.control_frame,
            text="Settings",
            command=self.open_settings,
            fg_color="transparent",
            border_width=1,
        )
        self.settings_button.pack(side="right", padx=10, pady=5)

        self.status_label = customtkinter.CTkLabel(self.control_frame, text="Ready")
        self.status_label.pack(side="left", padx=10)

        self.log_box = customtkinter.CTkTextbox(
            self, state="disabled", font=("Courier New", 12)
        )
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Add Right-Click Context Menu
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
        try:
            try:
                with open(CONFIG_FILE_NAME, "r") as f:
                    config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                config = {}

            config["BRAZE_API_KEY"] = keyring.get_password(
                SERVICE_NAME, "braze_api_key"
            )
            config["TRANSIFEX_API_TOKEN"] = keyring.get_password(
                SERVICE_NAME, "transifex_api_token"
            )

            config["BRAZE_REST_ENDPOINT"] = config.get(
                "braze_endpoint", "https://rest.iad-05.braze.com"
            )
            config["TRANSIFEX_ORGANIZATION_SLUG"] = config.get(
                "transifex_org", "control4"
            )
            config["TRANSIFEX_PROJECT_SLUG"] = config.get("transifex_project", "braze")
            config["BACKUP_ENABLED"] = config.get("backup_enabled", True)
            config["BACKUP_PATH"] = config.get(
                "backup_path", str(Path.home() / "Downloads")
            )
            config["LOG_LEVEL"] = config.get("log_level", "Normal")

            if all([config["BRAZE_API_KEY"], config["TRANSIFEX_API_TOKEN"]]):
                return config
            return None
        except Exception as e:
            self.log_message(f"Error loading credentials: {e}")
            return None


if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")

    app = App()
    app.mainloop()
