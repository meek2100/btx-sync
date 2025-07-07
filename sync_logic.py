# sync_logic.py

import requests
import json
import time
import threading
from pathlib import Path
from typing import Callable, Any, List, Dict

from logger import AppLogger
from constants import (
    BLOCK_TRANSLATABLE_FIELDS,
    EMAIL_TRANSLATABLE_FIELDS,
    TRANSIFEX_API_BASE_URL,
    BRAZE_EMAIL_TEMPLATES_LIST_ENDPOINT,
    BRAZE_EMAIL_TEMPLATE_INFO_ENDPOINT,
    BRAZE_CONTENT_BLOCKS_LIST_ENDPOINT,
    BRAZE_CONTENT_BLOCK_INFO_ENDPOINT,
    TRANSIFEX_RESOURCES_ENDPOINT,
    TRANSIFEX_RESOURCE_STRINGS_ASYNC_UPLOADS_ENDPOINT,
    TRANSIFEX_TMX_ASYNC_DOWNLOADS_ENDPOINT,
)

STATE_FILE_PATH = Path.home() / ".btx-sync" / "sync_state.json"


class SyncState:
    """Manages the state of the sync process for resumability."""

    @staticmethod
    def load() -> Dict[str, List[str]]:
        """Loads the sync state from the state file."""
        if not STATE_FILE_PATH.exists():
            return {"templates": [], "blocks": []}
        with open(STATE_FILE_PATH, "r") as f:
            return json.load(f)

    @staticmethod
    def save(templates: List[str], blocks: List[str]) -> None:
        """Saves the given lists of item IDs to the state file."""
        STATE_FILE_PATH.parent.mkdir(exist_ok=True)
        with open(STATE_FILE_PATH, "w") as f:
            json.dump({"templates": templates, "blocks": blocks}, f)

    @staticmethod
    def remove_item(item_type: str, item_id: str) -> None:
        """Removes a successfully processed item from the state file."""
        if STATE_FILE_PATH.exists():
            state = SyncState.load()
            if item_id in state.get(item_type, []):
                state[item_type].remove(item_id)
                SyncState.save(state["templates"], state["blocks"])

    @staticmethod
    def clear() -> None:
        """Removes the state file."""
        if STATE_FILE_PATH.exists():
            STATE_FILE_PATH.unlink()


class CancellationError(Exception):
    """Custom exception to signal a user-initiated cancellation."""

    pass


class BrazeClient:
    """A client to handle interactions with the Braze API."""

    def __init__(self, api_key: str, endpoint: str, logger: AppLogger):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.base_url = endpoint
        self.logger = logger
        self.api_call_delay = 1.0

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Makes an API request and handles rate-limiting (429) errors.
        """
        while True:
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 0))
                    wait_time = retry_after if retry_after > 0 else self.api_call_delay
                    self.logger.info(
                        f"Rate limit hit. Waiting for {wait_time} seconds."
                    )
                    time.sleep(wait_time)
                    continue
                raise
            except requests.exceptions.RequestException:
                self.logger.error("A network error occurred.")
                raise

    def get_paginated_list(self, endpoint: str, list_key: str) -> list[dict[str, Any]]:
        """Fetches a complete list of items from a paginated Braze endpoint."""
        all_items = []
        offset = 0
        limit = 100
        while True:
            base_url = f"{self.base_url}{endpoint}?limit={limit}"
            if offset > 0:
                url = f"{base_url}&offset={offset}"
            else:
                url = base_url
            self.logger.info(f"Fetching {list_key} from Braze: offset {offset}")
            response = self._make_request("GET", url, timeout=30)
            data = response.json()
            items = data.get(list_key, [])
            if not items:
                break
            all_items.extend(items)
            offset += len(items)
            if len(items) < limit:
                break
        return all_items

    def get_item_details(self, endpoint: str, item_id: str) -> dict[str, Any]:
        """Fetches detailed information for a single Braze item."""
        if "email" in endpoint:
            id_param_name = "email_template_id"
        else:
            id_param_name = "content_block_id"
        url = f"{self.base_url}{endpoint}?{id_param_name}={item_id}"
        self.logger.info(f"  > Fetching details for ID: {item_id}")
        response = self._make_request("GET", url, timeout=30)
        return response.json()


class TransifexClient:
    """A client to handle interactions with the Transifex API."""

    def __init__(self, api_token: str, org: str, proj: str, logger: AppLogger):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/vnd.api+json",
            }
        )
        self.project_id = f"o:{org}:p:{proj}"
        self.logger = logger

    def create_or_update_resource(self, slug: str, name: str) -> None:
        """Ensures a resource exists in Transifex with the correct name."""
        resource_id = f"{self.project_id}:r:{slug}"
        url = f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_RESOURCES_ENDPOINT}/{resource_id}"
        response = self.session.get(url, timeout=30)

        if response.status_code == 404:
            self.logger.info(f"  > Resource '{slug}' not found. Creating...")
            self._create_resource(slug, name)
        elif response.status_code == 200:
            self._update_resource_name_if_needed(resource_id, name, response.json())
        else:
            response.raise_for_status()

    def _create_resource(self, slug: str, name: str) -> None:
        """Helper to create a new resource."""
        create_url = f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_RESOURCES_ENDPOINT}"
        payload = {
            "data": {
                "type": "resources",
                "attributes": {"slug": slug, "name": name},
                "relationships": {
                    "project": {"data": {"type": "projects", "id": self.project_id}},
                    "i18n_format": {
                        "data": {
                            "type": "i18n_formats",
                            "id": "KEYVALUEJSON",
                        }
                    },
                },
            }
        }
        create_response = self.session.post(
            create_url, data=json.dumps(payload), timeout=30
        )
        create_response.raise_for_status()
        self.logger.info(f"  > Resource '{slug}' created with name '{name}'.")

    def _update_resource_name_if_needed(
        self, resource_id: str, name: str, details: dict
    ) -> None:
        """Helper to update the name of an existing resource."""
        existing_name = details["data"]["attributes"]["name"]
        if existing_name != name:
            self.logger.info(f"  > Updating name for '{resource_id}' to '{name}'...")
            url = (
                f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_RESOURCES_ENDPOINT}/{resource_id}"
            )
            patch_payload = {
                "data": {
                    "type": "resources",
                    "id": resource_id,
                    "attributes": {"name": name},
                }
            }
            patch_response = self.session.patch(
                url, data=json.dumps(patch_payload), timeout=30
            )
            patch_response.raise_for_status()
            self.logger.info("  > Name updated successfully.")
        else:
            self.logger.info(f"  > Resource '{resource_id}' found with correct name.")

    def upload_source_content(self, content_dict: dict, resource_slug: str) -> None:
        """Uploads a dictionary of source strings to a Transifex resource."""
        if not content_dict:
            self.logger.info("  > No content to upload. Skipping.")
            return

        resource_id = f"{self.project_id}:r:{resource_slug}"
        url = f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_RESOURCE_STRINGS_ASYNC_UPLOADS_ENDPOINT}"
        payload = {
            "data": {
                "type": "resource_strings_async_uploads",
                "attributes": {
                    "content": json.dumps(content_dict),
                    "content_encoding": "text",
                },
                "relationships": {
                    "resource": {"data": {"type": "resources", "id": resource_id}}
                },
            }
        }
        response = self.session.post(url, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        if response.status_code == 202:
            self.logger.info(f"  > Upload started for {len(content_dict)} string(s).")


def perform_tmx_backup(
    config: dict,
    transifex_session: requests.Session,
    logger: AppLogger,
    cancel_event: threading.Event,
) -> bool:
    """
    Handles the entire TMX backup process for all project languages.
    Returns True on success, False on failure.
    """
    logger.info("\n--- Starting TMX Backup ---")
    backup_path_str = config.get("BACKUP_PATH")
    if not backup_path_str:
        logger.error("Backup path is not defined. Skipping backup.")
        return True

    backup_path = Path(backup_path_str)
    backup_path.mkdir(parents=True, exist_ok=True)
    project_id = (
        f"o:{config.get('TRANSIFEX_ORGANIZATION_SLUG')}"
        f":p:{config.get('TRANSIFEX_PROJECT_SLUG')}"
    )

    try:
        logger.info("  > Requesting TMX file for all languages from Transifex...")
        post_url = f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_TMX_ASYNC_DOWNLOADS_ENDPOINT}"
        post_payload = {
            "data": {
                "type": "tmx_async_downloads",
                "relationships": {
                    "project": {"data": {"type": "projects", "id": project_id}}
                },
            }
        }
        response = transifex_session.post(
            post_url, data=json.dumps(post_payload), timeout=30
        )
        response.raise_for_status()
        job_id = response.json()["data"]["id"]
        status_url = (
            f"{TRANSIFEX_API_BASE_URL}{TRANSIFEX_TMX_ASYNC_DOWNLOADS_ENDPOINT}/{job_id}"
        )
        logger.info(f"  > Backup job created successfully. ID: {job_id}")

    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred: {e}")
        return False
    except Exception as e:
        logger.fatal(f"An unexpected error occurred starting TMX backup job: {e}")
        return False

    try:
        logger.info("  > Waiting for Transifex to process the file...")
        timeout = time.time() + 300
        file_content = None
        poll_interval = 5
        max_poll_interval = 30

        while time.time() < timeout:
            if cancel_event.is_set():
                raise CancellationError("Backup process cancelled by user.")

            response = transifex_session.get(status_url, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")

            if "application/vnd.api+json" in content_type:
                status_data = response.json()
                status = status_data.get("data", {}).get("attributes", {}).get("status")

                if status == "completed":
                    download_url = status_data["data"]["links"]["download"]
                    logger.info("  > File ready for download.")
                    tmx_response = transifex_session.get(download_url, timeout=60)
                    tmx_response.raise_for_status()
                    file_content = tmx_response.content
                    break
                elif status == "failed":
                    logger.error("Transifex reported the backup job failed.")
                    return False

                logger.debug(
                    f"Current job status: '{status}'. "
                    f"Polling again in {poll_interval}s."
                )
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 2, max_poll_interval)
            elif (
                "text/xml" in content_type or "application/octet-stream" in content_type
            ):
                logger.info("  > Received TMX file content directly.")
                file_content = response.content
                break
            else:
                logger.error(f"Unexpected content type: '{content_type}'.")
                return False

        if file_content is None:
            logger.error("TMX backup job timed out after 5 minutes.")
            return False

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = (
            f"backup_{config.get('TRANSIFEX_PROJECT_SLUG')}_all_langs_{timestamp}.tmx"
        )
        filepath = backup_path / filename
        with open(filepath, "wb") as f:
            f.write(file_content)
        logger.info(f"  > SUCCESS: Backup saved to {filepath}")
        return True

    except CancellationError:
        raise
    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred while checking backup status: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error during TMX backup polling: {e}")
        return False


def _process_email_templates(
    braze: BrazeClient,
    tx: TransifexClient,
    templates: List[Dict[str, Any]],
    check_for_cancel: Callable[[], None],
    progress_callback: Callable[[int, int], None],
    total_items: int,
    processed_items: int,
) -> int:
    """Processes all email templates."""
    for template in templates:
        check_for_cancel()
        template_id = template.get("email_template_id")
        template_name = template.get("template_name")
        if not template_id or not template_name:
            tx.logger.info("\nSkipping email template with missing ID or name.")
            processed_items += 1
            progress_callback(processed_items, total_items)
            continue
        tx.logger.info(f"\nProcessing '{template_name}' (ID: {template_id})...")
        details = braze.get_item_details(
            BRAZE_EMAIL_TEMPLATE_INFO_ENDPOINT, template_id
        )
        tx.create_or_update_resource(slug=template_id, name=template_name)
        content = {
            f: details.get(f)
            for f in EMAIL_TRANSLATABLE_FIELDS
            if details.get(f) and str(details.get(f)).strip()
        }
        tx.upload_source_content(content, resource_slug=template_id)
        processed_items += 1
        progress_callback(processed_items, total_items)
        SyncState.remove_item("templates", template_id)
    return processed_items


def _process_content_blocks(
    braze: BrazeClient,
    tx: TransifexClient,
    blocks: List[Dict[str, Any]],
    check_for_cancel: Callable[[], None],
    progress_callback: Callable[[int, int], None],
    total_items: int,
    processed_items: int,
) -> int:
    """Processes all content blocks."""
    for block in blocks:
        check_for_cancel()
        block_id = block.get("content_block_id")
        block_name = block.get("name")
        if not block_id or not block_name:
            tx.logger.info("\nSkipping content block with missing ID or name.")
            processed_items += 1
            progress_callback(processed_items, total_items)
            continue
        tx.logger.info(f"\nProcessing '{block_name}' (ID: {block_id})...")
        details = braze.get_item_details(BRAZE_CONTENT_BLOCK_INFO_ENDPOINT, block_id)
        tx.create_or_update_resource(slug=block_id, name=block_name)
        content = {
            f: details.get(f)
            for f in BLOCK_TRANSLATABLE_FIELDS
            if details.get(f) and str(details.get(f)).strip()
        }
        tx.upload_source_content(content, resource_slug=block_id)
        processed_items += 1
        progress_callback(processed_items, total_items)
        SyncState.remove_item("blocks", block_id)
    return processed_items


def sync_logic_main(
    config: dict,
    log_callback: Callable[[str], None],
    cancel_event: threading.Event,
    progress_callback: Callable[[int, int], None],
    resume: bool = False,
) -> None:
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("--- Starting Braze to Transifex Sync ---")

    def check_for_cancel() -> None:
        if cancel_event.is_set():
            raise CancellationError("Sync process was cancelled by the user.")

    try:
        braze = BrazeClient(
            config["BRAZE_API_KEY"], config["BRAZE_REST_ENDPOINT"], logger
        )
        tx = TransifexClient(
            config["TRANSIFEX_API_TOKEN"],
            config["TRANSIFEX_ORGANIZATION_SLUG"],
            config["TRANSIFEX_PROJECT_SLUG"],
            logger,
        )

        check_for_cancel()

        if resume:
            logger.info("\n--- Resuming previous sync session. ---")
            state = SyncState.load()
            all_templates = state.get("templates", [])
            all_blocks = state.get("blocks", [])
            templates_to_process = [
                {"email_template_id": tid, "template_name": "Unknown (resumed)"}
                for tid in all_templates
            ]
            blocks_to_process = [
                {"content_block_id": bid, "name": "Unknown (resumed)"}
                for bid in all_blocks
            ]
        else:
            if config.get("BACKUP_ENABLED", False):
                if not perform_tmx_backup(config, tx.session, logger, cancel_event):
                    logger.info("\n--- Sync halted due to backup failure. ---")
                    return
                logger.info("--- TMX Backup complete. Proceeding with sync. ---\n")
            else:
                logger.info("TMX backup is disabled. Skipping.")

            check_for_cancel()
            logger.info("Fetching item lists from Braze...")
            templates_to_process = braze.get_paginated_list(
                BRAZE_EMAIL_TEMPLATES_LIST_ENDPOINT, "templates"
            )
            check_for_cancel()
            blocks_to_process = braze.get_paginated_list(
                BRAZE_CONTENT_BLOCKS_LIST_ENDPOINT, "content_blocks"
            )
            # Save initial state
            template_ids = [
                t["email_template_id"]
                for t in templates_to_process
                if "email_template_id" in t
            ]
            block_ids = [
                b["content_block_id"]
                for b in blocks_to_process
                if "content_block_id" in b
            ]
            SyncState.save(template_ids, block_ids)

        total_items = len(templates_to_process) + len(blocks_to_process)
        processed_items = 0
        progress_callback(processed_items, total_items)

        logger.info("\n[1] Processing Email Templates...")
        processed_items = _process_email_templates(
            braze,
            tx,
            templates_to_process,
            check_for_cancel,
            progress_callback,
            total_items,
            processed_items,
        )

        logger.info("\n[2] Processing Content Blocks...")
        _process_content_blocks(
            braze,
            tx,
            blocks_to_process,
            check_for_cancel,
            progress_callback,
            total_items,
            processed_items,
        )

        logger.info("\n--- Sync Complete! ---")
        SyncState.clear()

    except CancellationError as e:
        logger.info(f"\n--- {e} ---")
        logger.info("Sync state has been saved. You can resume this session later.")
    except requests.exceptions.HTTPError as e:
        logger.fatal("An API error occurred.")
        if e.request and e.response is not None:
            logger.error(
                f"Request to {e.request.url} failed with status "
                f"{e.response.status_code}"
            )
            try:
                error_details = e.response.json()
                logger.error(f"Details: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                logger.error(f"Response Content: {e.response.text}")
        SyncState.clear()  # Clear state on hard failure
    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred: {e}")
    except Exception as e:
        logger.fatal(f"An unexpected error occurred: {e}")
        SyncState.clear()  # Clear state on hard failure
