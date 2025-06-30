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
    cd braze-transifex-sync
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

5.  **Run the application:**
    ```bash
    python app.py
    ```

### Testing

This project uses `pytest` for unit testing. To run the test suite:

1.  Make sure you have installed the development dependencies.
2.  Run pytest from the project's root directory:
    ```bash
    pytest --cov=.
    ```

### Building the Executable

You can package the application into a single, standalone executable using `PyInstaller`.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Run the build command:**
    This command includes the necessary flags to bundle the assets folder and the README file.
    ```bash
    pyinstaller --onefile --windowed --name "btx-sync" --icon="assets/icon.ico" --add-data "assets:assets" --add-data "README.md:." app.py
    ```