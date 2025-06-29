# Braze-Transifex Sync Tool

A cross-platform desktop application for synchronizing content from Braze to Transifex for translation. This tool allows non-technical users to easily pull content from Braze, upload it to Transifex, and manage translation workflows with a simple graphical user interface (GUI).

## Features

-   **Braze Content Extraction:** Fetches Email Templates and Content Blocks directly from the Braze API.
-   **Transifex Integration:** Creates a unique resource in Transifex for each Braze item, using the Braze ID as a stable slug and the Braze name as the human-readable resource name.
-   **TMX Backup:** Automatically performs a backup of your project's entire Translation Memory (TMX) file from Transifex before syncing, as a safety measure.
-   **Secure Credential Storage:** Uses the native OS keychain (`keyring`) to securely store your Braze and Transifex API keys. No sensitive information is stored in plaintext files.
-   **User-Friendly GUI:** A simple interface built with CustomTkinter for easy operation, with helpers and pop-ups to guide users.
-   **Configurable Settings:** An easy-to-use settings panel for configuring API keys, endpoints, and features like TMX backup.
-   **Robust Logging:** Provides clear feedback on the sync process, with an optional "Debug" mode for detailed API call inspection.

## Setup and Installation

To run this application from the source code, you'll need Python 3.10 or higher.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/braze-transifex-sync.git](https://github.com/your-username/braze-transifex-sync.git)
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

## Usage

1.  **Run the application:**
    ```bash
    python app.py
    ```

2.  **Configure Settings:**
    -   On the first launch, click the "Settings" button.
    -   Fill in your Braze and Transifex API keys, endpoints, and slugs. Use the "?" buttons for help.
    -   Configure your TMX backup preferences.
    -   Click "Save". Your credentials will be stored securely in your OS keychain.

3.  **Run the Sync:**
    -   Click the "Run Sync" button on the main window.
    -   Monitor the progress in the log window. The process is complete when the status returns to "Ready".

## Testing

This project uses `pytest` for unit testing. To run the test suite:

1.  Make sure you have installed the development dependencies (`pip install -r tests/requirements-dev.txt`).
2.  Run pytest from the project's root directory:
    ```bash
    pytest --cov=.
    ```

## Building the Executable

You can package the application into a single, standalone executable using `PyInstaller`.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Run the build command:**
    ```bash
    pyinstaller --onefile --windowed --name "BrazeTransifexSync" --icon="assets/icon.ico" app.py
    ```
    *(Ensure you have an `icon.ico` file in an `assets` folder or remove the `--icon` flag.)*

3.  The final executable will be located in the `dist` folder.
