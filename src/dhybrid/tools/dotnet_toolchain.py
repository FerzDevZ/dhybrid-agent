"""C#/.NET toolchain integration (dotnet test, dotnet build, dotnet restore, dotnet clean, dotnet format, dotnet ef migrations, dotnet outdated, dotnet tool install)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run_dotnet_cmd(workspace: str, args: list[str], timeout: int = 180) -> str:
    """Run a dotnet command in the workspace."""
    try:
        result = subprocess.run(
            ["dotnet"] + args,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 and output.strip():
            return f"EXIT {result.returncode}:\n{output}"
        return output or "OK (no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: dotnet command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'dotnet' command not found. Install .NET SDK from https://dotnet.microsoft.com/download"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def dotnet_test(workspace: str, args: str = "") -> str:
    """Run dotnet test in the workspace.

    Args:
        workspace: Path to .NET project directory
        args: Additional arguments to pass to 'dotnet test' (e.g., '--filter', '--logger')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        # Check for any .csproj file
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(workspace, cmd_args)


def dotnet_build(workspace: str, args: str = "") -> str:
    """Run dotnet build in the workspace.

    Args:
        workspace: Path to .NET project directory
        args: Additional arguments (e.g., '-c Release', '--no-restore')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    cmd_args = ["build"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(workspace, cmd_args)


def dotnet_restore(workspace: str, args: str = "") -> str:
    """Run dotnet restore in the workspace.

    Args:
        workspace: Path to .NET project directory
        args: Additional arguments
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    cmd_args = ["restore"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(workspace, cmd_args)


def dotnet_clean(workspace: str) -> str:
    """Run dotnet clean in the workspace.

    Args:
        workspace: Path to .NET project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    return _run_dotnet_cmd(workspace, ["clean"])


def dotnet_fmt(workspace: str, args: str = "") -> str:
    """Run dotnet format to format C# source code.

    Args:
        workspace: Path to .NET project directory
        args: Additional arguments (e.g., '--check', '--verbosity detailed')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    cmd_args = ["format"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(workspace, cmd_args)


def dotnet_format(workspace: str, args: str = "") -> str:
    """Alias for dotnet_fmt - run dotnet format."""
    return dotnet_fmt(workspace, args)


def dotnet_tool_install(tool: str, args: str = "") -> str:
    """Install a .NET global tool.

    Args:
        tool: Tool name (e.g., 'dotnet-ef', 'dotnet-outdated')
        args: Additional arguments (e.g., '--version 8.0.0')
    """
    cmd_args = ["tool", "install", "--global"]
    if args:
        cmd_args.extend(args.split())
    cmd_args.append(tool)
    return _run_dotnet_cmd(".", cmd_args)


def dotnet_outdated(workspace: str) -> str:
    """Check for outdated NuGet packages.

    Args:
        workspace: Path to .NET project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    # Try dotnet-outdated tool
    return _run_dotnet_cmd(workspace, ["tool", "install", "--global", "dotnet-outdated"])
    # Then run it
    result = _run_dotnet_cmd(workspace, ["dotnet-outdated"])
    return result


def dotnet_ef_migrations(workspace: str, args: str = "") -> str:
    """Run Entity Framework Core migrations.

    Args:
        workspace: Path to .NET project directory
        args: Additional arguments (e.g., 'add InitialCreate', 'remove')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "*.csproj").exists():
        csproj_files = list(workspace_path.glob("*.csproj"))
        if not csproj_files:
            return f"ERROR: No .csproj found in {workspace}"
    
    cmd_args = ["ef", "migrations"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(workspace, cmd_args)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "dotnet_test",
        "Run dotnet test in a .NET project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_test,
    )
    reg.register(
        "dotnet_build",
        "Run dotnet build to compile a .NET project.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_build,
    )
    reg.register(
        "dotnet_restore",
        "Run dotnet restore to restore NuGet packages.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_restore,
    )
    reg.register(
        "dotnet_clean",
        "Run dotnet clean to clean build artifacts.",
        {"workspace": {"type": "string", "required": True}},
        dotnet_clean,
    )
    reg.register(
        "dotnet_fmt",
        "Run dotnet format to format C# source code.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_fmt,
    )
    reg.register(
        "dotnet_format",
        "Alias for dotnet_fmt - run dotnet format.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_format,
    )
    reg.register(
        "dotnet_tool_install",
        "Install a .NET global tool (e.g., dotnet-ef, dotnet-outdated).",
        {"tool": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_tool_install,
    )
    reg.register(
        "dotnet_outdated",
        "Check for outdated NuGet packages.",
        {"workspace": {"type": "string", "required": True}},
        dotnet_outdated,
    )
    reg.register(
        "dotnet_ef_migrations",
        "Run Entity Framework Core migrations.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        dotnet_ef_migrations,
    )