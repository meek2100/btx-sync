# gui_settings.py

import customtkinter
import keyring
import webbrowser
from tkinter import messagebox, filedialog
from pathlib import Path

from config import SERVICE_NAME
from utils import resource_path


class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Settings")

        # ADDED: Set the window icon to match the main application
        self.iconbitmap(resource_path("assets/icon.ico"))

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

        # --- Action Buttons ---
        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(
            row=12, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="ew"
        )
        self.button_frame.grid_columnconfigure(
            0, weight=1
        )  # Make left column expandable

        self.reset_button = customtkinter.CTkButton(
            self.button_frame,
            text="Reset to Defaults",
            command=self.confirm_and_reset,
            fg_color="#D32F2F",
            hover_color="#B71C1C",
        )
        self.reset_button.pack(side="left", padx=(0, 10))

        self.save_button = customtkinter.CTkButton(
            self.button_frame, text="Save", command=self.save_and_close
        )
        self.save_button.pack(side="right")

        self.cancel_button = customtkinter.CTkButton(
            self.button_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.cancel_button.pack(side="right", padx=(0, 10))

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
        """Saves all settings to the system keychain."""

        # Helper to set a password or delete it if empty
        def set_key(key, value):
            if value:
                keyring.set_password(SERVICE_NAME, key, value)
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordNotFoundError:
                    pass  # It's okay if it doesn't exist

        # Save API keys
        set_key("braze_api_key", self.braze_api_key_entry.get())
        set_key("transifex_api_token", self.transifex_api_token_entry.get())

        # Save other settings
        set_key("braze_endpoint", self.braze_endpoint_entry.get())
        set_key("transifex_org", self.transifex_org_slug_entry.get())
        set_key("transifex_project", self.transifex_project_slug_entry.get())
        set_key("backup_path", self.backup_path_entry.get())
        set_key("log_level", self.log_level_menu.get())

        # Save boolean as a string "1" or "0"
        backup_enabled_value = "1" if self.backup_checkbox.get() == 1 else "0"
        set_key("backup_enabled", backup_enabled_value)

        messagebox.showinfo("Success", "Settings have been saved successfully.")

    def load_settings(self):
        """Loads all settings from the system keychain after clearing current values."""
        # --- Clear all existing fields before loading ---
        entry_widgets = [
            self.braze_api_key_entry,
            self.transifex_api_token_entry,
            self.braze_endpoint_entry,
            self.transifex_org_slug_entry,
            self.transifex_project_slug_entry,
            self.backup_path_entry,
        ]
        for entry in entry_widgets:
            entry.delete(0, "end")
        # --- End of added block ---

        # Load API Keys
        braze_key = keyring.get_password(SERVICE_NAME, "braze_api_key") or ""
        tx_token = keyring.get_password(SERVICE_NAME, "transifex_api_token") or ""
        if braze_key:
            self.braze_api_key_entry.insert(0, braze_key)
        if tx_token:
            self.transifex_api_token_entry.insert(0, tx_token)

        # MODIFIED: Removed hardcoded default values
        braze_endpoint = keyring.get_password(SERVICE_NAME, "braze_endpoint") or ""
        tx_org = keyring.get_password(SERVICE_NAME, "transifex_org") or ""
        tx_project = keyring.get_password(SERVICE_NAME, "transifex_project") or ""

        # These defaults are fine
        backup_path = keyring.get_password(SERVICE_NAME, "backup_path") or str(
            Path.home() / "Downloads"
        )
        log_level = keyring.get_password(SERVICE_NAME, "log_level") or "Normal"
        backup_enabled = keyring.get_password(SERVICE_NAME, "backup_enabled") or "1"

        # Populate UI
        self.braze_endpoint_entry.insert(0, braze_endpoint)
        self.transifex_org_slug_entry.insert(0, tx_org)
        self.transifex_project_slug_entry.insert(0, tx_project)
        self.backup_path_entry.insert(0, backup_path)
        if backup_enabled == "1":
            self.backup_checkbox.select()
        else:
            self.backup_checkbox.deselect()
        self.log_level_menu.set(log_level)

    def confirm_and_reset(self):
        """Shows a confirmation dialog and resets all settings if confirmed."""
        answer = messagebox.askyesno(
            "Confirm Reset",
            "Are you sure you want to delete all saved settings and reset to defaults?\n\nThis action cannot be undone.",
        )
        if answer:
            # List of all keys we use in keyring
            keys_to_delete = [
                "braze_api_key",
                "transifex_api_token",
                "braze_endpoint",
                "transifex_org",
                "transifex_project",
                "backup_path",
                "log_level",
                "backup_enabled",
            ]
            for key in keys_to_delete:
                try:
                    # Attempt to delete each key
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordNotFoundError:
                    # It's okay if the key doesn't exist, just continue
                    pass

            # Reload the settings window to clear fields and show defaults
            self.load_settings()
            messagebox.showinfo(
                "Success", "All settings have been reset to their default values."
            )
