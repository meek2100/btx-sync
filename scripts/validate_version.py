# scripts/validate_version.py
import sys
from pathlib import Path
import importlib.util


def load_version_from_path(file_path: Path) -> str:
    """Dynamically loads NEXT_RELEASE_VERSION from a constants file."""
    module_name = f"temp_constants_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise FileNotFoundError(f"Could not find {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "NEXT_RELEASE_VERSION", "0.0.0")


def parse_version_string(version_str: str) -> tuple:
    """Parses a version string like '1.2.3' into a comparable tuple (1, 2, 3)."""
    try:
        parts = list(map(int, version_str.split(".")))
        return tuple(parts)
    except ValueError:
        print(f"Error: Invalid version format '{version_str}'. Must be e.g., '1.2.3'")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Error: Path to develop branch's constants.py not provided.")
        sys.exit(1)

    develop_constants_path = Path(sys.argv[1])
    current_constants_path = Path("constants.py")

    if not current_constants_path.exists():
        print(f"Error: {current_constants_path} not found in current branch.")
        sys.exit(1)

    if not develop_constants_path.exists():
        print("No 'develop' branch constants found. Skipping version comparison.")
        sys.exit(0)

    try:
        current_version_str = load_version_from_path(current_constants_path)
        develop_version_str = load_version_from_path(develop_constants_path)

        current_version = parse_version_string(current_version_str)
        develop_version = parse_version_string(develop_version_str)

        print(f"Current PR NEXT_RELEASE_VERSION: {current_version_str}")
        print(f"Develop branch NEXT_RELEASE_VERSION: {develop_version_str}")

        # Rule: NEXT_RELEASE_VERSION must not decrease.
        if current_version < develop_version:
            print(
                f"Error: NEXT_RELEASE_VERSION cannot decrease from "
                f"{develop_version_str} to {current_version_str}."
            )
            sys.exit(1)

        print("Version validation successful!")
        sys.exit(0)

    except Exception as e:
        print(f"An unexpected error occurred during version validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
