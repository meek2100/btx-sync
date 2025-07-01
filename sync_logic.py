# sync_logic.py

import requests
import json
import time
import threading
from pathlib import Path
from typing import Callable, Any

from logger import AppLogger
from constants import (
    BLOCK_TRANSLATABLE_FIELDS,
    EMAIL_TRANSLATABLE_FIELDS,
    TRANSIFEX_API_BASE_URL,
)


# Custom exception to signal a user-initiated cancellation.
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
        # A small delay to be respectful to the API.
        self.api_call_delay = 0.2

    def get_paginated_list(self, endpoint: str, list_key: str) -> list[dict[str, Any]]:
        """Fetches a complete list of items from a paginated Braze endpoint."""
        all_items = []
        offset = 0
        limit = 100
        while True:
            time.sleep(self.api_call_delay)
            url = f"{self.base_url}{endpoint}?limit={limit}&offset={offset}"
            self.logger.info(f"Fetching {list_key} from Braze: offset {offset}")
            response = self.session.get(url, timeout=30)
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

    def get_item_details(self, endpoint: str, item_id: str) -> dict[str, Any]:
        """Fetches detailed information for a single Braze item."""
        time.sleep(self.api_call_delay)
        url = f"{self.base_url}{endpoint}?{endpoint.split('/')[-1]}_id={item_id}"
        self.logger.info(f"  > Fetching details for ID: {item_id}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
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
        url = f"{TRANSIFEX_API_BASE_URL}/resources/{resource_id}"
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
        create_url = f"{TRANSIFEX_API_BASE_URL}/resources"
        payload = {
            "data": {
                "type": "resources",
                "attributes": {"slug": slug, "name": name},
                "relationships": {
                    "project": {"data": {"type": "projects", "id": self.project_id}},
                    "i18n_format": {
                        "data": {"type": "i18n_formats", "id": "KEYVALUEJSON"}
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
            url = f"{TRANSIFEX_API_BASE_URL}/resources/{resource_id}"
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
        url = f"{TRANSIFEX_API_BASE_URL}/resource_strings_async_uploads"
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
        post_url = f"{TRANSIFEX_API_BASE_URL}/tmx_async_downloads"
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
        status_url = f"{TRANSIFEX_API_BASE_URL}/tmx_async_downloads/{job_id}"
        logger.info(f"  > Backup job created successfully. ID: {job_id}")

    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred: {e}")
        return False
    except Exception as e:
        logger.fatal(f"An unexpected error occurred starting TMX backup job: {e}")
        return False

    try:
        logger.info("  > Waiting for Transifex to process the file...")
        timeout = time.time() + 300  # 5-minute timeout
        file_content = None
        # Start with a 5-second poll, backing off exponentially to a max of 30s.
        # This is efficient and respects the server's resources.
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
                    tmx_response = requests.get(download_url, timeout=60)
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
            # The API may directly return the file if it was cached or processed instantly.
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


def sync_logic_main(
    config: dict,
    log_callback: Callable[[str], None],
    cancel_event: threading.Event,
    progress_callback: Callable[[str], None],
) -> None:
    """The main function that orchestrates the entire sync process."""
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("--- Starting Braze to Transifex Sync ---")

    def check_for_cancel(message: str = "Working...") -> None:
        """Helper to update progress and check for user cancellation."""
        progress_callback(message)
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

        check_for_cancel("Starting sync process...")
        if config.get("BACKUP_ENABLED", False):
            if not perform_tmx_backup(config, tx.session, logger, cancel_event):
                logger.info("\n--- Sync halted due to backup failure. ---")
                return
            logger.info("--- TMX Backup complete. Proceeding with sync. ---\n")
        else:
            logger.info("TMX backup is disabled. Skipping.")

        check_for_cancel("\n[1] Processing Email Templates...")
        logger.info("\n[1] Processing Email Templates...")
        templates = braze.get_paginated_list("/templates/email/list", "templates")
        for template in templates:
            check_for_cancel(f"Email: {template.get('template_name')}")
            template_id = template.get("email_template_id")
            # The name comes from the 'template_name' key in the list response.
            template_name = template.get("template_name")
            if not template_id or not template_name:
                continue
            logger.info(f"\nProcessing '{template_name}' (ID: {template_id})...")
            details = braze.get_item_details("/templates/email/info", template_id)
            # FIX: Use the correct variable 'template_name' here.
            tx.create_or_update_resource(slug=template_id, name=template_name)
            content = {
                f: details.get(f)
                for f in EMAIL_TRANSLATABLE_FIELDS
                if details.get(f) and str(details.get(f)).strip()
            }
            tx.upload_source_content(content, resource_slug=template_id)

        check_for_cancel("\n[2] Processing Content Blocks...")
        logger.info("\n[2] Processing Content Blocks...")
        blocks = braze.get_paginated_list("/content_blocks/list", "content_blocks")
        for block in blocks:
            check_for_cancel(f"Block: {block.get('name')}")
            block_id = block.get("content_block_id")
            if not block_id:
                continue
            logger.info(f"\nProcessing '{block.get('name')}'...")
            details = braze.get_item_details("/content_blocks/info", block_id)
            tx.create_or_update_resource(slug=block_id, name=block.get("name"))
            content = {
                f: details.get(f)
                for f in BLOCK_TRANSLATABLE_FIELDS
                if details.get(f) and str(details.get(f)).strip()
            }
            tx.upload_source_content(content, resource_slug=block_id)

        logger.info("\n--- Sync Complete! ---")

    except CancellationError as e:
        logger.info(f"\n--- {e} ---")
    except requests.exceptions.HTTPError as e:
        logger.fatal("An API error occurred.")
        if e.request and e.response is not None:
            logger.error(
                f"Request to {e.request.url} failed with status {e.response.status_code}"
            )
            try:
                error_details = e.response.json()
                logger.error(f"Details: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                logger.error(f"Response Content: {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred: {e}")
    except KeyError as e:
        logger.fatal(f"Unexpected API response. Missing key: {e}")
    except Exception as e:
        logger.fatal(f"An unexpected error occurred: {e}")
