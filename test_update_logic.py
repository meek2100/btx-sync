import sys
import shutil
from pathlib import Path
from tufup.client import Client

# --- Configuration ---
# Use an old version to ensure an update is found.
LOCAL_APP_VERSION = "0.0.1a20250701"

APP_NAME = "btx-sync"
UPDATE_URL = "https://meek2100.github.io/btx-sync/"

# --- Test Logic ---
if __name__ == "__main__":
    print("--- Running Local Update-Logic Test ---")
    script_dir = Path(__file__).parent.resolve()
    app_data_dir = Path.home() / f".{APP_NAME}"

    print(f"Simulating local app version: {LOCAL_APP_VERSION}")

    if app_data_dir.exists():
        print(f"Clearing previous cache: {app_data_dir}")
        shutil.rmtree(app_data_dir)

    project_root_json = script_dir / "repository" / "metadata" / "root.json"
    print(f"Looking for initial root metadata at: {project_root_json}")

    if not project_root_json.exists():
        print("\n[FATAL ERROR] Cannot find initial root.json.")
        sys.exit(1)

    metadata_dir = app_data_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(project_root_json, metadata_dir / "root.json")
    print("Successfully copied initial root.json to cache directory.")

    try:
        print("\nInitializing tufup.Client...")
        client = Client(
            app_name=APP_NAME,
            app_install_dir=script_dir / "dist",
            current_version=LOCAL_APP_VERSION,
            metadata_dir=metadata_dir,
            target_dir=app_data_dir / "targets",
            metadata_base_url=f"{UPDATE_URL}metadata/",
            target_base_url=f"{UPDATE_URL}targets/",
        )

        print('\nCalling client.check_for_updates(pre="a")...')
        new_update = client.check_for_updates(pre="a")

        if new_update:
            print("\n" + "*" * 20)
            print("--- [SUCCESS] Update Target Found! ---")
            print(f"New version available: {new_update.version}")

            print("\n--- Available functions on the `client` object: ---")
            print([m for m in dir(client) if not m.startswith("_")])

            print("\n--- Available functions on the `new_update` object: ---")
            print([m for m in dir(new_update) if not m.startswith("_")])
            print("*" * 20)

        else:
            print("\n--- [FAILURE] No Update Found ---")

    except Exception as e:
        print("\n--- [ERROR] An exception occurred ---")
        print(e)
