# gui_settings.py

import customtkinter
import keyring
import webbrowser
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import Any

from config import SERVICE_NAME
from utils import resource_path


class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.title("Settings")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.geometry("600x680")
        self.grid_columnconfigure(1, weight=1)

        self.create_setting_row("Braze API Key:", 1, "...", show="*")
        self.create_setting_row("Braze Endpoint:", 2, "...")

        self.create_setting_row("Transifex API Token:", 4, "...", show="*")
        self.create_setting_row("Transifex Org Slug:", 5, "...")
        self.create_setting_row("Transifex Project Slug:", 6, "...")

        self.update_label = customtkinter.CTkLabel(
            self,
            text="Application Updates",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.update_label.grid(
            row=7, column=0, columnspan=3, padx=20, pady=(20, 5), sticky="w"
        )
        self.update_checkbox = customtkinter.CTkCheckBox(
            self, text="Automatically check for updates on startup"
        )
        self.update_checkbox.grid(
            row=8, column=0, columnspan=3, padx=20, pady=5, sticky="w"
        )

        self.backup_label = customtkinter.CTkLabel(
            self,
            text="Backup Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.backup_label.grid(
            row=9, column=0, columnspan=3, padx=20, pady=(20, 5), sticky="w"
        )
        self.backup_checkbox = customtkinter.CTkCheckBox(
            self, text="Backup TMX before sync"
        )
        self.backup_checkbox.grid(
            row=10, column=0, columnspan=3, padx=20, pady=5, sticky="w"
        )
        self.backup_path_label = customtkinter.CTkLabel(self, text="Backup Directory:")
        self.backup_path_label.grid(row=11, column=0, padx=20, pady=5, sticky="w")
        self.backup_path_entry = customtkinter.CTkEntry(self)
        self.backup_path_entry.grid(row=11, column=1, padx=20, pady=5, sticky="ew")
        self.browse_button = customtkinter.CTkButton(
            self, text="Browse...", command=self.browse_directory
        )
        self.browse_button.grid(row=11, column=2, padx=(5, 20), pady=5)

        self.debug_label = customtkinter.CTkLabel(
            self,
            text="Debug Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.debug_label.grid(
            row=12, column=0, columnspan=3, padx=20, pady=(20, 5), sticky="w"
        )
        self.log_level_label = customtkinter.CTkLabel(self, text="Log Level:")
        self.log_level_label.grid(row=13, column=0, padx=20, pady=5, sticky="w")
        self.log_level_menu = customtkinter.CTkOptionMenu(
            self, values=["Normal", "Debug"]
        )
        self.log_level_menu.grid(row=13, column=1, padx=20, pady=5, sticky="w")

        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(
            row=14, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="ew"
        )
        self.button_frame.grid_columnconfigure(0, weight=1)
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

    def create_setting_row(
        self, label_text: str, row: int, help_info: str, show: str | None = None
    ) -> None:
        frame = customtkinter.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, padx=(20, 0), pady=5, sticky="w")
        label = customtkinter.CTkLabel(frame, text=label_text)
        label.pack(side="left")

        def on_help_click() -> None:
            """Handles click event for the help button."""
            if help_info.startswith("http"):
                self.open_link(help_info)
            else:
                self.show_info_popup(label_text, help_info)

        help_button = customtkinter.CTkButton(
            frame, text="?", width=20, height=20, command=on_help_click
        )
        help_button.pack(side="left", padx=5)

        entry = customtkinter.CTkEntry(self, show=show if show else None)
        entry.grid(row=row, column=1, columnspan=2, padx=20, pady=5, sticky="ew")
        entry_attr_name = (
            f"{label_text.lower().replace(' ', '_').replace(':', '')}_entry"
        )
        setattr(self, entry_attr_name, entry)

    def browse_directory(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.backup_path_entry.delete(0, "end")
            self.backup_path_entry.insert(0, directory)

    def open_link(self, url: str) -> None:
        webbrowser.open_new_tab(url)

    def show_info_popup(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def save_and_close(self) -> None:
        self.save_settings()
        self.destroy()

    def save_settings(self) -> None:
        def set_key(key: str, value: str) -> None:
            if value:
                keyring.set_password(SERVICE_NAME, key, value)
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordNotFoundError:
                    pass

        set_key("braze_api_key", self.braze_api_key_entry.get())
        set_key("transifex_api_token", self.transifex_api_token_entry.get())
        set_key("braze_endpoint", self.braze_endpoint_entry.get())
        set_key("transifex_org", self.transifex_org_slug_entry.get())
        set_key("transifex_project", self.transifex_project_slug_entry.get())
        set_key("backup_path", self.backup_path_entry.get())
        set_key("log_level", self.log_level_menu.get())
        set_key("backup_enabled", "1" if self.backup_checkbox.get() else "0")
        set_key("auto_update_enabled", "1" if self.update_checkbox.get() else "0")

    def load_settings(self) -> None:
        self.braze_api_key_entry.delete(0, "end")
        self.transifex_api_token_entry.delete(0, "end")
        self.braze_endpoint_entry.delete(0, "end")
        self.transifex_org_slug_entry.delete(0, "end")
        self.transifex_project_slug_entry.delete(0, "end")
        self.backup_path_entry.delete(0, "end")

        self.braze_api_key_entry.insert(
            0, keyring.get_password(SERVICE_NAME, "braze_api_key") or ""
        )
        self.transifex_api_token_entry.insert(
            0, keyring.get_password(SERVICE_NAME, "transifex_api_token") or ""
        )
        self.braze_endpoint_entry.insert(
            0, keyring.get_password(SERVICE_NAME, "braze_endpoint") or ""
        )
        self.transifex_org_slug_entry.insert(
            0, keyring.get_password(SERVICE_NAME, "transifex_org") or ""
        )
        self.transifex_project_slug_entry.insert(
            0, keyring.get_password(SERVICE_NAME, "transifex_project") or ""
        )
        self.backup_path_entry.insert(
            0,
            keyring.get_password(SERVICE_NAME, "backup_path")
            or str(Path.home() / "Downloads"),
        )
        self.log_level_menu.set(
            keyring.get_password(SERVICE_NAME, "log_level") or "Normal"
        )

        if (keyring.get_password(SERVICE_NAME, "backup_enabled") or "1") == "1":
            self.backup_checkbox.select()
        else:
            self.backup_checkbox.deselect()

        if (keyring.get_password(SERVICE_NAME, "auto_update_enabled") or "1") == "1":
            self.update_checkbox.select()
        else:
            self.update_checkbox.deselect()

    def confirm_and_reset(self) -> None:
        answer = messagebox.askyesno(
            "Confirm Reset", "Are you sure you want to delete all saved settings?"
        )
        if answer:
            keys_to_delete = [
                "braze_api_key",
                "transifex_api_token",
                "braze_endpoint",
                "transifex_org",
                "transifex_project",
                "backup_path",
                "log_level",
                "backup_enabled",
                "auto_update_enabled",
            ]
            for key in keys_to_delete:
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordNotFoundError:
                    pass
            self.load_settings()
            messagebox.showinfo("Success", "All settings have been reset.")
