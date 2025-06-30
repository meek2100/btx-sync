# gui_settings.py

import customtkinter
import keyring
import json
import webbrowser
from tkinter import messagebox, filedialog
from pathlib import Path

from config import SERVICE_NAME, CONFIG_FILE_NAME


class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Settings")
        self.geometry("600x600")

        self.grid_columnconfigure(1, weight=1)

        # Braze Settings
        self.create_setting_row(
            "Braze API Key:",
            1,
            "https://www.braze.com/docs/user_guide/administrative/app_settings/api_settings_tab/#api-keys-1",
            show="*",
        )
        self.create_setting_row(
            "Braze Endpoint:",
            2,
            "https://www.braze.com/docs/user_guide/administrative/access_braze/sdk_endpoints",
        )

        # Transifex Settings
        self.create_setting_row(
            "Transifex API Token:",
            4,
            "https://developers.transifex.com/reference/api-authentication",
            show="*",
        )
        org_slug_msg = "Log in to Transifex. In the URL, the Organization Slug is the part right after '.com/'.\n\nExample: https://app.transifex.com/control4/...\nThe slug is 'control4'."
        self.create_setting_row("Transifex Org Slug:", 5, org_slug_msg)
        project_slug_msg = "In your project URL, the Project Slug is the part after your organization slug.\n\nExample: https://app.transifex.com/control4/braze-testing/...\nThe slug is 'braze-testing'."
        self.create_setting_row("Transifex Project Slug:", 6, project_slug_msg)

        # Backup Settings
        self.backup_label = customtkinter.CTkLabel(
            self,
            text="Backup Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.backup_label.grid(
            row=7, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w"
        )
        self.backup_checkbox = customtkinter.CTkCheckBox(
            self, text="Backup TMX before sync"
        )
        self.backup_checkbox.grid(
            row=8, column=0, columnspan=2, padx=20, pady=5, sticky="w"
        )
        self.backup_path_label = customtkinter.CTkLabel(self, text="Backup Directory:")
        self.backup_path_label.grid(row=9, column=0, padx=20, pady=5, sticky="w")
        self.backup_path_entry = customtkinter.CTkEntry(self)
        self.backup_path_entry.grid(row=9, column=1, padx=20, pady=5, sticky="ew")
        self.browse_button = customtkinter.CTkButton(
            self, text="Browse...", command=self.browse_directory
        )
        self.browse_button.grid(row=9, column=2, padx=(5, 20), pady=5)

        # Debug Settings
        self.debug_label = customtkinter.CTkLabel(
            self,
            text="Debug Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.debug_label.grid(
            row=10, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w"
        )
        self.log_level_label = customtkinter.CTkLabel(self, text="Log Level:")
        self.log_level_label.grid(row=11, column=0, padx=20, pady=5, sticky="w")
        self.log_level_menu = customtkinter.CTkOptionMenu(
            self, values=["Normal", "Debug"]
        )
        self.log_level_menu.grid(row=11, column=1, padx=20, pady=5, sticky="w")

        # Action Buttons
        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(
            row=12, column=1, columnspan=2, padx=20, pady=(20, 10), sticky="e"
        )
        self.save_button = customtkinter.CTkButton(
            self.button_frame, text="Save", command=self.save_and_close
        )
        self.save_button.pack(side="right", padx=(10, 0))
        self.cancel_button = customtkinter.CTkButton(
            self.button_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.cancel_button.pack(side="right")

        self.load_settings()

    def create_setting_row(self, label_text, row, help_info, show=None):
        frame = customtkinter.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, padx=(20, 0), pady=5, sticky="w")
        label = customtkinter.CTkLabel(frame, text=label_text)
        label.pack(side="left")
        command = (
            (lambda: self.open_link(help_info))
            if help_info.startswith("http")
            else (lambda: self.show_info_popup(label_text, help_info))
        )
        help_button = customtkinter.CTkButton(
            frame, text="?", width=20, height=20, command=command
        )
        help_button.pack(side="left", padx=5)
        entry = customtkinter.CTkEntry(self, show=show if show else None)
        entry.grid(row=row, column=1, columnspan=2, padx=20, pady=5, sticky="ew")
        setattr(
            self,
            f"{label_text.lower().replace(' ', '_').replace(':', '')}_entry",
            entry,
        )

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.backup_path_entry.delete(0, "end")
            self.backup_path_entry.insert(0, directory)

    def open_link(self, url):
        webbrowser.open_new_tab(url)

    def show_info_popup(self, title, message):
        messagebox.showinfo(title, message)

    def save_and_close(self):
        self.save_settings()
        self.destroy()

    def save_settings(self):
        keyring.set_password(
            SERVICE_NAME, "braze_api_key", self.braze_api_key_entry.get()
        )
        keyring.set_password(
            SERVICE_NAME, "transifex_api_token", self.transifex_api_token_entry.get()
        )
        config = {
            "braze_endpoint": self.braze_endpoint_entry.get(),
            "transifex_org": self.transifex_org_slug_entry.get(),
            "transifex_project": self.transifex_project_slug_entry.get(),
            "backup_enabled": self.backup_checkbox.get() == 1,
            "backup_path": self.backup_path_entry.get(),
            "log_level": self.log_level_menu.get(),
        }
        with open(CONFIG_FILE_NAME, "w") as f:
            json.dump(config, f, indent=4)

        # ADDED: Provide visual feedback to the user that the save was successful.
        messagebox.showinfo("Success", "Settings have been saved successfully.")

    def load_settings(self):
        try:
            with open(CONFIG_FILE_NAME, "r") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}

        braze_key = keyring.get_password(SERVICE_NAME, "braze_api_key")
        tx_token = keyring.get_password(SERVICE_NAME, "transifex_api_token")

        braze_endpoint = config.get("braze_endpoint", "https://rest.iad-05.braze.com")
        tx_org = config.get("transifex_org", "control4")
        tx_project = config.get("transifex_project", "braze")
        backup_enabled = config.get("backup_enabled", True)
        backup_path = config.get("backup_path", str(Path.home() / "Downloads"))
        log_level = config.get("log_level", "Normal")

        if braze_key:
            self.braze_api_key_entry.insert(0, braze_key)
        if tx_token:
            self.transifex_api_token_entry.insert(0, tx_token)
        self.braze_endpoint_entry.insert(0, braze_endpoint)
        self.transifex_org_slug_entry.insert(0, tx_org)
        self.transifex_project_slug_entry.insert(0, tx_project)
        self.backup_path_entry.insert(0, backup_path)
        if backup_enabled:
            self.backup_checkbox.select()
        self.log_level_menu.set(log_level)
