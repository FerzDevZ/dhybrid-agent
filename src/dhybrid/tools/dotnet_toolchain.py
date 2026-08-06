"""C#/.NET toolchain integration (dotnet test, dotnet build, dotnet restore, dotnet clean, dotnet format, dotnet ef migrations, dotnet outdated, dotnet tool install)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _find_dotnet_project(workspace: str) -> Path | None:
    """Find .csproj/.sln file in workspace or subdirectories (for multi-project solutions)."""
    workspace_path = Path(workspace)
    # Check root first for solution file
    for sln in workspace_path.glob("*.sln"):
        return workspace_path
    # Check root first for project file
    for csproj in workspace_path.glob("*.csproj"):
        return workspace_path
    # Search subdirectories for solution file
    for sln in workspace_path.rglob("*.sln"):
        if "bin" not in sln.parts and "obj" not in sln.parts:
            return sln.parent
    # Search subdirectories for project file
    for csproj in workspace_path.rglob("*.csproj"):
        if "bin" not in csproj.parts and "obj" not in csproj.parts:
            return csproj.parent
    return None


def _run_dotnet_cmd(workspace: str, args: list[str], timeout: int = 180) -> str:
    """Run a dotnet command in the workspace."""
    try:
        result = subprocess.run(
            ["dotnet"] + args,
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
        return f"ERROR: dotnet command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'dotnet' command not found. Install .NET SDK from https://dotnet.microsoft.com/download"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def dotnet_test(workspace: str, args: str = "") -> str:
    """Run dotnet test in the workspace.

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
        args: Additional arguments (e.g., '--filter FullyQualifiedName~MyTest', '--no-build')
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(str(proj_dir), cmd_args)


def dotnet_build(workspace: str, args: str = "") -> str:
    """Run dotnet build in the workspace.

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
        args: Additional arguments (e.g., '--configuration Release', '--no-restore')
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    cmd_args = ["build"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(str(proj_dir), cmd_args)


def dotnet_restore(workspace: str) -> str:
    """Run dotnet restore in the workspace.

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    return _run_dotnet_cmd(str(proj_dir), ["restore"])


def dotnet_clean(workspace: str) -> str:
    """Run dotnet clean in the workspace.

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    return _run_dotnet_cmd(str(proj_dir), ["clean"])


def dotnet_fmt(workspace: str, args: str = "") -> str:
    """Run dotnet format in the workspace (requires dotnet-format tool).

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
        args: Additional arguments (e.g., '--verify-no-changes', '--include-generated')
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    cmd_args = ["format"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(str(proj_dir), cmd_args)


def dotnet_format(workspace: str, args: str = "") -> str:
    """Run dotnet format (alias for dotnet_fmt)."""
    return dotnet_fmt(workspace, args)


def dotnet_tool_install(workspace: str, tool: str) -> str:
    """Install a .NET global tool.

    Args:
        workspace: Path to project directory
        tool: Tool package name (e.g., 'dotnet-ef', 'dotnet-outdated-tool')
    """
    return _run_dotnet_cmd(workspace, ["tool", "install", "--global", tool])


def dotnet_outdated(workspace: str) -> str:
    """Run dotnet-outdated-tool to check for outdated packages (requires dotnet-outdated-tool).

    Args:
        workspace: Path to .NET project/solution directory (or parent of multi-project solution)
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    return _run_dotnet_cmd(str(proj_dir), ["outdated"])


def dotnet_ef_migrations(workspace: str, args: str = "") -> str:
    """Run dotnet ef migrations (requires dotnet-ef tool).

    Args:
        workspace: Path to .NET project directory (or parent of multi-project solution)
        args: Additional arguments (e.g., 'add InitialCreate', 'list', 'script')
    """
    proj_dir = _find_dotnet_project(workspace)
    if proj_dir is None:
        return f"ERROR: No .csproj or .sln found in {workspace} or subdirectories"
    
    cmd_args = ["ef", "migrations"]
    if args:
        cmd_args.extend(args.split())
    return _run_dotnet_cmd(str(proj_dir), cmd_args)


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