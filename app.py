# app.py
import customtkinter
import keyring
import threading
import tkinter
import webbrowser
import sys
import shutil
from pathlib import Path
from PIL import Image
from customtkinter import CTkImage
from tufup.client import Client
from logger import AppLogger

# Import from our other modules
from constants import (
    DEFAULT_AUTO_UPDATE_ENABLED,
    DEFAULT_BACKUP_ENABLED,
    DEFAULT_BACKUP_PATH_NAME,
    DEFAULT_LOG_LEVEL,
    NEXT_RELEASE_VERSION,
)
from config import SERVICE_NAME
from gui_settings import SettingsWindow
from sync_logic import sync_logic_main
from utils import resource_path, is_production_environment

# --- Dynamic Version Configuration ---
try:
    # This file is created by the build process (see release.yml)
    from version import __version__ as APP_VERSION  # type: ignore
except ImportError:
    # Fallback for local development
    APP_VERSION = f"{NEXT_RELEASE_VERSION}-dev"

# --- Tufup Configuration ---
APP_NAME = "btx-sync"
UPDATE_URL = "https://meek2100.github.io/btx-sync/"


def check_for_updates(log_callback: callable, config: dict):
    """Checks for app updates using tufup and applies them."""
    # Use the existing AppLogger for tiered logging
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("Checking for updates...")

    # Create a dedicated directory for app data if it doesn't exist
    app_data_dir = Path.home() / f".{APP_NAME}"
    app_data_dir.mkdir(exist_ok=True)

    # Define the required tufup paths
    metadata_dir = app_data_dir / "metadata"
    target_dir = app_data_dir / "targets"

    local_root_path = metadata_dir / "root.json"
    if not local_root_path.exists():
        try:
            bundled_root_path = resource_path("repository/metadata/root.json")
            metadata_dir.mkdir(exist_ok=True)
            shutil.copy(bundled_root_path, local_root_path)
            logger.debug("Initial root.json copied to metadata directory.")
        except Exception as e:
            logger.error(f"Failed to initialize update metadata: {e}")
            return

    try:
        # Log the parameters being sent to the client in debug mode
        logger.debug(f"tufup.Client(app_name='{APP_NAME}')")
        logger.debug(f"tufup.Client(current_version='{APP_VERSION}')")
        logger.debug(f"tufup.Client(metadata_dir='{metadata_dir}')")

        client = Client(
            app_name=APP_NAME,
            app_install_dir=Path(sys.executable).parent,
            current_version=APP_VERSION,
            metadata_dir=metadata_dir,
            target_dir=target_dir,
            metadata_base_url=f"{UPDATE_URL}",
            target_base_url=f"{UPDATE_URL}targets/",
        )

        new_update = client.check_for_updates()

        if new_update:
            logger.info(f"Update {new_update.version} found, downloading...")
            if new_update.download_and_install():
                logger.info("Update successful. Restarting application...")
            else:
                logger.error("Update download or installation failed.")
        else:
            logger.info("Application is up to date.")

    except Exception as e:
        logger.error(f"Update check failed: {e}")


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("btx sync")
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

        self.cancel_button = customtkinter.CTkButton(
            self.control_frame,
            text="Cancel",
            command=self.cancel_sync,
            fg_color="transparent",
            border_width=1,
        )

        self.cancel_event = threading.Event()

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

        self.status_label = customtkinter.CTkLabel(
            self.control_frame, text="Loading..."
        )
        self.status_label.pack(side="left", padx=10)

        self.log_box = customtkinter.CTkTextbox(
            self, state="disabled", font=("Courier New", 12)
        )
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.more_menu = tkinter.Menu(self, tearoff=0)
        self.more_menu.add_command(label="Settings", command=self.open_settings)
        self.more_menu.add_command(label="Help", command=self.open_help_file)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="About", command=self.open_about_window)

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

        self.update_readiness_status()

        config = self.get_current_config()
        if is_production_environment() and config.get("AUTO_UPDATE_ENABLED", True):
            # Pass the config dictionary to the update thread
            update_thread = threading.Thread(
                target=check_for_updates, args=(self.log_message, config), daemon=True
            )
            update_thread.start()
        elif not is_production_environment():
            self.log_message("Auto-update check disabled in development mode.")

    def get_current_config(self):
        """
        Loads all settings from the system keychain and returns them as a
        dictionary.
        """
        config = {}
        config["BRAZE_API_KEY"] = keyring.get_password(SERVICE_NAME, "braze_api_key")
        config["TRANSIFEX_API_TOKEN"] = keyring.get_password(
            SERVICE_NAME, "transifex_api_token"
        )
        config["BRAZE_REST_ENDPOINT"] = (
            keyring.get_password(SERVICE_NAME, "braze_endpoint") or ""
        )
        config["TRANSIFEX_ORGANIZATION_SLUG"] = (
            keyring.get_password(SERVICE_NAME, "transifex_org") or ""
        )
        config["TRANSIFEX_PROJECT_SLUG"] = (
            keyring.get_password(SERVICE_NAME, "transifex_project") or ""
        )
        config["BACKUP_PATH"] = keyring.get_password(SERVICE_NAME, "backup_path")
        if not config["BACKUP_PATH"]:
            config["BACKUP_PATH"] = str(Path.home() / DEFAULT_BACKUP_PATH_NAME)
        config["LOG_LEVEL"] = (
            keyring.get_password(SERVICE_NAME, "log_level") or DEFAULT_LOG_LEVEL
        )
        backup_enabled_str = keyring.get_password(
            SERVICE_NAME, "backup_enabled"
        ) or str(int(DEFAULT_BACKUP_ENABLED))
        config["BACKUP_ENABLED"] = backup_enabled_str == "1"
        update_enabled_str = keyring.get_password(
            SERVICE_NAME, "auto_update_enabled"
        ) or str(int(DEFAULT_AUTO_UPDATE_ENABLED))
        config["AUTO_UPDATE_ENABLED"] = update_enabled_str == "1"
        return config

    def update_readiness_status(self):
        """Checks config and updates UI state, always showing debug status if enabled."""
        config = self.get_current_config()
        is_ready = all([config.get("BRAZE_API_KEY"), config.get("TRANSIFEX_API_TOKEN")])
        base_status = "Ready" if is_ready else "Configuration required"
        self.run_button.configure(state="normal" if is_ready else "disabled")
        debug_suffix = " (Debug)" if config.get("LOG_LEVEL") == "Debug" else ""
        self.status_label.configure(text=f"{base_status}{debug_suffix}")

    def show_more_menu(self):
        """Displays the 'more options' pop-up menu."""
        x = self.more_button.winfo_rootx()
        y = self.more_button.winfo_rooty() + self.more_button.winfo_height()
        self.more_menu.tk_popup(x, y)

    def open_about_window(self):
        """Displays an 'About' dialog with the application version."""
        tkinter.messagebox.showinfo(
            "About btx sync",
            f"Version: {APP_VERSION}\n\n"
            "A cross-platform desktop application for synchronizing content "
            "from Braze to Transifex for translation.",
        )

    def open_help_file(self):
        """Opens the README.md documentation file."""
        try:
            readme_path = resource_path("README.md")
            webbrowser.open(f"file://{readme_path}")
        except Exception as e:
            tkinter.messagebox.showerror("Error", f"Could not open help file.\n\n{e}")

    def show_right_click_menu(self, event):
        """Displays the right-click menu at the cursor's position."""
        self.right_click_menu.tk_popup(event.x_root, event.y_root)

    def copy_log_text(self):
        """Copies the selected text from the log box to the clipboard."""
        try:
            self.clipboard_append(self.log_box.get("sel.first", "sel.last"))
        except tkinter.TclError:
            pass

    def select_all_log_text(self):
        """Selects all text in the log box."""
        self.log_box.tag_add("sel", "1.0", "end")
        return "break"

    def log_message(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def update_status_label(self, message: str) -> None:
        """Updates the status label in the UI."""
        self.after(0, self._update_status_label_gui, message)

    def _update_status_label_gui(self, message: str) -> None:
        """Internal helper to update the status label on the GUI thread."""
        config = self.get_current_config()
        debug_suffix = " (Debug)" if config.get("LOG_LEVEL") == "Debug" else ""
        self.status_label.configure(text=f"Running: {message}{debug_suffix}")

    def cancel_sync(self):
        """Sets the cancellation event to stop the sync thread."""
        self.status_label.configure(text="Cancelling...")
        self.cancel_button.configure(state="disabled")
        self.cancel_event.set()

    def sync_thread_target(self):
        self.run_button.pack_forget()
        self.cancel_button.pack(side="left", padx=10, pady=5)
        self.cancel_button.configure(state="normal")
        self.status_label.configure(text="Running...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        config = self.load_config_for_sync()
        try:
            if config:
                sync_logic_main(
                    config,
                    self.log_message,
                    self.cancel_event,
                    self.update_status_label,
                )
            else:
                self.log_message("--- CONFIGURATION ERROR ---")
        finally:
            self.cancel_button.pack_forget()
            self.run_button.pack(side="left", padx=10, pady=5)
            status = "Cancelled" if self.cancel_event.is_set() else None
            self.update_readiness_status()
            if status:
                self.status_label.configure(text=status)
            self.log_message("\n")

    def start_sync_thread(self):
        self.cancel_event.clear()
        thread = threading.Thread(target=self.sync_thread_target, daemon=True)
        thread.start()

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
            self.settings_window.grab_set()
            self.wait_window(self.settings_window)
            self.update_readiness_status()
        else:
            self.settings_window.focus()

    def load_config_for_sync(self):
        """
        Loads the configuration and validates that essential keys are present for
        syncing.
        Returns the config dictionary if valid, otherwise returns None.
        """
        config = self.get_current_config()
        return (
            config
            if all([config["BRAZE_API_KEY"], config["TRANSIFEX_API_TOKEN"]])
            else None
        )


if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = App()
    app.mainloop()
