import sys
from pathlib import Path
import importlib.util


def load_constants_from_path(file_path: Path):
    """Dynamically loads constants from a specified file path."""
    spec = importlib.util.spec_from_file_location("temp_constants", file_path)
    if spec is None:
        raise FileNotFoundError(f"Could not find {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        "NEXT_RELEASE_VERSION": getattr(module, "NEXT_RELEASE_VERSION", "0.0.0"),
        "RELEASE_TYPE": getattr(module, "RELEASE_TYPE", "alpha"),
    }


def parse_version_string(version_str: str) -> tuple:
    """Parses a version string into a comparable tuple."""
    parts = list(map(int, version_str.split(".")))
    return tuple(parts)


def main():
    try:
        # Get paths for current and develop branch versions of constants.py
        current_constants_path = Path("constants.py")
        develop_constants_path = Path(
            "develop_constants.py"
        )  # This will be copied by CI

        if not current_constants_path.exists():
            print(f"Error: {current_constants_path} not found in current branch.")
            sys.exit(1)

        # If develop_constants.py doesn't exist (e.g., first PR, or main branch)
        # then we only need to validate the current constants for basic format.
        # For simplicity, we'll focus on develop-to-develop PRs.
        if not develop_constants_path.exists():
            print(
                "No previous 'develop' branch constants found. "
                "Skipping version comparison. "
                "Ensure initial 'develop' version is set correctly."
            )
            sys.exit(0)  # Allow to pass if no base for comparison (e.g., first push)

        current_config = load_constants_from_path(current_constants_path)
        develop_config = load_constants_from_path(develop_constants_path)

        current_next_version = parse_version_string(
            current_config["NEXT_RELEASE_VERSION"]
        )
        develop_next_version = parse_version_string(
            develop_config["NEXT_RELEASE_VERSION"]
        )

        current_release_type = current_config["RELEASE_TYPE"]
        develop_release_type = develop_config["RELEASE_TYPE"]

        print(
            f"Current PR NEXT_RELEASE_VERSION: {current_config['NEXT_RELEASE_VERSION']} (type: {current_release_type})"
        )
        print(
            f"Develop branch NEXT_RELEASE_VERSION: {develop_config['NEXT_RELEASE_VERSION']} (type: {develop_release_type})"
        )

        # Rule 1: NEXT_RELEASE_VERSION must not decrease
        if current_next_version < develop_next_version:
            print(
                f"Error: NEXT_RELEASE_VERSION cannot decrease from "
                f"{develop_config['NEXT_RELEASE_VERSION']} to "
                f"{current_config['NEXT_RELEASE_VERSION']}."
            )
            sys.exit(1)

        # Rule 2: If NEXT_RELEASE_VERSION is the same, RELEASE_TYPE can only move
        #         from alpha to beta, or stay the same.
        if current_next_version == develop_next_version:
            if develop_release_type == "beta" and current_release_type == "alpha":
                print(
                    f"Error: Cannot transition from 'beta' to 'alpha' for the "
                    f"same NEXT_RELEASE_VERSION "
                    f"({current_config['NEXT_RELEASE_VERSION']}). "
                    f"A version bump is required for alpha."
                )
                sys.exit(1)
            elif (
                develop_release_type == "alpha" and current_release_type == "alpha"
            ) or (develop_release_type == "beta" and current_release_type == "beta"):
                print("NEXT_RELEASE_VERSION is same, RELEASE_TYPE is same. OK.")
            elif develop_release_type == "alpha" and current_release_type == "beta":
                print(
                    "NEXT_RELEASE_VERSION is same, RELEASE_TYPE moved "
                    "alpha -> beta. OK."
                )
            else:
                print(
                    f"Error: Invalid RELEASE_TYPE transition for "
                    f"NEXT_RELEASE_VERSION "
                    f"({current_config['NEXT_RELEASE_VERSION']}): "
                    f"'{develop_release_type}' -> '{current_release_type}'."
                )
                sys.exit(1)
        else:  # current_next_version > develop_next_version
            # Rule 3: If NEXT_RELEASE_VERSION increases, RELEASE_TYPE can be anything
            #         (typically restarts with 'alpha' or 'beta').
            print("NEXT_RELEASE_VERSION increased. Valid transition for RELEASE_TYPE.")

        print("Version validation successful!")
        sys.exit(0)

    except Exception as e:
        print(f"An unexpected error occurred during version validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
