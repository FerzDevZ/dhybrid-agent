"""Go toolchain integration (go test, go vet, golangci-lint, gosec, go build, go fmt, go mod tidy)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_go_cmd(workspace: str, args: list[str], timeout: int = 120) -> str:
    """Run a go command in the workspace."""
    try:
        result = subprocess.run(
            ["go"] + args,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return f"ERROR (exit {result.returncode}):\n{result.stderr}\n{result.stdout}"
        return result.stdout or "OK (no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'go' command not found. Install Go toolchain."
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def _run_tool_cmd(workspace: str, tool: str, args: list[str], timeout: int = 120) -> str:
    """Run an external tool (golangci-lint, gosec, etc.)."""
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
        if result.returncode != 0 and output:
            return f"EXIT {result.returncode}:\n{output}"
        return output or "OK (no issues)"
    except subprocess.TimeoutExpired:
        return f"ERROR: {tool} timed out after {timeout}s"
    except FileNotFoundError:
        return f"ERROR: '{tool}' not installed. Install with: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def go_test(workspace: str, args: str = "") -> str:
    """Run go test in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments to pass to 'go test' (e.g., '-v', '-race', './...')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_go_cmd(workspace, cmd_args)


def go_vet(workspace: str, args: str = "") -> str:
    """Run go vet in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments (e.g., './...')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["vet"]
    if args:
        cmd_args.extend(args.split())
    return _run_go_cmd(workspace, cmd_args)


def go_fmt(workspace: str, args: str = "") -> str:
    """Run go fmt in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments (e.g., './...')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["fmt"]
    if args:
        cmd_args.extend(args.split())
    return _run_go_cmd(workspace, cmd_args)


def go_build(workspace: str, args: str = "") -> str:
    """Run go build in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments (e.g., '-o myapp', './...')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["build"]
    if args:
        cmd_args.extend(args.split())
    return _run_go_cmd(workspace, cmd_args)


def go_mod_tidy(workspace: str) -> str:
    """Run go mod tidy in the workspace.

    Args:
        workspace: Path to Go module directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    return _run_go_cmd(workspace, ["mod", "tidy"])


def golangci_lint(workspace: str, args: str = "") -> str:
    """Run golangci-lint in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments (e.g., '--fix', './...')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["run"]
    if args:
        cmd_args.extend(args.split())
    return _run_tool_cmd(workspace, "golangci-lint", cmd_args)


def gosec(workspace: str, args: str = "") -> str:
    """Run gosec security scanner in the workspace.

    Args:
        workspace: Path to Go module directory
        args: Additional arguments (e.g., './...', '-fmt=json')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "go.mod").exists():
        return f"ERROR: No go.mod found in {workspace}"
    
    cmd_args = ["-fmt=text"]
    if args:
        cmd_args.extend(args.split())
    return _run_tool_cmd(workspace, "gosec", cmd_args)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "go_test",
        "Run go test in a Go module workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        go_test,
    )
    reg.register(
        "go_vet",
        "Run go vet static analysis in a Go module workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        go_vet,
    )
    reg.register(
        "go_fmt",
        "Run go fmt to format Go source code.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        go_fmt,
    )
    reg.register(
        "go_build",
        "Run go build to compile Go packages.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        go_build,
    )
    reg.register(
        "go_mod_tidy",
        "Run go mod tidy to clean up module dependencies.",
        {"workspace": {"type": "string", "required": True}},
        go_mod_tidy,
    )
    reg.register(
        "golangci_lint",
        "Run golangci-lint for comprehensive Go linting.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        golangci_lint,
    )
    reg.register(
        "gosec",
        "Run gosec security scanner for Go code.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        gosec,
    )