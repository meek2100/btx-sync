# app.py
import customtkinter
import keyring
import threading
import tkinter
import webbrowser
import sys
import shutil
import platform
from tkinter import messagebox
from pathlib import Path
from PIL import Image
from customtkinter import CTkImage
from tufup.client import Client

# Import from our other modules
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
)
from config import SERVICE_NAME
from gui_settings import SettingsWindow
from sync_logic import sync_logic_main
from utils import resource_path, is_production_environment
from logger import AppLogger

# --- Dynamic Version Configuration ---
try:
    from version import __version__ as APP_VERSION  # type: ignore
except ImportError:
    APP_VERSION = "0.0.0-dev"

# --- Tufup Configuration ---
APP_NAME = "btx-sync"
UPDATE_URL = "https://meek2100.github.io/btx-sync/"


def check_for_updates(app_instance):
    """
    Checks for app updates and displays a notification bar if a new version
    is found. Log messages are now sent to debug to keep the check silent.
    """
    logger = AppLogger(
        app_instance.log_message,
        app_instance.get_current_config().get("LOG_LEVEL", "Normal"),
    )
    # This message will now only appear in debug mode
    logger.debug("Checking for updates...")

    platform_system = platform.system().lower()
    if platform_system == "windows":
        platform_suffix = "win"
    elif platform_system == "darwin":
        platform_suffix = "mac"
    else:
        platform_suffix = "linux"

    platform_app_name = f"{APP_NAME}-{platform_suffix}"
    logger.debug(f"Platform: {platform_system}, App Name: {platform_app_name}")

    app_data_dir = Path.home() / f".{APP_NAME}"
    app_data_dir.mkdir(exist_ok=True)
    metadata_dir = app_data_dir / "metadata"
    target_dir = app_data_dir / "targets"
    metadata_dir.mkdir(exist_ok=True)
    target_dir.mkdir(exist_ok=True)

    local_root_path = metadata_dir / "root.json"
    if not local_root_path.exists():
        try:
            bundled_root_path = resource_path("repository/metadata/root.json")
            shutil.copy(bundled_root_path, local_root_path)
            logger.debug("Initial root.json copied.")
        except Exception as e:
            logger.error(f"Failed to initialize update metadata: {repr(e)}")
            return

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
        new_update = client.check_for_updates(pre="a")

        if new_update:
            # The blue bar is the primary notification; log this for debug purposes.
            logger.debug(f"Update {new_update.version} found.")
            app_instance.tufup_client = client
            app_instance.show_update_notification(new_update)
        else:
            # This message will now only appear in debug mode.
            logger.debug("Application is up to date.")

    except Exception as e:
        logger.error(f"Update check failed: {repr(e)}")


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("btx sync")
        self.geometry("800x600")
        self.iconbitmap(resource_path("assets/icon.ico"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- UPDATE NOTIFICATION FRAME ---
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

        # --- CONTROL FRAME ---
        self.control_frame = customtkinter.CTkFrame(self, height=50)
        self.control_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

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

        # --- LOG BOX ---
        self.log_box = customtkinter.CTkTextbox(
            self, state="disabled", font=("Courier New", 12)
        )
        self.log_box.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- MENUS ---
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

        # --- INITIALIZATION ---
        self.log_box.bind("<Button-3>", self.show_right_click_menu)
        self.settings_window = None
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
        elif not in_prod:
            self.log_message("Auto-update check disabled in development mode.")

    def show_update_notification(self, new_update):
        self.new_update_info = new_update
        self.update_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

    def apply_update(self):
        if not self.new_update_info:
            return
        self.update_button.configure(state="disabled", text="Installing...")
        self.log_message(f"Downloading update {self.new_update_info.version}...")
        update_thread = threading.Thread(target=self.threaded_apply, daemon=True)
        update_thread.start()

    def threaded_apply(self):
        """Uses the stored client instance to apply the update."""
        if not self.tufup_client:
            self.log_message("[ERROR] Update client not initialized.")
            self.update_button.configure(state="normal", text="Install Now")
            return

        # In production, the install dir is the app's current directory.
        # This logic is now handled by tufup's default behavior.
        self.tufup_client.app_install_dir = Path(sys.executable).parent

        # Use confirm=False and force=True to ensure the default installer
        # runs without any interactive prompts for a seamless update.
        if self.tufup_client.download_and_apply_update(
            target=self.new_update_info, confirm=False, force=True
        ):
            self.log_message("Update successful. The application will now restart.")
        else:
            self.log_message("[ERROR] Update failed.")
            self.update_button.configure(state="normal", text="Install Now")

    def force_update_check(self):
        """Starts the update check process manually, triggered by the user."""
        self.log_message("\n--- Manual update check initiated ---")
        update_thread = threading.Thread(
            target=check_for_updates, args=(self,), daemon=True
        )
        update_thread.start()

    def get_current_config(self):
        """
        Loads all settings from the system keychain and returns them as a dict.
        """
        config = {}
        for key in MANAGED_SETTINGS_KEYS:
            config[key.upper()] = keyring.get_password(SERVICE_NAME, key)

        if not config.get(KEY_BACKUP_PATH.upper()):
            config[KEY_BACKUP_PATH.upper()] = str(
                Path.home() / DEFAULT_BACKUP_PATH_NAME
            )
        if not config.get(KEY_LOG_LEVEL.upper()):
            config[KEY_LOG_LEVEL.upper()] = DEFAULT_LOG_LEVEL
        if config.get(KEY_BACKUP_ENABLED.upper()) is None:
            config[KEY_BACKUP_ENABLED.upper()] = str(int(DEFAULT_BACKUP_ENABLED))
        if config.get(KEY_AUTO_UPDATE.upper()) is None:
            config[KEY_AUTO_UPDATE.upper()] = str(int(DEFAULT_AUTO_UPDATE_ENABLED))

        config["BACKUP_ENABLED"] = config[KEY_BACKUP_ENABLED.upper()] == "1"
        config["AUTO_UPDATE_ENABLED"] = config[KEY_AUTO_UPDATE.upper()] == "1"
        return config

    def update_readiness_status(self):
        """Checks config and updates UI state, always showing debug status."""
        config = self.get_current_config()
        is_ready = all([config.get("BRAZE_API_KEY"), config.get("TRANSIFEX_API_TOKEN")])
        base_status = "Ready" if is_ready else "Configuration required"
        self.run_button.configure(state="normal" if is_ready else "disabled")
        debug_suffix = " (Debug)" if config.get("LOG_LEVEL") == "Debug" else ""
        self.status_label.configure(text=f"{base_status}{debug_suffix}")

    def show_more_menu(self):
        x = self.more_button.winfo_rootx()
        y = self.more_button.winfo_rooty() + self.more_button.winfo_height()
        self.more_menu.tk_popup(x, y)

    def open_about_window(self):
        messagebox.showinfo(
            "About btx sync",
            f"Version: {APP_VERSION}\n\n"
            "A cross-platform desktop application for synchronizing content "
            "from Braze to Transifex for translation.",
        )

    def open_help_file(self):
        try:
            readme_path = resource_path("README.md")
            webbrowser.open(f"file://{readme_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open help file.\n\n{e}")

    def show_right_click_menu(self, event):
        self.right_click_menu.tk_popup(event.x_root, event.y_root)

    def copy_log_text(self):
        try:
            self.clipboard_append(self.log_box.get("sel.first", "sel.last"))
        except tkinter.TclError:
            pass

    def select_all_log_text(self):
        self.log_box.tag_add("sel", "1.0", "end")
        return "break"

    def log_message(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def update_status_label(self, message: str) -> None:
        self.after(0, self._update_status_label_gui, message)

    def _update_status_label_gui(self, message: str) -> None:
        config = self.get_current_config()
        debug_suffix = " (Debug)" if config.get("LOG_LEVEL") == "Debug" else ""
        self.status_label.configure(text=f"Running: {message}{debug_suffix}")

    def cancel_sync(self):
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
        config = self.get_current_config()
        try:
            if all([config["BRAZE_API_KEY"], config["TRANSIFEX_API_TOKEN"]]):
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


if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = App()
    app.mainloop()
