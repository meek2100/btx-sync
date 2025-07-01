# btx sync

A cross-platform desktop application for synchronizing content from Braze to Transifex for translation. This tool allows non-technical users to easily pull content from Braze, upload it to Transifex, and manage translation workflows with a simple graphical user interface (GUI).

## Features

-   **Braze Content Extraction:** Fetches Email Templates and Content Blocks directly from the Braze API.
-   **Transifex Integration:** Creates a unique resource in Transifex for each Braze item, using the Braze ID as a stable slug and the Braze name as the human-readable resource name.
-   **TMX Backup:** Automatically performs a backup of your project's entire Translation Memory (TMX) file from Transifex before syncing, as a safety measure.
-   **Secure Credential Storage:** Uses the native OS keychain (`keyring`) to securely store your Braze and Transifex API keys. No sensitive information is stored in plaintext files.
-   **User-Friendly GUI:** A simple interface built with CustomTkinter for easy operation, with helpers and pop-ups to guide users.
-   **Configurable Settings:** An easy-to-use settings panel for configuring API keys, endpoints, and features like TMX backup.
-   **Robust Logging:** Provides clear feedback on the sync process, with an optional "Debug" mode for detailed API call inspection.

## How It Works

This tool automates the process of preparing Braze content for professional translation via Transifex.

1.  **Connects to Braze:** It uses the Braze API to fetch all of your **Email Templates** and **Content Blocks**.
2.  **Creates Transifex Resources:** For each item from Braze, it creates a corresponding "resource" in your Transifex project.
    * The **Braze ID** (e.g., `email_template_id`) is used as the `slug` in Transifex. This creates a stable, unique identifier that won't change even if the name does.
    * The **Braze Name** (e.g., `template_name`) is used as the display `name` in Transifex, making it easy for translators to identify the content.
3.  **Extracts Content:** It extracts the text from translatable fields (like `subject` and `body`) from each Braze item.
4.  **Uploads for Translation:** This extracted text is uploaded as the "source strings" to the corresponding resource in Transifex, ready for your translation team to get to work.

---
## For End-Users

### Installation

1.  Go to the **[Releases Page](https://github.com/meek2100/btx-sync/releases)** on GitHub.
2.  Under the latest release, download the executable file for your operating system (e.g., `btx-sync-Windows.exe` for Windows, `btx-sync-macOS.zip` for macOS).
3.  For macOS, unzip the downloaded file to get the application. Move the application to your "Applications" folder.
4.  Run the application.

### Usage

1.  **Configure Settings:**
    -   On the first launch, click the "⋮" button in the top right and select "Settings".
    -   Fill in your Braze and Transifex API keys, endpoints, and slugs. Use the "?" buttons for help.
    -   Configure your TMX backup preferences.
    -   Click "Save". Your credentials will be stored securely in your OS keychain.

2.  **Run the Sync:**
    -   Once configured, the status will show "Ready".
    -   Click the "Run Sync" button on the main window.
    -   Monitor the progress in the log window. The process is complete when the status returns to "Ready".

---
## For Developers

### Development Setup

To run this application from the source code, you'll need Python 3.10 or higher.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/meek2100/btx-sync.git](https://github.com/meek2100/btx-sync.git)
    cd btx-sync
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv .venv
    .venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install core dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **(Optional) Install development dependencies for testing:**
    ```bash
    pip install -r tests/requirements-dev.txt
    ```

5.  **(Optional) Create Placeholder Version File:**
    To prevent linter errors like `Import "version" could not be resolved` in your IDE, create a local placeholder file. This file is ignored by Git.
    ```bash
    echo '__version__ = "0.0.0-dev"' > version.py
    ```

6.  **Run the application:**
    ```bash
    python app.py
    ```

### Releasing a New Version

The application version is derived automatically from Git tags. To release a new version:

1.  Ensure all changes are committed to the `main` branch.
2.  Create a new Git tag with a 'v' prefix (e.g., `v1.1.0`).
3.  Push the tag to the repository (`git push --tags`). This will trigger the release workflow.

### Testing

This project uses `pytest` for unit testing. To run the test suite:

1.  Make sure you have installed the development dependencies.
2.  Run pytest from the project's root directory:
    ```bash
    pytest --cov=.
    ```

### Building the Executable

You can package the application into a standalone executable using `PyInstaller`. This command mirrors the production build process.

```bash
# For Windows
pyinstaller --onefile --windowed --name "btx-sync" --icon="assets/icon.ico" --add-data "assets;assets" --add-data "README.md;." app.py

# For macOS/Linux
pyinstaller --onefile --windowed --name "btx-sync" --icon="assets/icon.icns" --add-data "assets:assets" --add-data "README.md:." app.py