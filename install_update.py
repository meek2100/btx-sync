# install_update.py
import sys
import shutil
from pathlib import Path


def install(app_install_dir: Path, archive_dir: Path):
    """
    A simple, non-interactive install script that replaces the contents
    of the installation directory with the contents of the archive directory.
    """
    if not app_install_dir.is_dir() or not archive_dir.is_dir():
        sys.exit(1)

    # Overwrite the destination with the new version
    shutil.copytree(archive_dir, app_install_dir, dirs_exist_ok=True)

    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        install(
            app_install_dir=Path(sys.argv[1]),
            archive_dir=Path(sys.argv[2]),
        )
    else:
        sys.exit(1)
