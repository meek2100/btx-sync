import sys
import shutil
from pathlib import Path
from tufup.client import Client

# --- Configuration ---
# Simulate an old alpha version
LOCAL_APP_VERSION = "0.0.1a20250701"

APP_NAME = "btx-sync"
UPDATE_URL = "https://meek2100.github.io/btx-sync/"

# --- Test Logic ---
if __name__ == "__main__":
    print("--- Running Local Update-Logic Test ---")
    print(f"Simulating local app version: {LOCAL_APP_VERSION}")
    print(f"Checking server at: {UPDATE_URL}")

    app_data_dir = Path.home() / f".{APP_NAME}"
    metadata_dir = app_data_dir / "metadata"
    target_dir = app_data_dir / "targets"

    if app_data_dir.exists():
        print(f"Clearing previous cache: {app_data_dir}")
        shutil.rmtree(app_data_dir)

    project_root_json = Path("repository/metadata/root.json")
    local_root_path = metadata_dir / "root.json"
    if project_root_json.exists():
        metadata_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(project_root_json, local_root_path)
        print(f"Copied initial root.json to {local_root_path}")
    else:
        print(f"[ERROR] Cannot find initial root.json at {project_root_json}")
        sys.exit(1)

    try:
        print("\nInitializing tufup.Client...")
        client = Client(
            app_name=APP_NAME,
            app_install_dir=Path("."),
            current_version=LOCAL_APP_VERSION,
            metadata_dir=metadata_dir,
            target_dir=target_dir,
            metadata_base_url=f"{UPDATE_URL}metadata/",
            target_base_url=f"{UPDATE_URL}targets/",
        )
        print("Initialization complete.")

        print('\nCalling client.check_for_updates(pre="a")...')
        # FIX: Pass the `pre` argument
        new_update = client.check_for_updates(pre="a")
        print("Call complete.")

        if new_update:
            print("\n--- [SUCCESS] Update Found! ---")
            print(f"New version available: {new_update.version}")
        else:
            print("\n--- [FAILURE] No Update Found ---")

    except Exception as e:
        print("\n--- [ERROR] An exception occurred ---")
        print(e)
