"""Build portable Rialo CLI invocations for Windows/WSL and native Linux."""

from __future__ import annotations

import os
import shlex


CLI_MODES = {"auto", "native", "wsl"}


def resolve_cli_mode(value: str) -> str:
    if value not in CLI_MODES:
        raise ValueError(f"unsupported Rialo CLI mode: {value}")
    if value == "auto":
        return "wsl" if os.name == "nt" else "native"
    return value


def shell_directory_expression(path: str) -> str:
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        suffix = path[2:]
        if not suffix:
            return '"$HOME"'
        return f'"$HOME"/{shlex.quote(suffix)}'
    return shlex.quote(path)


def build_shell_invocation(
    command: str,
    project_dir: str,
    *,
    cli_mode: str = "auto",
) -> list[str]:
    mode = resolve_cli_mode(cli_mode)
    script = (
        'export PATH="$HOME/.local/share/rialo/bin:$PATH"; '
        f"cd -- {shell_directory_expression(project_dir)} && {command}"
    )
    if mode == "wsl":
        return ["wsl.exe", "--", "bash", "-lc", script]
    return ["bash", "-lc", script]
