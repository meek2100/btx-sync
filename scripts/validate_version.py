# scripts/validate_version.py
import sys
from pathlib import Path
import importlib.util


def load_constants_from_path(file_path: Path):
    """Dynamically loads constants from a specified file path."""
    module_name = f"temp_constants_{file_path.stem}_{file_path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise FileNotFoundError(f"Could not find {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        "NEXT_RELEASE_VERSION": getattr(module, "NEXT_RELEASE_VERSION", "0.0.0"),
        "RELEASE_TYPE": getattr(module, "RELEASE_TYPE", "alpha"),
    }


def parse_version_string(version_str: str) -> tuple:
    """Parses a version string like '1.2.3' into a comparable tuple (1, 2, 3)."""
    try:
        parts = list(map(int, version_str.split(".")))
        return tuple(parts)
    except ValueError as e:
        print(f"Error: Invalid version format '{version_str}'. {e}")
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
        current_config = load_constants_from_path(current_constants_path)
        develop_config = load_constants_from_path(develop_constants_path)

        current_version = parse_version_string(current_config["NEXT_RELEASE_VERSION"])
        develop_version = parse_version_string(develop_config["NEXT_RELEASE_VERSION"])

        print(
            f"Current PR Version: {current_config['NEXT_RELEASE_VERSION']}-{current_config['RELEASE_TYPE']}"
        )
        print(
            f"Develop Version: {develop_config['NEXT_RELEASE_VERSION']}-{develop_config['RELEASE_TYPE']}"
        )

        if current_version < develop_version:
            print(
                f"Error: NEXT_RELEASE_VERSION cannot decrease from "
                f"{develop_config['NEXT_RELEASE_VERSION']} to {current_config['NEXT_RELEASE_VERSION']}."
            )
            sys.exit(1)

        if current_version == develop_version:
            precedence = {"alpha": 0, "beta": 1, "rc": 2}
            current_val = precedence.get(current_config["RELEASE_TYPE"])
            develop_val = precedence.get(develop_config["RELEASE_TYPE"])

            if current_val is None or develop_val is None:
                print(
                    f"Error: Invalid RELEASE_TYPE. Must be one of {list(precedence.keys())}."
                )
                sys.exit(1)

            if current_val < develop_val:
                print(
                    f"Error: Cannot regress release type from '{develop_config['RELEASE_TYPE']}' "
                    f"to '{current_config['RELEASE_TYPE']}' for the same version."
                )
                sys.exit(1)

        print("Version validation successful!")
        sys.exit(0)

    except Exception as e:
        print(f"An unexpected error occurred during version validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
