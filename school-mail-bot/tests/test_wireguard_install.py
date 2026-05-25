import subprocess
from pathlib import Path


def test_script_syntax_is_valid() -> None:
    """Verifies that the bash script contains no syntax errors."""
    script_path = Path(__file__).parents[2] / "wireguard-install.sh"
    assert script_path.exists(), "Script file does not exist"

    # Use relative posix path to prevent Windows backslash issues in git bash / WSL
    cwd_resolved = Path.cwd().resolve()
    script_resolved = script_path.resolve()

    cwd_parts = cwd_resolved.parts
    script_parts = script_resolved.parts

    common_len = 0
    for p1, p2 in zip(cwd_parts, script_parts):
        if p1.lower() == p2.lower():
            common_len += 1
        else:
            break

    up_count = len(cwd_parts) - common_len
    down_parts = script_parts[common_len:]
    relative_parts = [".."] * up_count + list(down_parts)
    path_str = "/".join(relative_parts) if relative_parts else "."

    # Run bash syntax check: bash -n <script>
    result = subprocess.run(["bash", "-n", path_str], capture_output=True, text=True)
    assert result.returncode == 0, f"Bash syntax check failed:\n{result.stderr}"
