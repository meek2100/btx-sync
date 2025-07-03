# constants.py

# Default settings for the application.
# These values are used when no setting is found in the OS keychain.

# Braze API default endpoint
DEFAULT_BRAZE_REST_ENDPOINT = "https://rest.iad-01.braze.com"

# Transifex API base URL (constant as it's not user-configurable)
TRANSIFEX_API_BASE_URL = "https://rest.api.transifex.com"

# Default path for TMX backups (User's Downloads directory)
DEFAULT_BACKUP_PATH_NAME = "Downloads"  # Used with pathlib.Path.home()

# Default logging level
DEFAULT_LOG_LEVEL = "Normal"

# Default state for TMX backup and auto-update features
DEFAULT_BACKUP_ENABLED = True
DEFAULT_AUTO_UPDATE_ENABLED = True

# Centralized translatable fields for easier maintenance.
EMAIL_TRANSLATABLE_FIELDS = ["subject", "preheader", "body"]
BLOCK_TRANSLATABLE_FIELDS = ["content"]

# --- Settings Keys ---
# Centralized keys for managing settings in the OS keychain.
KEY_BRAZE_API = "braze_api_key"
KEY_TX_API = "transifex_api_token"
KEY_BRAZE_ENDPOINT = "braze_endpoint"
KEY_TX_ORG = "transifex_org"
KEY_TX_PROJECT = "transifex_project"
KEY_BACKUP_PATH = "backup_path"
KEY_LOG_LEVEL = "log_level"
KEY_BACKUP_ENABLED = "backup_enabled"
KEY_AUTO_UPDATE = "auto_update_enabled"

# A single list of all managed keys, used for functions like resetting defaults.
MANAGED_SETTINGS_KEYS = [
    KEY_BRAZE_API,
    KEY_TX_API,
    KEY_BRAZE_ENDPOINT,
    KEY_TX_ORG,
    KEY_TX_PROJECT,
    KEY_BACKUP_PATH,
    KEY_LOG_LEVEL,
    KEY_BACKUP_ENABLED,
    KEY_AUTO_UPDATE,
]

# --- Development Flags ---
# Set to True to enable the auto-update check when running from source code.
# This is useful for testing the update process locally.
DEV_AUTO_UPDATE_ENABLED = True
