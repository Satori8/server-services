import subprocess
from pathlib import Path


def test_script_syntax_is_valid() -> None:
    """Verifies that the bash script contains no syntax errors."""
    script_path = Path(__file__).parents[2] / "wireguard-install.sh"
    assert script_path.exists(), "Script file does not exist"

    # Use relative posix path to prevent Windows backslash issues in git bash / WSL
    try:
        path_str = script_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        path_str = script_path.as_posix()

    # Run bash syntax check: bash -n <script>
    result = subprocess.run(["bash", "-n", path_str], capture_output=True, text=True)
    assert result.returncode == 0, f"Bash syntax check failed:\n{result.stderr}"
