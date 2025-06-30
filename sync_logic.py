# sync_logic.py

import requests
import json
import time
from pathlib import Path
from typing import Callable

# Import the AppLogger for type hinting
from logger import AppLogger

# Define the Transifex API base URL as a constant to avoid hardcoding it multiple times.
TRANSIFEX_API_BASE_URL = "https://rest.api.transifex.com"


def perform_tmx_backup(
    config: dict, transifex_headers: dict, logger: AppLogger
) -> bool:
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
        post_url = f"{TRANSIFEX_API_BASE_URL}/tmx_async_downloads"
        post_payload = {
            "data": {
                "type": "tmx_async_downloads",
                "relationships": {
                    "project": {"data": {"type": "projects", "id": project_id}}
                },
            }
        }

        logger.debug(f"Sending Request to URL: {post_url}")
        sanitized_headers = transifex_headers.copy()
        if "Authorization" in sanitized_headers:
            sanitized_headers["Authorization"] = "Bearer [REDACTED]"
        logger.debug(f"Request Headers: {json.dumps(sanitized_headers, indent=2)}")
        logger.debug(f"Request Payload: {json.dumps(post_payload, indent=2)}")

        response = requests.post(
            post_url, headers=transifex_headers, data=json.dumps(post_payload)
        )
        response.raise_for_status()

        job_id = response.json()["data"]["id"]
        status_url = f"{TRANSIFEX_API_BASE_URL}/tmx_async_downloads/{job_id}"
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
        timeout = time.time() + 300  # 5-minute timeout
        file_content = None
        while time.time() < timeout:
            response = requests.get(status_url, headers=transifex_headers)
            response.raise_for_status()

            # The download endpoint can either return a JSON status or the file directly
            try:
                status_data = response.json()
                status = status_data["data"]["attributes"]["status"]
                if status == "completed":
                    download_url = status_data["data"]["links"]["download"]
                    logger.info("  > File ready for download.")
                    tmx_response = requests.get(download_url)
                    tmx_response.raise_for_status()
                    file_content = tmx_response.content
                    break
                elif status == "failed":
                    logger.error("Transifex reported the backup job failed.")
                    return False

                logger.debug(f"Current job status: '{status}'. Polling again in 5s.")
                time.sleep(5)

            except json.JSONDecodeError:
                # If the response isn't JSON, it's likely the file content itself.
                logger.info(
                    "  > Received non-JSON response, assuming it's the TMX file."
                )
                file_content = response.content
                break
        else:
            logger.error("TMX backup job timed out after 5 minutes.")
            return False

        if file_content:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"backup_{config.get('TRANSIFEX_PROJECT_SLUG')}_all_languages_{timestamp}.tmx"
            filepath = backup_path / filename
            with open(filepath, "wb") as f:
                f.write(file_content)
            logger.info(f"  > SUCCESS: Backup saved to {filepath}")
            return True
        else:
            logger.error(
                "File content was not retrieved despite a successful job status."
            )
            return False

    except requests.exceptions.HTTPError as http_err:
        logger.fatal("HTTP Error while checking backup status")
        logger.error(f"Status Code: {http_err.response.status_code}")
        logger.error(f"Response Body: {http_err.response.text}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during TMX backup polling: {e}")
        return False


def sync_logic_main(config: dict, log_callback: Callable[[str], None]) -> None:
    """
    This is the main function that runs the entire sync process.
    """
    logger = AppLogger(log_callback, config.get("LOG_LEVEL", "Normal"))
    logger.info("--- Starting Braze to Transifex Sync ---")

    # --- Retrieve Configuration ---
    braze_api_key = config.get("BRAZE_API_KEY")
    braze_rest_endpoint = config.get("BRAZE_REST_ENDPOINT")
    transifex_api_token = config.get("TRANSIFEX_API_TOKEN")
    transifex_org_slug = config.get("TRANSIFEX_ORGANIZATION_SLUG")
    transifex_project_slug = config.get("TRANSIFEX_PROJECT_SLUG")

    # --- Prepare API Headers ---
    braze_headers = {"Authorization": f"Bearer {braze_api_key}"}
    transifex_headers = {
        "Authorization": f"Bearer {transifex_api_token}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }

    # --- Define API Interaction Functions ---

    def fetch_braze_list(endpoint: str, list_key: str, limit: int = 100) -> list:
        all_items = []
        offset = 0
        while True:
            time.sleep(0.2)  # Basic rate limiting
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

    def fetch_braze_item_details(
        endpoint: str, id_param_name: str, item_id: str
    ) -> dict:
        time.sleep(0.2)  # Basic rate limiting
        url = f"{braze_rest_endpoint}{endpoint}?{id_param_name}={item_id}"
        logger.info(f"  > Fetching details for ID: {item_id}")
        logger.debug(f"Requesting URL: {url}")
        response = requests.get(url, headers=braze_headers)
        response.raise_for_status()
        return response.json()

    def create_or_update_transifex_resource(slug: str, name: str) -> None:
        resource_id = f"o:{transifex_org_slug}:p:{transifex_project_slug}:r:{slug}"
        url = f"{TRANSIFEX_API_BASE_URL}/resources/{resource_id}"
        logger.debug(f"Checking for resource at URL: {url}")
        response = requests.get(url, headers=transifex_headers)

        if response.status_code == 404:
            logger.info(f"  > Resource '{slug}' not found. Creating...")
            create_url = f"{TRANSIFEX_API_BASE_URL}/resources"
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
            existing_name = response.json()["data"]["attributes"]["name"]
            if existing_name != name:
                logger.info(
                    f"  > Resource '{slug}' found. Updating name from '{existing_name}' to '{name}'..."
                )
                patch_payload = {
                    "data": {
                        "type": "resources",
                        "id": resource_id,
                        "attributes": {"name": name},
                    }
                }
                patch_response = requests.patch(
                    url, headers=transifex_headers, data=json.dumps(patch_payload)
                )
                patch_response.raise_for_status()
                logger.info("  > Name updated successfully.")
            else:
                logger.info(f"  > Resource '{slug}' found with correct name '{name}'.")
        else:
            response.raise_for_status()

    def upload_source_content_to_transifex(
        content_dict: dict, resource_slug: str
    ) -> None:
        if not content_dict:
            logger.info("  > No content to upload. Skipping.")
            return
        logger.info(
            f"  > Preparing to upload {len(content_dict)} string(s) to resource '{resource_slug}'..."
        )
        url = f"{TRANSIFEX_API_BASE_URL}/resource_strings_async_uploads"
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
        logger.debug(
            f"Uploading content to {url} with payload: {json.dumps(payload, indent=2)}"
        )
        response = requests.post(
            url, headers=transifex_headers, data=json.dumps(payload)
        )
        response.raise_for_status()
        if response.status_code == 202:
            logger.info("  > Successfully started upload job.")

    # --- Main Execution Logic ---
    try:
        # Step 1: Perform TMX backup if enabled
        if config.get("BACKUP_ENABLED", False):
            if not perform_tmx_backup(config, transifex_headers, logger):
                logger.info("\n--- Sync halted due to backup failure. ---")
                return  # Stop execution if backup fails
            logger.info("--- TMX Backup complete. Proceeding with sync. ---\n")
        else:
            logger.info("TMX backup is disabled. Skipping.")

        # Step 2: Process Email Templates
        email_translatable_fields = ["subject", "preheader", "body"]
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

        # Step 3: Process Content Blocks
        block_translatable_fields = ["content"]
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

    # --- Global Error Handling ---
    except requests.exceptions.HTTPError as e:
        logger.fatal("An API error occurred.")
        if e.request:
            logger.error(f"URL: {e.request.url}")
        if e.response is not None:
            logger.error(f"Status Code: {e.response.status_code}")
            try:
                # Try to parse and print JSON error for better readability
                error_details = e.response.json()
                logger.error(f"Response: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                logger.error(f"Response: {e.response.text}")
        logger.error(
            "Please check that your API keys and endpoints in Settings are correct."
        )
    except requests.exceptions.ConnectionError:
        logger.fatal("A network connection error occurred.")
        logger.error("Could not connect to an API endpoint.")
        logger.error("Please check your internet connection and firewall settings.")
    except KeyError as e:
        logger.fatal("Received an unexpected response from an API.")
        logger.error(f"The expected field '{e}' was missing from the response data.")
        logger.error("This may indicate a change in the API. Please report this issue.")
    except Exception as e:
        logger.fatal("An unexpected error occurred during the sync process.")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Details: {str(e)}")
