# gui_settings.py

import customtkinter
import keyring
import tkinter
import webbrowser
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import Any, Callable
import requests

from constants import (
    MANAGED_SETTINGS_KEYS,
    KEY_BRAZE_API,
    KEY_TX_API,
    KEY_BRAZE_ENDPOINT,
    KEY_TX_ORG,
    KEY_TX_PROJECT,
    KEY_BACKUP_PATH,
    KEY_LOG_LEVEL,
    KEY_BACKUP_ENABLED,
    KEY_AUTO_UPDATE,
    DEFAULT_AUTO_UPDATE_ENABLED,
    DEFAULT_BACKUP_ENABLED,
    DEFAULT_BACKUP_PATH_NAME,
    DEFAULT_LOG_LEVEL,
    TRANSIFEX_API_BASE_URL,
)
from config import SERVICE_NAME
from utils import resource_path


class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.title("Settings")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.geometry("600x640")
        self.grid_columnconfigure(1, weight=1)

        # --- Braze Settings ---
        self._create_section_header(
            "Braze Settings", 0, self._test_braze_connection_from_ui
        )
        self.braze_api_key_entry = self.create_setting_row(
            "Braze API Key:", 1, "...", show="*"
        )
        self.braze_endpoint_entry = self.create_setting_row("Braze Endpoint:", 2, "...")

        # --- Transifex Settings ---
        self._create_section_header(
            "Transifex Settings", 3, self._test_transifex_connection_from_ui
        )
        self.transifex_api_token_entry = self.create_setting_row(
            "Transifex API Token:", 4, "...", show="*"
        )
        self.transifex_org_slug_entry = self.create_setting_row(
            "Transifex Org Slug:", 5, "..."
        )
        self.transifex_project_slug_entry = self.create_setting_row(
            "Transifex Project Slug:", 6, "..."
        )

        # --- Updates Section ---
        self.update_label = customtkinter.CTkLabel(
            self,
            text="Application Updates",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.update_label.grid(
            row=7, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="w"
        )

        update_action_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        update_action_frame.grid(
            row=8, column=0, columnspan=2, padx=20, pady=0, sticky="ew"
        )
        update_action_frame.grid_columnconfigure(0, weight=1)

        self.update_checkbox = customtkinter.CTkCheckBox(
            update_action_frame,
            text="Automatically check for updates on startup",
            command=self._on_setting_change,
        )
        self.update_checkbox.pack(side="left")

        self.check_now_button = customtkinter.CTkButton(
            update_action_frame,
            text="Check for updates",
            command=self.trigger_update_check,
            width=150,
        )
        self.check_now_button.pack(side="right")

        # --- Backup Section ---
        self.backup_label = customtkinter.CTkLabel(
            self,
            text="Backup Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self.backup_label.grid(
            row=9, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="w"
        )

        self.backup_checkbox = customtkinter.CTkCheckBox(
            self, text="Backup TMX before sync", command=self._on_setting_change
        )
        self.backup_checkbox.grid(
            row=10, column=0, columnspan=2, padx=20, pady=5, sticky="w"
        )

        backup_dir_label = customtkinter.CTkLabel(self, text="Backup Directory:")
        backup_dir_label.grid(row=11, column=0, padx=(20, 10), pady=5, sticky="w")

        backup_entry_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        backup_entry_frame.grid(row=11, column=1, padx=(0, 20), pady=5, sticky="ew")
        backup_entry_frame.grid_columnconfigure(0, weight=1)

        self.backup_directory_entry = self._create_entry_with_trace(backup_entry_frame)
        self.backup_directory_entry.pack(side="left", fill="x", expand=True)

        self.browse_button = customtkinter.CTkButton(
            backup_entry_frame,
            text="Browse...",
            command=self.browse_directory,
            width=100,
        )
        self.browse_button.pack(side="left", padx=(5, 0))

        # --- Advanced Settings ---
        self.advanced_checkbox = customtkinter.CTkCheckBox(
            self, text="Show Advanced Settings", command=self.toggle_advanced_settings
        )
        self.advanced_checkbox.grid(
            row=12, column=0, columnspan=2, padx=20, pady=(20, 0), sticky="w"
        )

        self.advanced_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.advanced_frame.grid(
            row=13, column=0, columnspan=2, padx=0, pady=0, sticky="ew"
        )
        self.advanced_frame.grid_remove()  # Hidden by default

        debug_label = customtkinter.CTkLabel(
            self.advanced_frame,
            text="Debug Settings",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        debug_label.pack(anchor="w", padx=20, pady=(10, 5))

        log_level_frame = customtkinter.CTkFrame(
            self.advanced_frame, fg_color="transparent"
        )
        log_level_frame.pack(fill="x", padx=20, pady=5, anchor="w")

        log_level_label = customtkinter.CTkLabel(log_level_frame, text="Log Level:")
        log_level_label.pack(side="left")

        self.log_level_menu = customtkinter.CTkOptionMenu(
            log_level_frame, values=["Normal", "Debug"], command=self._on_setting_change
        )
        self.log_level_menu.pack(side="left", padx=10)

        self.reset_button = customtkinter.CTkButton(
            self.advanced_frame,
            text="Reset to Defaults",
            command=self.confirm_and_reset,
            fg_color="#D32F2F",
            hover_color="#B71C1C",
        )
        self.reset_button.pack(fill="x", padx=20, pady=10)

        # --- Bottom Button Bar ---
        self.bottom_button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.bottom_button_frame.grid(
            row=14, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="ew"
        )
        self.bottom_button_frame.grid_columnconfigure(0, weight=1)

        self.save_button = customtkinter.CTkButton(
            self.bottom_button_frame,
            text="Save",
            command=self.save_and_close,
            state="disabled",
        )
        self.save_button.pack(side="right")

        self.cancel_button = customtkinter.CTkButton(
            self.bottom_button_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.cancel_button.pack(side="right", padx=(0, 10))

        self.load_settings()

    def toggle_advanced_settings(self):
        if self.advanced_checkbox.get() == 1:
            self.advanced_frame.grid()
            self.geometry("600x720")
        else:
            self.advanced_frame.grid_remove()
            self.geometry("600x640")

    def _on_setting_change(self, *args: Any) -> None:
        self.save_button.configure(state="normal")

    def _create_entry_with_trace(
        self, parent, show: str | None = None
    ) -> customtkinter.CTkEntry:
        string_var = tkinter.StringVar()
        string_var.trace_add("write", self._on_setting_change)
        entry = customtkinter.CTkEntry(parent, textvariable=string_var, show=show)
        entry.string_var = string_var
        return entry

    def _create_section_header(
        self, text: str, row: int, test_command: Callable
    ) -> None:
        header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        header_frame.grid(
            row=row, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="ew"
        )
        header_frame.grid_columnconfigure(0, weight=1)

        label = customtkinter.CTkLabel(
            header_frame, text=text, font=customtkinter.CTkFont(size=14, weight="bold")
        )
        label.pack(side="left")

        button = customtkinter.CTkButton(
            header_frame, text="↻", width=28, height=28, command=test_command
        )
        button.pack(side="right")

    def create_setting_row(
        self, label_text: str, row: int, help_info: str, show: str | None = None
    ) -> customtkinter.CTkEntry:
        label = customtkinter.CTkLabel(self, text=label_text)
        label.grid(row=row, column=0, padx=(20, 10), pady=5, sticky="w")

        entry_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        entry_frame.grid(row=row, column=1, padx=(0, 20), pady=5, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        entry = self._create_entry_with_trace(entry_frame, show=show)
        entry.pack(side="left", fill="x", expand=True)

        def on_help_click():
            if help_info.startswith("http"):
                self.open_link(help_info)
            else:
                self.show_info_popup(label_text, help_info)

        help_button = customtkinter.CTkButton(
            entry_frame, text="?", width=28, height=28, command=on_help_click
        )
        help_button.pack(side="left", padx=(5, 0))

        return entry

    def browse_directory(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.backup_directory_entry.delete(0, "end")
            self.backup_directory_entry.insert(0, directory)

    def open_link(self, url: str) -> None:
        webbrowser.open_new_tab(url)

    def show_info_popup(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def trigger_update_check(self) -> None:
        if hasattr(self.master, "force_update_check"):
            self.master.force_update_check()
            messagebox.showinfo("Update Check Started", "See main window for progress.")
        else:
            messagebox.showerror("Error", "Could not trigger update check.")

    def save_and_close(self) -> None:
        self.save_settings()
        self.destroy()

    def save_settings(self) -> None:
        def set_key(key, value):
            return (
                keyring.set_password(SERVICE_NAME, key, value)
                if value
                else keyring.delete_password(SERVICE_NAME, key)
            )

        set_key(KEY_BRAZE_API, self.braze_api_key_entry.get())
        set_key(KEY_TX_API, self.transifex_api_token_entry.get())
        set_key(KEY_BRAZE_ENDPOINT, self.braze_endpoint_entry.get())
        set_key(KEY_TX_ORG, self.transifex_org_slug_entry.get())
        set_key(KEY_TX_PROJECT, self.transifex_project_slug_entry.get())
        set_key(KEY_BACKUP_PATH, self.backup_directory_entry.get())
        set_key(KEY_LOG_LEVEL, self.log_level_menu.get())
        set_key(KEY_BACKUP_ENABLED, "1" if self.backup_checkbox.get() else "0")
        set_key(KEY_AUTO_UPDATE, "1" if self.update_checkbox.get() else "0")
        self.save_button.configure(state="disabled")

    def load_settings(self) -> None:
        def get_setting(key, default=""):
            return keyring.get_password(SERVICE_NAME, key) or default

        self.braze_api_key_entry.insert(0, get_setting(KEY_BRAZE_API, ""))
        self.transifex_api_token_entry.insert(0, get_setting(KEY_TX_API, ""))
        self.braze_endpoint_entry.insert(0, get_setting(KEY_BRAZE_ENDPOINT, ""))
        self.transifex_org_slug_entry.insert(0, get_setting(KEY_TX_ORG, ""))
        self.transifex_project_slug_entry.insert(0, get_setting(KEY_TX_PROJECT, ""))
        self.backup_directory_entry.insert(
            0, get_setting(KEY_BACKUP_PATH, str(Path.home() / DEFAULT_BACKUP_PATH_NAME))
        )

        self.log_level_menu.set(get_setting(KEY_LOG_LEVEL, DEFAULT_LOG_LEVEL))
        backup_val = get_setting(KEY_BACKUP_ENABLED, str(int(DEFAULT_BACKUP_ENABLED)))
        self.backup_checkbox.select() if backup_val == "1" else self.backup_checkbox.deselect()
        update_val = get_setting(KEY_AUTO_UPDATE, str(int(DEFAULT_AUTO_UPDATE_ENABLED)))
        self.update_checkbox.select() if update_val == "1" else self.update_checkbox.deselect()

        self.save_button.configure(state="disabled")

    def confirm_and_reset(self) -> None:
        if messagebox.askyesno("Confirm Reset", "Are you sure?"):
            for key in MANAGED_SETTINGS_KEYS:
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordNotFoundError:
                    pass
            self.load_settings()
            messagebox.showinfo("Success", "All settings have been reset.")

    def _test_braze_connection_from_ui(self):
        key = self.braze_api_key_entry.get()
        endpoint = self.braze_endpoint_entry.get()
        status, msg = self._test_braze_connection(key, endpoint)
        messagebox.showinfo("Braze Connection Test", f"{status}: {msg}")

    def _test_transifex_connection_from_ui(self):
        token = self.transifex_api_token_entry.get()
        org = self.transifex_org_slug_entry.get()
        project = self.transifex_project_slug_entry.get()
        status, msg = self._test_transifex_connection(token, org, project)
        messagebox.showinfo("Transifex Connection Test", f"{status}: {msg}")

    def _test_braze_connection(self, api_key: str, endpoint: str) -> tuple[str, str]:
        if not api_key or not endpoint:
            return "SKIPPED", "Missing API Key or Endpoint."
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        try:
            response = session.get(
                f"{endpoint}/templates/email/list?limit=1", timeout=10
            )
            response.raise_for_status()
            return "SUCCESS", "Connected to Braze API."
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return "FAILED", "Invalid Braze API Key or Endpoint."
            return "FAILED", f"Braze API Error: {e.response.status_code}"
        except requests.exceptions.RequestException:
            return "FAILED", "Could not connect to Braze."

    def _test_transifex_connection(
        self, api_token: str, org_slug: str, project_slug: str
    ) -> tuple[str, str]:
        if not api_token or not org_slug or not project_slug:
            return "SKIPPED", "Missing API Token, Org, or Project Slug."
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/vnd.api+json",
            }
        )
        try:
            project_id = f"o:{org_slug}:p:{project_slug}"
            response = session.get(
                f"{TRANSIFEX_API_BASE_URL}/projects/{project_id}", timeout=10
            )
            response.raise_for_status()
            return "SUCCESS", "Connected to Transifex API & Project."
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return "FAILED", "Invalid Transifex API Token."
            elif e.response.status_code == 404:
                return "FAILED", "Transifex Org or Project Slug not found."
            return "FAILED", f"Transifex API Error: {e.response.status_code}"
        except requests.exceptions.RequestException:
            return "FAILED", "Could not connect to Transifex."
