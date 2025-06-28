import customtkinter
import requests
import json
import time
import keyring
import threading
import webbrowser
import tkinter
from tkinter import messagebox, filedialog
from pathlib import Path

# --- APPLICATION CONFIGURATION ---
# A unique name for your application to store credentials under
SERVICE_NAME = "com.yourcompany.braze-transifex-sync"
CONFIG_FILE_NAME = "config.json"


# --- HELPER CLASS FOR LOGGING ---
class AppLogger:
    def __init__(self, log_callback, level="Normal"):
        self.log_callback = log_callback
        self.level = level

    def info(self, message):
        self.log_callback(message)

    def debug(self, message):
        if self.level == "Debug":
            self.log_callback(f"[DEBUG] {message}")

    def error(self, message):
        self.log_callback(f"[ERROR] {message}")

    def fatal(self, message):
        self.log_callback(f"\n--- [FATAL] {message} ---")


# --- CORE SYNC LOGIC ---


def perform_tmx_backup(config, transifex_headers, logger):
    """
    Handles the entire TMX backup process for all project languages in a single file.
    Returns True on success, False on failure.
    """
    logger.info("\n--- Starting TMX Backup ---")
    backup_path_str = config.get("BACKUP_PATH")
    if not backup_path_str:
        logger.error("Backup path is not defined. Skipping backup.")
        return True

    backup_path = Path(backup_path_str)
    backup_path.mkdir(parents=True, exist_ok=True)
    project_id = f"o:{config.get('TRANSIFEX_ORGANIZATION_SLUG')}:p:{config.get('TRANSIFEX_PROJECT_SLUG')}"

    try:
        logger.info("  > Requesting TMX file for all languages from Transifex...")
        post_url = "https://rest.api.transifex.com/tmx_async_downloads"
        post_payload = {
            "data": {
                "type": "tmx_async_downloads",
                "relationships": {
                    "project": {"data": {"type": "projects", "id": project_id}}
                },
            }
        }

        logger.debug("Sending Request to URL: " + post_url)
        sanitized_headers = transifex_headers.copy()
        if "Authorization" in sanitized_headers:
            sanitized_headers["Authorization"] = "Bearer [REDACTED]"
        logger.debug("Request Headers: " + json.dumps(sanitized_headers, indent=2))
        logger.debug("Request Payload: " + json.dumps(post_payload, indent=2))

        response = requests.post(
            post_url, headers=transifex_headers, data=json.dumps(post_payload)
        )
        response.raise_for_status()

        job_id = response.json()["data"]["id"]
        status_url = f"https://rest.api.transifex.com/tmx_async_downloads/{job_id}"
        logger.info(f"  > Backup job created successfully. ID: {job_id}")

    except requests.exceptions.HTTPError as http_err:
        logger.fatal("HTTP Error during TMX backup job start")
        logger.error(f"Status Code: {http_err.response.status_code}")
        logger.error(f"Response Body: {http_err.response.text}")
        return False
    except Exception as e:
        logger.fatal("An unexpected error occurred starting TMX backup job")
        logger.error(f"Error: {e}")
        return False

    try:
        logger.info("  > Waiting for Transifex to process the file...")
        timeout = time.time() + 300
        while time.time() < timeout:
            response = requests.get(status_url, headers=transifex_headers)
            response.raise_for_status()

            try:
                # First, try to parse the response as JSON
                status_data = response.json()
                status = status_data["data"]["attributes"]["status"]
                if status == "completed":
                    download_url = status_data["data"]["links"]["download"]
                    logger.info("  > File ready for download.")
                    tmx_response = requests.get(download_url)
                    tmx_response.raise_for_status()
                    # Use the raw content for saving
                    file_content = tmx_response.content
                    break  # Exit polling loop, proceed to save
                elif status == "failed":
                    logger.error("Transifex reported the backup job failed.")
                    return False

                logger.debug(f"Current job status: '{status}'. Polling again in 5s.")
                time.sleep(5)

            except json.JSONDecodeError:
                # If JSON parsing fails, assume we received the raw file content directly.
                logger.info(
                    "  > Received non-JSON response, assuming it's the TMX file."
                )
                file_content = response.content
                break  # Exit polling loop, proceed to save
        else:  # This 'else' belongs to the 'while' loop, executes if it times out
            logger.error("TMX backup job timed out after 5 minutes.")
            return False

        # Save the file content we received
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"backup_{config.get('TRANSIFEX_PROJECT_SLUG')}_all_languages_{timestamp}.tmx"
        filepath = backup_path / filename
        with open(filepath, "wb") as f:
            f.write(file_content)
        logger.info(f"  > SUCCESS: Backup saved to {filepath}")
        return True

    except requests.exceptions.HTTPError as http_err:
        logger.fatal("HTTP Error while checking backup status")
        logger.error(f"Status Code: {http_err.response.status_code}")
        logger.error(f"Response Body: {http_err.response.text}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during TMX backup polling: {e}")
        return False


def sync_logic_main(config, log_callback):
    """
    This is the main function that runs the entire sync process.
    """
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("--- Starting Braze to Transifex Sync ---")

    braze_api_key = config.get("BRAZE_API_KEY")
    braze_rest_endpoint = config.get("BRAZE_REST_ENDPOINT")
    transifex_api_token = config.get("TRANSIFEX_API_TOKEN")
    transifex_org_slug = config.get("TRANSIFEX_ORGANIZATION_SLUG")
    transifex_project_slug = config.get("TRANSIFEX_PROJECT_SLUG")

    braze_headers = {"Authorization": f"Bearer {braze_api_key}"}
    transifex_headers = {
        "Authorization": f"Bearer {transifex_api_token}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }

    if config.get("BACKUP_ENABLED", False):
        if not perform_tmx_backup(config, transifex_headers, logger):
            logger.info("\n--- Sync halted due to backup failure. ---")
            return
        logger.info("--- TMX Backup complete. Proceeding with sync. ---\n")
    else:
        logger.info("TMX backup is disabled. Skipping.")

    email_translatable_fields = ["subject", "preheader", "body"]
    block_translatable_fields = ["content"]

    def fetch_braze_list(endpoint, list_key, limit=100):
        all_items = []
        offset = 0
        while True:
            time.sleep(0.2)
            url = f"{braze_rest_endpoint}{endpoint}?limit={limit}"
            if offset > 0:
                url += f"&offset={offset}"
            logger.info(f"Fetching {list_key} list from Braze: offset {offset}")
            logger.debug(f"Requesting URL: {url}")
            response = requests.get(url, headers=braze_headers)
            response.raise_for_status()
            data = response.json()
            items = data.get(list_key, [])
            if not items:
                break
            all_items.extend(items)
            offset += len(items)
            if len(items) < limit:
                break
        return all_items

    def fetch_braze_item_details(endpoint, id_param_name, item_id):
        time.sleep(0.2)
        url = f"{braze_rest_endpoint}{endpoint}?{id_param_name}={item_id}"
        logger.info(f"  > Fetching details for ID: {item_id}")
        logger.debug(f"Requesting URL: {url}")
        response = requests.get(url, headers=braze_headers)
        response.raise_for_status()
        return response.json()

    def create_or_update_transifex_resource(slug, name):
        resource_id = f"o:{transifex_org_slug}:p:{transifex_project_slug}:r:{slug}"
        # FIX: Using the non-versioned endpoint
        url = f"https://rest.api.transifex.com/resources/{resource_id}"
        logger.debug(f"Checking for resource at URL: {url}")
        response = requests.get(url, headers=transifex_headers)
        if response.status_code == 404:
            logger.info(f"  > Resource '{slug}' not found. Creating...")
            # FIX: Using the non-versioned endpoint
            create_url = "https://rest.api.transifex.com/resources"
            payload = {
                "data": {
                    "type": "resources",
                    "attributes": {"slug": slug, "name": name},
                    "relationships": {
                        "project": {
                            "data": {
                                "type": "projects",
                                "id": f"o:{transifex_org_slug}:p:{transifex_project_slug}",
                            }
                        },
                        "i18n_format": {
                            "data": {"type": "i18n_formats", "id": "KEYVALUEJSON"}
                        },
                    },
                }
            }
            logger.debug(f"Creating resource with payload: {json.dumps(payload)}")
            create_response = requests.post(
                create_url, headers=transifex_headers, data=json.dumps(payload)
            )
            create_response.raise_for_status()
            logger.info(f"  > Resource '{slug}' created with name '{name}'.")
        elif response.status_code == 200:
            logger.info(f"  > Resource '{slug}' found with correct name '{name}'.")
        else:
            response.raise_for_status()

    def upload_source_content_to_transifex(content_dict, resource_slug):
        if not content_dict:
            logger.info("  > No content to upload. Skipping.")
            return
        logger.info(
            f"  > Preparing to upload {len(content_dict)} string(s) to resource '{resource_slug}'..."
        )
        # FIX: Using the non-versioned endpoint
        url = "https://rest.api.transifex.com/resource_strings_async_uploads"
        payload = {
            "data": {
                "type": "resource_strings_async_uploads",
                "attributes": {
                    "content": json.dumps(content_dict),
                    "content_encoding": "text",
                },
                "relationships": {
                    "resource": {
                        "data": {
                            "type": "resources",
                            "id": f"o:{transifex_org_slug}:p:{transifex_project_slug}:r:{resource_slug}",
                        }
                    }
                },
            }
        }
        logger.debug(f"Uploading content to {url} with payload: {json.dumps(payload)}")
        response = requests.post(
            url, headers=transifex_headers, data=json.dumps(payload)
        )
        response.raise_for_status()
        if response.status_code == 202:
            logger.info("  > Successfully started upload job.")

    try:
        logger.info("\n[1] Processing Email Templates...")
        for template_info in fetch_braze_list("/templates/email/list", "templates"):
            template_id = template_info.get("email_template_id")
            template_name = template_info.get("template_name")
            if not template_id or not template_name:
                continue
            logger.info(f"\nProcessing '{template_name}' (ID: {template_id})...")
            details = fetch_braze_item_details(
                "/templates/email/info", "email_template_id", template_id
            )
            create_or_update_transifex_resource(slug=template_id, name=template_name)
            content = {
                f: details.get(f)
                for f in email_translatable_fields
                if details.get(f) and details.get(f).strip()
            }
            upload_source_content_to_transifex(content, resource_slug=template_id)

        logger.info("\n[2] Processing Content Blocks...")
        for block_info in fetch_braze_list("/content_blocks/list", "content_blocks"):
            block_id = block_info.get("content_block_id")
            block_name = block_info.get("name")
            if not block_id or not block_name:
                continue
            logger.info(f"\nProcessing '{block_name}' (ID: {block_id})...")
            details = fetch_braze_item_details(
                "/content_blocks/info", "content_block_id", block_id
            )
            create_or_update_transifex_resource(slug=block_id, name=block_name)
            content = {
                f: details.get(f)
                for f in block_translatable_fields
                if details.get(f) and details.get(f).strip()
            }
            upload_source_content_to_transifex(content, resource_slug=block_id)

        logger.info("\n--- Sync Complete! ---")
    except Exception as e:
        logger.fatal("An unexpected error occurred during the main sync process.")
        logger.error(f"Error: {str(e)}")
        logger.error("Please check your settings and network connection.")


# --- GUI CLASSES ---


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


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Braze-Transifex Sync Tool")
        self.geometry("800x600")
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

        # --- FIX: Add Right-Click Context Menu ---
        self.right_click_menu = tkinter.Menu(
            self.log_box, tearoff=0, background="#2B2B2B", foreground="white"
        )
        self.right_click_menu.add_command(label="Copy", command=self.copy_log_text)
        self.right_click_menu.add_separator()
        self.right_click_menu.add_command(
            label="Select All", command=self.select_all_log_text
        )

        self.log_box.bind("<Button-3>", self.show_right_click_menu)
        # --- END FIX ---

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
            # This handles the case where no text is selected, preventing an error
            pass

    def select_all_log_text(self):
        """Selects all text in the log box."""
        self.log_box.tag_add("sel", "1.0", "end")
        return "break"  # Prevents the default right-click behavior from interfering

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
