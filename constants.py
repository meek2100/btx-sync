# constants.py

# --- Application Versioning ---
# Set this to the version number of your *next intended production release*.
NEXT_RELEASE_VERSION = "0.0.1"

# Set the pre-release type for 'develop' branch builds ("alpha", "beta", or "rc").
RELEASE_TYPE = "beta"

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
