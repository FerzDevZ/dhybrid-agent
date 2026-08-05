"""Java toolchain integration (mvn test, mvn build, mvn compile, mvn package, mvn clean, gradle test, gradle build, gradle check, spotbugs, checkstyle)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_mvn_cmd(workspace: str, args: list[str], timeout: int = 300) -> str:
    """Run a maven command in the workspace."""
    try:
        result = subprocess.run(
            ["mvn"] + args,
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
        return f"ERROR: maven command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'mvn' command not found. Install Maven from https://maven.apache.org/"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def _run_gradle_cmd(workspace: str, args: list[str], timeout: int = 300) -> str:
    """Run a gradle command in the workspace."""
    try:
        result = subprocess.run(
            ["gradle"] + args,
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
        return f"ERROR: gradle command timed out after {timeout}s"
    except FileNotFoundError:
        return "ERROR: 'gradle' command not found. Install Gradle from https://gradle.org/"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def mvn_test(workspace: str, args: str = "") -> str:
    """Run mvn test in the workspace.

    Args:
        workspace: Path to Maven project directory
        args: Additional arguments to pass to 'mvn test' (e.g., '-Dtest=MyTest')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "pom.xml").exists():
        return f"ERROR: No pom.xml found in {workspace}"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_mvn_cmd(workspace, cmd_args)


def mvn_build(workspace: str, args: str = "") -> str:
    """Run mvn compile (or build) in the workspace.

    Args:
        workspace: Path to Maven project directory
        args: Additional arguments (e.g., '-DskipTests')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "pom.xml").exists():
        return f"ERROR: No pom.xml found in {workspace}"
    
    cmd_args = ["compile"]
    if args:
        cmd_args.extend(args.split())
    return _run_mvn_cmd(workspace, cmd_args)


def mvn_compile(workspace: str, args: str = "") -> str:
    """Run mvn compile in the workspace.

    Args:
        workspace: Path to Maven project directory
        args: Additional arguments (e.g., '-DskipTests')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "pom.xml").exists():
        return f"ERROR: No pom.xml found in {workspace}"
    
    cmd_args = ["compile"]
    if args:
        cmd_args.extend(args.split())
    return _run_mvn_cmd(workspace, cmd_args)


def mvn_package(workspace: str, args: str = "") -> str:
    """Run mvn package in the workspace.

    Args:
        workspace: Path to Maven project directory
        args: Additional arguments (e.g., '-DskipTests')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "pom.xml").exists():
        return f"ERROR: No pom.xml found in {workspace}"
    
    cmd_args = ["package"]
    if args:
        cmd_args.extend(args.split())
    return _run_mvn_cmd(workspace, cmd_args)


def mvn_clean(workspace: str) -> str:
    """Run mvn clean in the workspace.

    Args:
        workspace: Path to Maven project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "pom.xml").exists():
        return f"ERROR: No pom.xml found in {workspace}"
    
    return _run_mvn_cmd(workspace, ["clean"])


def gradle_test(workspace: str, args: str = "") -> str:
    """Run gradle test in the workspace.

    Args:
        workspace: Path to Gradle project directory
        args: Additional arguments (e.g., '--tests MyTest')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "build.gradle.kts").exists() and not (workspace_path / "build.gradle").exists():
        return f"ERROR: No build.gradle(.kts) found in {workspace}"
    
    cmd_args = ["test"]
    if args:
        cmd_args.extend(args.split())
    return _run_gradle_cmd(workspace, cmd_args)


def gradle_build(workspace: str, args: str = "") -> str:
    """Run gradle build in the workspace.

    Args:
        workspace: Path to Gradle project directory
        args: Additional arguments (e.g., '-x test')
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "build.gradle.kts").exists() and not (workspace_path / "build.gradle").exists():
        return f"ERROR: No build.gradle(.kts) found in {workspace}"
    
    cmd_args = ["build"]
    if args:
        cmd_args.extend(args.split())
    return _run_gradle_cmd(workspace, cmd_args)


def gradle_check(workspace: str, args: str = "") -> str:
    """Run gradle check (includes checkstyle, spotbugs if configured).

    Args:
        workspace: Path to Gradle project directory
        args: Additional arguments
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "build.gradle.kts").exists() and not (workspace_path / "build.gradle").exists():
        return f"ERROR: No build.gradle(.kts) found in {workspace}"
    
    cmd_args = ["check"]
    if args:
        cmd_args.extend(args.split())
    return _run_gradle_cmd(workspace, cmd_args)


def spotbugs_check(workspace: str) -> str:
    """Run SpotBugs static analysis.

    Args:
        workspace: Path to Gradle project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "build.gradle.kts").exists() and not (workspace_path / "build.gradle").exists():
        return f"ERROR: No build.gradle(.kts) found in {workspace}"
    
    return _run_gradle_cmd(workspace, ["spotbugsMain"])


def checkstyle_check(workspace: str) -> str:
    """Run Checkstyle for code style checking.

    Args:
        workspace: Path to Gradle project directory
    """
    workspace_path = Path(workspace)
    if not (workspace_path / "build.gradle.kts").exists() and not (workspace_path / "build.gradle").exists():
        return f"ERROR: No build.gradle(.kts) found in {workspace}"
    
    return _run_gradle_cmd(workspace, ["checkstyleMain"])


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "mvn_test",
        "Run mvn test in a Maven project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        mvn_test,
    )
    reg.register(
        "mvn_build",
        "Run mvn compile to compile a Maven project.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        mvn_build,
    )
    reg.register(
        "mvn_compile",
        "Run mvn compile to compile Java sources.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        mvn_compile,
    )
    reg.register(
        "mvn_package",
        "Run mvn package to create JAR/WAR.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        mvn_package,
    )
    reg.register(
        "mvn_clean",
        "Run mvn clean to clean target directory.",
        {"workspace": {"type": "string", "required": True}},
        mvn_clean,
    )
    reg.register(
        "gradle_test",
        "Run gradle test in a Gradle project workspace.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        gradle_test,
    )
    reg.register(
        "gradle_build",
        "Run gradle build to build a Gradle project.",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        gradle_build,
    )
    reg.register(
        "gradle_check",
        "Run gradle check (includes checkstyle, spotbugs if configured).",
        {"workspace": {"type": "string", "required": True}, "args": {"type": "string"}},
        gradle_check,
    )
    reg.register(
        "spotbugs_check",
        "Run SpotBugs static analysis via Gradle.",
        {"workspace": {"type": "string", "required": True}},
        spotbugs_check,
    )
    reg.register(
        "checkstyle_check",
        "Run Checkstyle for Java code style checking.",
        {"workspace": {"type": "string", "required": True}},
        checkstyle_check,
    )