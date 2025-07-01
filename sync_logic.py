# sync_logic.py

import requests
import json
import time
import threading
from pathlib import Path
from typing import Callable

# Import the AppLogger for type hinting
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
        poll_interval = 5  # Initial poll interval
        max_poll_interval = 30  # Maximum poll interval

        while time.time() < timeout:
            if cancel_event.is_set():
                raise CancellationError("Backup process cancelled by user.")

            response = transifex_session.get(status_url, timeout=30)
            response.raise_for_status()

            # Check content type header to distinguish JSON status from file content
            content_type = response.headers.get("Content-Type", "")

            if (
                "application/vnd.api+json" in content_type
                or "application/json" in content_type
            ):
                try:
                    status_data = response.json()
                    status = (
                        status_data.get("data", {}).get("attributes", {}).get("status")
                    )

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

                except json.JSONDecodeError:
                    logger.error(
                        "Received invalid JSON while checking TMX backup status. "
                        f"Response: {response.text[:200]}..."
                    )
                    return False
            elif (
                "text/xml" in content_type or "application/octet-stream" in content_type
            ):
                logger.info("  > Received TMX file content directly.")
                file_content = response.content
                break
            else:
                logger.error(
                    f"Unexpected content type received during TMX backup polling: "
                    f"'{content_type}'. Response: {response.text[:200]}..."
                )
                return False

        if file_content is None:
            logger.error("TMX backup job timed out after 5 minutes.")
            return False

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = (
            f"backup_{config.get('TRANSIFEX_PROJECT_SLUG')}_"
            f"all_languages_{timestamp}.tmx"
        )
        filepath = backup_path / filename
        with open(filepath, "wb") as f:
            f.write(file_content)
        logger.info(f"  > SUCCESS: Backup saved to {filepath}")
        return True

    except CancellationError:
        # Re-raise to be caught by the main handler
        raise
    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred while checking backup status: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during TMX backup polling: {e}")
        return False


def sync_logic_main(
    config: dict,
    log_callback: Callable[[str], None],
    cancel_event: threading.Event,
    progress_callback: Callable[[str], None],  # Added progress_callback
) -> None:
    """
    This is the main function that runs the entire sync process.
    """
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("--- Starting Braze to Transifex Sync ---")

    def check_for_cancel(message: str = "Working...") -> None:  # Added message
        progress_callback(message)  # Call the progress callback
        if cancel_event.is_set():
            raise CancellationError("Sync process was cancelled by the user.")

    braze_session = requests.Session()
    braze_session.headers.update(
        {"Authorization": f"Bearer {config.get('BRAZE_API_KEY')}"}
    )

    transifex_session = requests.Session()
    transifex_session.headers.update(
        {
            "Authorization": f"Bearer {config.get('TRANSIFEX_API_TOKEN')}",
            "Content-Type": "application/vnd.api+json",
        }
    )

    def fetch_braze_list(endpoint: str, list_key: str, limit: int = 100) -> list:
        all_items = []
        offset = 0
        braze_rest_endpoint = config.get("BRAZE_REST_ENDPOINT")
        while True:
            check_for_cancel(f"Fetching {list_key} (offset {offset})...")  # Updated
            time.sleep(0.2)

            # Construct URL without offset for the first page
            base_url = f"{braze_rest_endpoint}{endpoint}?limit={limit}"
            if offset > 0:
                url = f"{base_url}&offset={offset}"
            else:
                url = base_url

            logger.info(f"Fetching {list_key} list from Braze: offset {offset}")
            response = braze_session.get(url, timeout=30)
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

    def fetch_braze_item_details(
        endpoint: str, id_param_name: str, item_id: str
    ) -> dict:
        check_for_cancel(
            f"Fetching details for {id_param_name}: {item_id}..."
        )  # Updated
        time.sleep(0.2)
        braze_rest_endpoint = config.get("BRAZE_REST_ENDPOINT")
        url = f"{braze_rest_endpoint}{endpoint}?{id_param_name}={item_id}"
        logger.info(f"  > Fetching details for ID: {item_id}")
        response = braze_session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def create_or_update_transifex_resource(slug: str, name: str) -> None:
        check_for_cancel(f"Processing resource '{slug}'...")  # Updated
        org = config.get("TRANSIFEX_ORGANIZATION_SLUG")
        proj = config.get("TRANSIFEX_PROJECT_SLUG")
        transifex_project_id = f"o:{org}:p:{proj}"
        resource_id = f"{transifex_project_id}:r:{slug}"
        url = f"{TRANSIFEX_API_BASE_URL}/resources/{resource_id}"

        response = transifex_session.get(url, timeout=30)

        if response.status_code == 404:
            logger.info(f"  > Resource '{slug}' not found. Creating...")
            create_url = f"{TRANSIFEX_API_BASE_URL}/resources"
            payload = {
                "data": {
                    "type": "resources",
                    "attributes": {"slug": slug, "name": name},
                    "relationships": {
                        "project": {
                            "data": {"type": "projects", "id": transifex_project_id}
                        },
                        "i18n_format": {
                            "data": {"type": "i18n_formats", "id": "KEYVALUEJSON"}
                        },
                    },
                }
            }
            create_response = transifex_session.post(
                create_url, data=json.dumps(payload), timeout=30
            )
            create_response.raise_for_status()
            logger.info(f"  > Resource '{slug}' created with name '{name}'.")

        elif response.status_code == 200:
            existing_name = response.json()["data"]["attributes"]["name"]
            if existing_name != name:
                logger.info(f"  > Updating name for '{slug}' to '{name}'...")
                patch_payload = {
                    "data": {
                        "type": "resources",
                        "id": resource_id,
                        "attributes": {"name": name},
                    }
                }
                patch_response = transifex_session.patch(
                    url, data=json.dumps(patch_payload), timeout=30
                )
                patch_response.raise_for_status()
                logger.info("  > Name updated successfully.")
            else:
                logger.info(f"  > Resource '{slug}' found with correct name.")
        else:
            response.raise_for_status()

    def upload_source_content_to_transifex(
        content_dict: dict, resource_slug: str
    ) -> None:
        check_for_cancel(f"Uploading content for '{resource_slug}'...")  # Updated
        if not content_dict:
            logger.info("  > No content to upload. Skipping.")
            return

        org = config.get("TRANSIFEX_ORGANIZATION_SLUG")
        proj = config.get("TRANSIFEX_PROJECT_SLUG")
        resource_id = f"o:{org}:p:{proj}:r:{resource_slug}"
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
        response = transifex_session.post(url, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        if response.status_code == 202:
            logger.info(f"  > Upload started for {len(content_dict)} string(s).")

    try:
        check_for_cancel("Starting sync process...")  # Initial status update
        if config.get("BACKUP_ENABLED", False):
            if not perform_tmx_backup(config, transifex_session, logger, cancel_event):
                logger.info("\n--- Sync halted due to backup failure. ---")
                return
            logger.info("--- TMX Backup complete. Proceeding with sync. ---\n")
        else:
            logger.info("TMX backup is disabled. Skipping.")

        check_for_cancel("\n[1] Processing Email Templates...")  # Updated status
        logger.info("\n[1] Processing Email Templates...")
        for template in fetch_braze_list("/templates/email/list", "templates"):
            check_for_cancel(
                f"Processing Email Template '{template.get('template_name')}'..."
            )  # Updated status
            template_id = template.get("email_template_id")
            template_name = template.get("template_name")
            if not template_id or not template_name:
                continue
            logger.info(f"\nProcessing '{template_name}' (ID: {template_id})...")
            details = fetch_braze_item_details(
                "/templates/email/info", "email_template_id", template_id
            )
            create_or_update_transifex_resource(slug=template_id, name=template_name)
            content = {
                f: details.get(f)
                for f in EMAIL_TRANSLATABLE_FIELDS
                if details.get(f) and str(details.get(f)).strip()
            }
            upload_source_content_to_transifex(content, resource_slug=template_id)

        check_for_cancel("\n[2] Processing Content Blocks...")  # Updated status
        logger.info("\n[2] Processing Content Blocks...")
        for block in fetch_braze_list("/content_blocks/list", "content_blocks"):
            check_for_cancel(
                f"Processing Content Block '{block.get('name')}'..."
            )  # Updated status
            block_id = block.get("content_block_id")
            block_name = block.get("name")
            if not block_id or not block_name:
                continue
            logger.info(f"\nProcessing '{block_name}' (ID: {block_id})...")
            details = fetch_braze_item_details(
                "/content_blocks/info", "content_block_id", block_id
            )
            create_or_update_transifex_resource(slug=block_id, name=block_name)
            content = {
                f: details.get(f)
                for f in BLOCK_TRANSLATABLE_FIELDS
                if details.get(f) and str(details.get(f)).strip()
            }
            upload_source_content_to_transifex(content, resource_slug=block_id)

        logger.info("\n--- Sync Complete! ---")

    except CancellationError as e:
        logger.info(f"\n--- {e} ---")
    except requests.exceptions.HTTPError as e:
        logger.fatal("An API error occurred.")
        if e.request:
            logger.error(f"Request URL: {e.request.url}")
            logger.debug(f"Request Headers: {e.request.headers}")
            if e.request.body:
                logger.debug(f"Request Body: {e.request.body}")
        if e.response is not None:
            logger.error(f"Response Status Code: {e.response.status_code}")
            try:
                error_details = e.response.json()
                logger.error(
                    f"Response Error Details: {json.dumps(error_details, indent=2)}"
                )
            except json.JSONDecodeError:
                logger.error(f"Response Content: {e.response.text}")
            logger.debug(f"Response Headers: {e.response.headers}")
    except requests.exceptions.RequestException as e:
        logger.fatal(f"A network error occurred: {e}")
    except KeyError as e:
        logger.fatal(f"Received an unexpected API response. Missing expected key: {e}")
    except Exception as e:
        logger.fatal(f"An unexpected error occurred: {e}")
