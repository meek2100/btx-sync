# app.py

import customtkinter
import keyring
import threading
import tkinter
import sys
import shutil
import platform
import os
from tkinter import messagebox
from pathlib import Path
from PIL import Image
from customtkinter import CTkImage

# tufup is used for secure, signed updates
from tufup.client import Client

from constants import (
    DEV_AUTO_UPDATE_ENABLED,
    DEFAULT_AUTO_UPDATE_ENABLED,
    DEFAULT_BACKUP_ENABLED,
    DEFAULT_BACKUP_PATH_NAME,
    DEFAULT_LOG_LEVEL,
    MANAGED_SETTINGS_KEYS,
    KEY_BACKUP_ENABLED,
    KEY_AUTO_UPDATE,
    KEY_LOG_LEVEL,
    KEY_BACKUP_PATH,
    PLATFORM_SUFFIXES,
)
from config import SERVICE_NAME
from gui_settings import SettingsWindow
from gui_help import HelpWindow
from sync_logic import sync_logic_main, SyncState, STATE_FILE_PATH
from utils import resource_path, is_production_environment
from logger import AppLogger

try:
    from version import __version__ as APP_VERSION  # type: ignore
except ImportError:
    APP_VERSION = "0.0.0-dev"

# Define the custom windows batch template with a restart command
WIN_RESTART_BATCH_TEMPLATE = """@echo off
echo Moving app files...
robocopy "{src_dir}" "{dst_dir}" {robocopy_options}
echo Relaunching application...
start "" "{dst_dir}\\btx-sync.exe"
echo Done.
{delete_self}
"""

APP_NAME = "btx-sync"
UPDATE_URL = "https://meek2100.github.io/btx-sync/"


def check_for_updates(app_instance: "App") -> None:
    """
    Initializes the tufup client and checks for application updates.
    Includes logic to automatically clear the cache and retry if expired
    metadata is found.
    """
    logger = AppLogger(
        app_instance.log_message,
        app_instance.get_current_config().get("LOG_LEVEL", "Normal"),
    )
    logger.debug("Checking for updates...")
    platform_system = platform.system().lower()
    platform_suffix = PLATFORM_SUFFIXES.get(platform_system, "linux")
    platform_app_name = f"{APP_NAME}-{platform_suffix}"
    logger.debug(f"Platform: {platform_system}, App Name: {platform_app_name}")

    # Define and create local directories for update assets
    app_data_dir = Path.home() / f".{APP_NAME}"
    app_data_dir.mkdir(exist_ok=True)
    metadata_dir = app_data_dir / "metadata"
    target_dir = app_data_dir / "targets"
    metadata_dir.mkdir(exist_ok=True)
    target_dir.mkdir(exist_ok=True)

    # On first run, copy the bundled root.json to the local cache
    local_root_path = metadata_dir / "root.json"
    if not local_root_path.exists():
        try:
            bundled_root_path = resource_path("repository/metadata/root.json")
            shutil.copy(bundled_root_path, local_root_path)
            logger.debug("Initial root.json copied.")
        except Exception as e:
            logger.error(f"Failed to initialize update metadata: {repr(e)}")
            return

    # Initialize the tufup client
    try:
        platform_update_url = f"{UPDATE_URL}{platform_suffix}/"
        client = Client(
            app_name=platform_app_name,
            app_install_dir=Path(sys.executable).parent,
            current_version=APP_VERSION,
            metadata_dir=metadata_dir,
            target_dir=target_dir,
            metadata_base_url=f"{platform_update_url}metadata/",
            target_base_url=f"{platform_update_url}targets/",
        )
        logger.debug(f"tufup.Client(current_version='{APP_VERSION}')")
    except Exception as e:
        logger.error(f"Failed to initialize update client: {repr(e)}")
        return

    # Check for updates, with cache-clearing retry logic
    new_update = None
    try:
        new_update = client.check_for_updates(pre="a")
    except Exception as e:
        # If metadata is expired, clear cache and retry once
        if "ExpiredMetadataError" in repr(e):
            logger.error(f"Expired metadata detected: {e}")
            logger.info("Clearing cache and retrying update check...")

            # Delete all .json files except the trusted root.json
            for f_path in metadata_dir.glob("*.json"):
                if f_path.name != "root.json":
                    try:
                        f_path.unlink()
                    except OSError as unlink_error:
                        logger.error(f"Failed to remove {f_path.name}: {unlink_error}")

            # Retry the check
            try:
                new_update = client.check_for_updates(pre="a")
            except Exception as retry_e:
                logger.error(f"Update check failed on retry: {repr(retry_e)}")
        else:
            logger.error(f"Update check failed: {repr(e)}")

    if new_update:
        logger.debug(f"Update {new_update.version} found.")
        app_instance.tufup_client = client
        app_instance.new_update_info = new_update
        app_instance.show_update_notification()
    else:
        logger.debug("Application is up to date.")


def cleanup_old_updates() -> None:
    install_dir = Path(sys.executable).parent
    for old_file in install_dir.glob("*.old"):
        try:
            old_file.unlink()
            print(f"Removed old update file: {old_file.name}")
        except OSError:
            pass


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("btx sync")
        self.geometry("800x600")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.sync_thread = None
        self.update_frame = customtkinter.CTkFrame(self, fg_color="#2B39B2")
        self.update_label = customtkinter.CTkLabel(
            self.update_frame, text="A new version is available!"
        )
        self.update_label.pack(side="left", padx=20, pady=5)
        self.update_button = customtkinter.CTkButton(
            self.update_frame, text="Install Now", command=self.apply_update
        )
        self.update_button.pack(side="right", padx=10, pady=5)
        self.new_update_info = None
        self.tufup_client = None

        self.control_frame = customtkinter.CTkFrame(self, height=50)
        self.control_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.control_frame.grid_columnconfigure(2, weight=1)

        self.run_button = customtkinter.CTkButton(
            self.control_frame,
            text="Run Sync",
            command=self.start_sync_thread,
        )
        self.run_button.pack(side="left", padx=10, pady=5)
        self.cancel_button = customtkinter.CTkButton(
            self.control_frame,
            text="Cancel",
            command=self.cancel_sync,
            fg_color="transparent",
            border_width=1,
        )
        self.cancel_event = threading.Event()
        self.status_label = customtkinter.CTkLabel(
            self.control_frame, text="Loading..."
        )
        self.status_label.pack(side="left", padx=10)
        self.progress_bar = customtkinter.CTkProgressBar(self.control_frame)

        self.more_icon = CTkImage(
            light_image=Image.open(resource_path("assets/dots_dark.png")),
            dark_image=Image.open(resource_path("assets/dots_light.png")),
            size=(20, 20),
        )
        self.more_button = customtkinter.CTkButton(
            self.control_frame,
            text="",
            image=self.more_icon,
            width=28,
            height=28,
            fg_color="transparent",
            border_width=0,
            command=self.show_more_menu,
        )
        self.more_button.pack(side="right", padx=10, pady=5)

        # New label for detailed status
        self.detail_status_label = customtkinter.CTkLabel(
            self, text="", text_color="gray", anchor="w"
        )
        self.detail_status_label.grid(
            row=3, column=0, padx=10, pady=(0, 5), sticky="ew"
        )

        self.log_box = customtkinter.CTkTextbox(
            self, state="disabled", font=("Courier New", 12)
        )
        self.log_box.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.more_menu = tkinter.Menu(self, tearoff=0)
        self.more_menu.add_command(label="Settings", command=self.open_settings)
        self.more_menu.add_command(label="Help", command=self.open_help_file)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="About", command=self.open_about_window)
        self.more_menu.add_separator()
        self.more_menu.add_command(
            label="Check for updates", command=self.force_update_check
        )
        self.right_click_menu = tkinter.Menu(
            self.log_box,
            tearoff=0,
            background="#2B2B2B",
            foreground="white",
        )
        self.right_click_menu.add_command(label="Copy", command=self.copy_log_text)
        self.right_click_menu.add_separator()
        self.right_click_menu.add_command(
            label="Select All", command=self.select_all_log_text
        )
        self.log_box.bind("<Button-3>", self.show_right_click_menu)

        self.settings_window = None
        self.help_window = None

        self.update_readiness_status()
        config = self.get_current_config()
        in_prod = is_production_environment()
        prod_update_enabled = in_prod and config.get("AUTO_UPDATE_ENABLED", True)
        dev_update_enabled = not in_prod and DEV_AUTO_UPDATE_ENABLED
        if prod_update_enabled or dev_update_enabled:
            update_thread = threading.Thread(
                target=check_for_updates, args=(self,), daemon=True
            )
            update_thread.start()

    def on_closing(self):
        """Handle the window closing event."""
        if self.sync_thread and self.sync_thread.is_alive():
            if messagebox.askyesno(
                "Exit",
                "A sync is currently in progress. Are you sure you want to exit?",
            ):
                self.destroy()
        else:
            self.destroy()

    def show_update_notification(self) -> None:
        self.update_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

    def apply_update(self) -> None:
        if not self.new_update_info:
            return
        self.update_button.configure(state="disabled", text="Installing...")
        update_thread = threading.Thread(target=self.threaded_apply, daemon=True)
        update_thread.start()

    def threaded_apply(self) -> None:
        if not self.tufup_client:
            self.log_message("[ERROR] Update client not initialized.")
            self.update_button.configure(state="normal", text="Install Now")
            return
        try:
            self.log_message(
                f"Downloading and applying update {self.new_update_info.version}..."
            )

            # Create a dictionary for keyword arguments
            update_kwargs = {"skip_confirmation": True}

            # If on Windows, add our custom batch template to the arguments
            if platform.system() == "Windows":
                update_kwargs["batch_template"] = WIN_RESTART_BATCH_TEMPLATE

            # Call the update method with our arguments
            self.tufup_client.download_and_apply_update(**update_kwargs)

        except SystemExit:
            # This is expected. tufup calls sys.exit(), which we catch.
            # Now, we must exit the entire process.
            os._exit(0)
        except Exception as e:
            self.log_message(f"[ERROR] An unexpected error occurred during update: {e}")
            self.update_button.configure(state="normal", text="Install Now")

    def get_current_config(self) -> dict:
        config = {}
        for key in MANAGED_SETTINGS_KEYS:
            config[key] = keyring.get_password(SERVICE_NAME, key)
        if not config.get(KEY_BACKUP_PATH):
            config[KEY_BACKUP_PATH] = str(Path.home() / DEFAULT_BACKUP_PATH_NAME)
        if not config.get(KEY_LOG_LEVEL):
            config[KEY_LOG_LEVEL] = DEFAULT_LOG_LEVEL
        if config.get(KEY_BACKUP_ENABLED) is None:
            config[KEY_BACKUP_ENABLED] = str(int(DEFAULT_BACKUP_ENABLED))
        if config.get(KEY_AUTO_UPDATE) is None:
            config[KEY_AUTO_UPDATE] = str(int(DEFAULT_AUTO_UPDATE_ENABLED))
        config["BACKUP_ENABLED"] = config[KEY_BACKUP_ENABLED] == "1"
        config["AUTO_UPDATE_ENABLED"] = config[KEY_AUTO_UPDATE] == "1"
        return config

    def update_readiness_status(self) -> None:
        config = self.get_current_config()
        is_ready = all([config.get("BRAZE_API_KEY"), config.get("TRANSIFEX_API_TOKEN")])
        base_status = "Ready" if is_ready else "Configuration required"
        self.run_button.configure(state="normal" if is_ready else "disabled")
        debug_suffix = " (Debug)" if config.get("LOG_LEVEL") == "Debug" else ""
        self.status_label.configure(text=f"{base_status}{debug_suffix}")
        self.detail_status_label.configure(text="")

    def show_more_menu(self) -> None:
        x = self.more_button.winfo_rootx()
        y = self.more_button.winfo_rooty() + self.more_button.winfo_height()
        self.more_menu.tk_popup(x, y)

    def open_about_window(self) -> None:
        messagebox.showinfo(
            "About btx sync",
            f"Version: {APP_VERSION}\n\n"
            "A cross-platform desktop application for synchronizing content "
            "from Braze to Transifex for translation.",
        )

    def open_help_file(self) -> None:
        """
        Opens the in-app help window. If a window already exists, it focuses
        it; otherwise, it creates a new one.
        """
        if self.help_window is None or not self.help_window.winfo_exists():
            self.help_window = HelpWindow(self)
            self.help_window.grab_set()
        else:
            self.help_window.focus()

    def show_right_click_menu(self, event) -> None:
        self.right_click_menu.tk_popup(event.x_root, event.y_root)

    def copy_log_text(self) -> None:
        try:
            self.clipboard_append(self.log_box.get("sel.first", "sel.last"))
        except tkinter.TclError:
            pass

    def select_all_log_text(self) -> str:
        self.log_box.tag_add("sel", "1.0", "end")
        return "break"

    def log_message(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def update_progress(self, current_value: int, max_value: int) -> None:
        if max_value > 0:
            # Throttle progress updates to avoid UI lag
            if (
                current_value % 10 == 0
                or current_value == max_value
                or current_value == 1
            ):
                progress = float(current_value) / max_value
                self.progress_bar.set(progress)

    def update_status_label(self, message: str) -> None:
        """Updates the detailed status label with the current operation."""
        self.detail_status_label.configure(text=message)

    def cancel_sync(self):
        self.status_label.configure(text="Cancelling...")
        self.cancel_button.configure(state="disabled")
        self.cancel_event.set()

    def sync_thread_target(self, resume: bool = False):
        self.progress_bar.pack(side="left", padx=(10, 5), fill="x", expand=True)
        self.progress_bar.set(0)
        self.run_button.pack_forget()
        self.cancel_button.pack(side="left", padx=10, pady=5)
        self.cancel_button.configure(state="normal")
        self.status_label.configure(text="Running...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        config = self.get_current_config()
        try:
            if all(
                [
                    config["BRAZE_API_KEY"],
                    config["TRANSIFEX_API_TOKEN"],
                ]
            ):
                sync_logic_main(
                    config,
                    self.log_message,
                    self.cancel_event,
                    self.update_progress,
                    self.update_status_label,
                    resume=resume,
                )
            else:
                self.log_message("--- CONFIGURATION ERROR ---")
        finally:
            self.progress_bar.pack_forget()
            self.cancel_button.pack_forget()
            self.run_button.pack(side="left", padx=10, pady=5)
            status = "Cancelled" if self.cancel_event.is_set() else None
            self.update_readiness_status()
            if status:
                self.status_label.configure(text=status)
            self.log_message("\n")

    def start_sync_thread(self):
        self.cancel_event.clear()
        resume = False
        if STATE_FILE_PATH.exists():
            answer = messagebox.askyesnocancel(
                "Resume Sync?",
                "An incomplete sync session was found. "
                "Do you want to resume where you left off?\n\n"
                "• Yes: Resume the sync.\n"
                "• No: Start a new sync and delete the old session.\n"
                "• Cancel: Do nothing.",
                icon=messagebox.QUESTION,
            )
            if answer is None:  # Cancel
                return
            if answer:  # Yes
                resume = True
            else:  # No
                SyncState.clear()

        self.sync_thread = threading.Thread(
            target=self.sync_thread_target, kwargs={"resume": resume}, daemon=True
        )
        self.sync_thread.start()

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
            self.settings_window.grab_set()
            self.wait_window(self.settings_window)
            self.update_readiness_status()
        else:
            self.settings_window.focus()

    def force_update_check(self):
        """Forces an update check to be performed."""
        self.log_message("\n--- Manual update check initiated ---")
        update_thread = threading.Thread(
            target=check_for_updates, args=(self,), daemon=True
        )
        update_thread.start()


if __name__ == "__main__":
    if is_production_environment():
        cleanup_old_updates()
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = App()
    app.mainloop()
