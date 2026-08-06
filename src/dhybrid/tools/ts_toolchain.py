"""TypeScript/Node toolchain integration (npm test, npm build, tsc, eslint, jest, vitest, npm install, npm audit)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _find_package_json(workspace: str) -> Path | None:
    """Find package.json file in workspace or subdirectories (for monorepos)."""
    workspace_path = Path(workspace)
    # Check root first
    if (workspace_path / "package.json").exists():
        return workspace_path
    # Search subdirectories for monorepo packages
    for pkg_json in workspace_path.rglob("package.json"):
        # Skip node_modules
        if "node_modules" not in pkg_json.parts:
            return pkg_json.parent
    return None


def _find_tsconfig(workspace: str) -> Path | None:
    """Find tsconfig.json file in workspace or subdirectories."""
    workspace_path = Path(workspace)
    # Check root first
    if (workspace_path / "tsconfig.json").exists():
        return workspace_path
    # Search subdirectories
    for tsconfig in workspace_path.rglob("tsconfig.json"):
        if "node_modules" not in tsconfig.parts:
            return tsconfig.parent
    return None


def _run_npm_cmd(workspace: str, args: list[str], timeout: int = 180) -> str:
    """Run an npm command in the workspace."""
    try:
        result = subprocess.run(
            ["npm"] + args,
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
        return f"ERROR: npm command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'npm' command not found. Install Node.js from https://nodejs.org/"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def _run_npx_cmd(workspace: str, args: list[str], timeout: int = 180) -> str:
    """Run an npx command in the workspace."""
    try:
        result = subprocess.run(
            ["npx"] + args,
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
        return f"ERROR: npx command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'npx' command not found. Install Node.js from https://nodejs.org/"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


def npm_test(workspace: str, args: str = "") -> str:
    """Run npm test in the workspace.

    Args:
        workspace: Path to Node.js project directory (or parent of monorepo)
        args: Additional arguments to pass to 'npm test'
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_npm_cmd(str(pkg_dir), cmd_args)


def npm_build(workspace: str, args: str = "") -> str:
    """Run npm build in the workspace.

    Args:
        workspace: Path to Node.js project directory (or parent of monorepo)
        args: Additional arguments to pass to 'npm run build'
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["run", "build"]
    if args:
        cmd_args.extend(args.split())
    return _run_npm_cmd(str(pkg_dir), cmd_args)


def npm_install(workspace: str, args: str = "") -> str:
    """Run npm install in the workspace.

    Args:
        workspace: Path to Node.js project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--save-dev package-name', '--production')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["install"]
    if args:
        cmd_args.extend(args.split())
    return _run_npm_cmd(str(pkg_dir), cmd_args)


def npm_audit(workspace: str, args: str = "") -> str:
    """Run npm audit for security vulnerability scanning.

    Args:
        workspace: Path to Node.js project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--json', '--audit-level=high')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["audit"]
    if args:
        cmd_args.extend(args.split())
    return _run_npm_cmd(str(pkg_dir), cmd_args)


def tsc_check(workspace: str, args: str = "") -> str:
    """Run TypeScript compiler (tsc) for type checking.

    Args:
        workspace: Path to TypeScript project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--noEmit', '--strict')
    """
    ts_dir = _find_tsconfig(workspace)
    if ts_dir is None:
        return f"ERROR: No tsconfig.json found in {workspace} or subdirectories"
    
    cmd_args = ["tsc", "--noEmit"]
    if args:
        cmd_args.extend(args.split())
    return _run_npx_cmd(str(ts_dir), cmd_args)


def eslint_check(workspace: str, args: str = "") -> str:
    """Run ESLint for linting JavaScript/TypeScript code.

    Args:
        workspace: Path to project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--fix', '--ext .ts,.tsx')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["eslint", "."]
    if args:
        cmd_args.extend(args.split())
    return _run_npx_cmd(str(pkg_dir), cmd_args)


def jest_test(workspace: str, args: str = "") -> str:
    """Run Jest tests.

    Args:
        workspace: Path to project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--coverage', '--watch')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["jest"]
    if args:
        cmd_args.extend(args.split())
    return _run_npx_cmd(str(pkg_dir), cmd_args)


def vitest_test(workspace: str, args: str = "") -> str:
    """Run Vitest tests.

    Args:
        workspace: Path to project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--run', '--coverage')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["vitest", "run"]
    if args:
        cmd_args.extend(args.split())
    return _run_npx_cmd(str(pkg_dir), cmd_args)


def prettier_fmt(workspace: str, args: str = "") -> str:
    """Run Prettier for code formatting.

    Args:
        workspace: Path to project directory (or parent of monorepo)
        args: Additional arguments (e.g., '--write', '--check')
    """
    pkg_dir = _find_package_json(workspace)
    if pkg_dir is None:
        return f"ERROR: No package.json found in {workspace} or subdirectories"
    
    cmd_args = ["prettier", "."]
    if args:
        cmd_args.extend(args.split())
    return _run_npx_cmd(str(pkg_dir), cmd_args)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "npm_test",
        "Run npm test in a Node.js project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        npm_test,
    )
    reg.register(
        "npm_build",
        "Run npm run build in a Node.js project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        npm_build,
    )
    reg.register(
        "npm_install",
        "Run npm install to install dependencies.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        npm_install,
    )
    reg.register(
        "npm_audit",
        "Run npm audit for security vulnerability scanning.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        npm_audit,
    )
    reg.register(
        "tsc_check",
        "Run TypeScript compiler (tsc) for type checking.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        tsc_check,
    )
    reg.register(
        "eslint_check",
        "Run ESLint for JavaScript/TypeScript linting.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        eslint_check,
    )
    reg.register(
        "jest_test",
        "Run Jest tests.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        jest_test,
    )
    reg.register(
        "vitest_test",
        "Run Vitest tests.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        vitest_test,
    )
    reg.register(
        "prettier_fmt",
        "Run Prettier for code formatting.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        prettier_fmt,
    )