import os
import shutil
import subprocess
import sys
from pathlib import Path


def compile_app() -> None:
    """Automates packaging of MediaFlow AI into a single distribution bundle using PyInstaller."""
    print("=== MediaFlow AI Packaging Engine ===")
    
    # 1. Verify dependencies
    try:
        import PyInstaller
    except ImportError:
        print("Error: 'pyinstaller' is not installed in the active environment.")
        print("Please run: pip install pyinstaller")
        sys.exit(1)

    root_dir = Path(__file__).parent.resolve()
    entry_point = root_dir / "app" / "main.py"
    
    if not entry_point.exists():
        print(f"Error: Entry point not found at: {entry_point}")
        sys.exit(1)

    print(f"Target entrypoint: {entry_point}")
    
    # 2. Build pyinstaller command parameters
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",  # Windowed mode for production deployment
        f"--name=FramePilot",
        # Add static resources
        f"--add-data={root_dir / 'config.yaml'}{os.pathsep}.",
        f"--add-data={root_dir / 'app' / 'ui' / 'themes'}{os.pathsep}app/ui/themes",
        str(entry_point)
    ]

    print("Running packaging subprocess:")
    print(" ".join(cmd))
    
    try:
        subprocess.run(cmd, check=True)
        # Copy config.yaml next to FramePilot.exe
        shutil.copy2(root_dir / "config.yaml", root_dir / "dist" / "FramePilot" / "config.yaml")
        print("\n=== SUCCESS ===")
        print("Application packaged successfully!")
        print(f"Executable folder exported to: {root_dir / 'dist' / 'FramePilot'}")
    except subprocess.CalledProcessError as e:
        print(f"\n=== FAILURE ===")
        print(f"PyInstaller execution failed with code: {e.returncode}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    compile_app()
