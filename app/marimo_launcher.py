from pathlib import Path
import subprocess
import sys


def main() -> int:
    notebook_path = Path(__file__).resolve().parent.parent / "docs" / "marimo_acoustics.py"
    command = ["marimo", "edit", str(notebook_path)]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
