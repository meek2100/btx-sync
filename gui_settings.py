# gui_settings.py

import customtkinter
import keyring
import webbrowser
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import Any
import requests

from constants import (
    DEFAULT_AUTO_UPDATE_ENABLED,
    DEFAULT_BACKUP_ENABLED,
    DEFAULT_BACKUP_PATH_NAME,
    DEFAULT_BRAZE_REST_ENDPOINT,
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

        # --- Button Frame (Updated) ---
        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(
            row=14, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="ew"
        )
        self.button_frame.grid_columnconfigure(0, weight=1)

        self.test_connection_button = customtkinter.CTkButton(
            self.button_frame,
            text="Test Connections",
            command=self.test_connections,
        )
        self.test_connection_button.pack(side="left", padx=(0, 10))

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
        # --- End Button Frame Update ---

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
            0,
            keyring.get_password(SERVICE_NAME, "braze_endpoint")
            or DEFAULT_BRAZE_REST_ENDPOINT,
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
            or str(Path.home() / DEFAULT_BACKUP_PATH_NAME),
        )
        self.log_level_menu.set(
            keyring.get_password(SERVICE_NAME, "log_level") or DEFAULT_LOG_LEVEL
        )

        backup_enabled_val = keyring.get_password(SERVICE_NAME, "backup_enabled")
        if (backup_enabled_val or str(int(DEFAULT_BACKUP_ENABLED))) == "1":
            self.backup_checkbox.select()
        else:
            self.backup_checkbox.deselect()

        auto_update_enabled_val = keyring.get_password(
            SERVICE_NAME, "auto_update_enabled"
        )
        if (auto_update_enabled_val or str(int(DEFAULT_AUTO_UPDATE_ENABLED))) == "1":
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

    def test_connections(self) -> None:
        """Tests the Braze and Transifex API connections using current input."""
        braze_key = self.braze_api_key_entry.get()
        braze_endpoint = self.braze_endpoint_entry.get()
        tx_token = self.transifex_api_token_entry.get()
        tx_org = self.transifex_org_slug_entry.get()
        tx_project = self.transifex_project_slug_entry.get()

        results = []

        # Test Braze Connection
        braze_status, braze_msg = self._test_braze_connection(braze_key, braze_endpoint)
        results.append(f"Braze Connection: {braze_status} - {braze_msg}")

        # Test Transifex Connection
        transifex_status, transifex_msg = self._test_transifex_connection(
            tx_token, tx_org, tx_project
        )
        results.append(f"Transifex Connection: {transifex_status} - {transifex_msg}")

        messagebox.showinfo("Connection Test Results", "\n".join(results))

    def _test_braze_connection(self, api_key: str, endpoint: str) -> tuple[str, str]:
        if not api_key or not endpoint:
            return "SKIPPED", "Missing API Key or Endpoint."
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        try:
            # Use a lightweight endpoint, e.g., fetching a small list
            response = session.get(
                f"{endpoint}/templates/email/list?limit=1", timeout=10
            )
            response.raise_for_status()
            return "SUCCESS", "Connected to Braze API."
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return "FAILED", "Invalid Braze API Key or Endpoint."
            return "FAILED", f"Braze API Error: {e.response.status_code}"
        except requests.exceptions.ConnectionError:
            return "FAILED", "Could not connect to Braze endpoint."
        except requests.exceptions.Timeout:
            return "FAILED", "Braze connection timed out."
        except Exception as e:
            return "FAILED", f"An unexpected error testing Braze: {e}"

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
            # Use a lightweight endpoint to check project existence
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
                return ("FAILED", "Transifex Org or Project Slug not found/accessible.")
            return "FAILED", f"Transifex API Error: {e.response.status_code}"
        except requests.exceptions.ConnectionError:
            return "FAILED", "Could not connect to Transifex endpoint."
        except requests.exceptions.Timeout:
            return "FAILED", "Transifex connection timed out."
        except Exception as e:
            return "FAILED", f"An unexpected error testing Transifex: {e}"
