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

### Secure Automatic Updates

This application includes a secure, automatic update feature to ensure you always have the latest version.

-   **On Startup**: The app quietly checks for new versions in the background.
-   **Secure**: All updates are cryptographically signed using The Update Framework (TUF) to verify they are from the developer and have not been tampered with.
-   **Seamless**: If an update is found, it will be downloaded and installed automatically. You will be prompted to restart the application to complete the process.
-   **Control**: You can disable this feature at any time in the Settings panel.

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

4.  **Install development dependencies for testing:**
    ```bash
    pip install -r tests/requirements-dev.txt
    ```

5.  **(Optional) Create Placeholder Version File:**
    To prevent linter errors in your IDE, create a local version file. This file is ignored by Git.
    ```bash
    echo '__version__ = "0.0.0-dev"' > version.py
    ```

6.  **Run the application:**
    ```bash
    python app.py
    ```

### Testing

This project uses **pytest** for unit and integration testing and is configured to measure code coverage. We aim for high test coverage to ensure reliability and prevent regressions.

1.  **Run All Tests:**
    To run the full test suite and generate a coverage report, run the following command from the project's root directory:
    ```bash
    pytest --cov=.
    ```

2.  **Testing Philosophy:**
    -   **Unit Tests:** Core logic, API clients, and utility functions are tested in isolation. External dependencies like `requests` and `keyring` are mocked to ensure tests are fast and predictable.
    -   **Error Handling:** Tests are designed to cover not just the "happy path" but also various error conditions, such as API failures, network issues, and unexpected data formats.
    -   **CI/CD:** The full test suite is run automatically via GitHub Actions on every push and pull request to the `main` and `develop` branches, ensuring that no new changes break existing functionality.