"""Rust toolchain integration (cargo test, cargo build, cargo clippy, cargo fmt, cargo audit, cargo check, cargo update)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_cargo_cmd(workspace: str, args: list[str], timeout: int = 180) -> str:
    """Run a cargo command in the workspace."""
    try:
        result = subprocess.run(
            ["cargo"] + args,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 and output.strip():
            return f"EXIT {result.returncode}:\n{output}"
        return output or "OK (no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: cargo command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'cargo' command not found. Install Rust toolchain from https://rustup.rs/"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def _run_tool_cmd(workspace: str, tool: str, args: list[str], timeout: int = 120) -> str:
    """Run an external tool (cargo-audit, etc.)."""
    try:
        result = subprocess.run(
            [tool] + args,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 and output.strip():
            return f"EXIT {result.returncode}:\n{output}"
        return output or "OK (no issues)"
    except subprocess.TimeoutExpired:
        return f"ERROR: {tool} timed out after {timeout}s"
    except FileNotFoundError:
        return f"ERROR: '{tool}' not installed. Install with: cargo install cargo-audit"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def cargo_test(workspace: str, args: str = "") -> str:
    """Run cargo test in the workspace.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments to pass to 'cargo test' (e.g., '--lib', '--bins', '-- --nocapture')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_build(workspace: str, args: str = "") -> str:
    """Run cargo build in the workspace.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '--release', '--lib', '--bins')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["build"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_check(workspace: str, args: str = "") -> str:
    """Run cargo check in the workspace (fast type-checking without codegen).

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '--lib', '--bins')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["check"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_fmt(workspace: str, args: str = "") -> str:
    """Run cargo fmt to format Rust source code.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '--check', '--all')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["fmt"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_clippy(workspace: str, args: str = "") -> str:
    """Run cargo clippy for linting.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '-- -D warnings', '--fix')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["clippy"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_audit(workspace: str, args: str = "") -> str:
    """Run cargo audit for security vulnerability scanning.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '--json', '--deny warnings')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    return _run_tool_cmd(workspace, "cargo-audit", ["audit"] + (args.split() if args else []))


def cargo_update(workspace: str, args: str = "") -> str:
    """Run cargo update to update dependencies.

    Args:
        workspace: Path to Cargo project directory
        args: Additional arguments (e.g., '-p package_name', '--precise version')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    cmd_args = ["update"]
    if args:
        cmd_args.extend(args.split())
    return _run_cargo_cmd(workspace, cmd_args)


def cargo_outdated(workspace: str) -> str:
    """Run cargo outdated to check for outdated dependencies.

    Args:
        workspace: Path to Cargo project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "Cargo.toml").exists():
        return f"ERROR: No Cargo.toml found in {workspace}"
    
    return _run_tool_cmd(workspace, "cargo-outdated", [])


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "cargo_test",
        "Run cargo test in a Rust project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_test,
    )
    reg.register(
        "cargo_build",
        "Run cargo build to compile a Rust project.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_build,
    )
    reg.register(
        "cargo_check",
        "Run cargo check for fast type-checking without codegen.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_check,
    )
    reg.register(
        "cargo_fmt",
        "Run cargo fmt to format Rust source code.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_fmt,
    )
    reg.register(
        "cargo_clippy",
        "Run cargo clippy for linting and best practices.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_clippy,
    )
    reg.register(
        "cargo_audit",
        "Run cargo audit for security vulnerability scanning.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_audit,
    )
    reg.register(
        "cargo_update",
        "Run cargo update to update dependencies in Cargo.lock.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        cargo_update,
    )
    reg.register(
        "cargo_outdated",
        "Run cargo outdated to check for outdated dependencies.",
        {"workspace": {"type": "string", "required": True}},
        cargo_outdated,
    )