"""CI/CD integration tool - generate GitHub Actions and GitLab CI configs."""

from __future__ import annotations


def generate_github_actions(
    language: str = "python",
    test_cmd: str = "pytest",
    lint_cmd: str = "ruff check .",
    build_cmd: str | None = None,
) -> str:
    """Generate GitHub Actions workflow YAML.

    Args:
        language: Programming language (python, javascript, typescript, go, rust)
        test_cmd: Command to run tests
        lint_cmd: Command to run linter
        build_cmd: Optional build command

    Returns:
        GitHub Actions workflow YAML as string
    """
    # Language-specific setup steps
    setup_steps = {
        "python": [
            "- uses: actions/setup-python@v5",
            "  with:",
            "    python-version: '3.12'",
            "    cache: 'pip'",
        ],
        "javascript": [
            "- uses: actions/setup-node@v4",
            "  with:",
            "    node-version: '20'",
            "    cache: 'npm'",
        ],
        "typescript": [
            "- uses: actions/setup-node@v4",
            "  with:",
            "    node-version: '20'",
            "    cache: 'npm'",
        ],
        "go": [
            "- uses: actions/setup-go@v5",
            "  with:",
            "    go-version: '1.22'",
            "    cache: true",
        ],
        "rust": [
            "- uses: dtolnay/rust-toolchain@stable",
            "  with:",
            "    components: clippy",
        ],
    }

    # Default steps for unknown languages
    steps = setup_steps.get(language, [])

    # Build workflow
    lines = [
        "name: CI",
        "",
        "on:",
        "  push:",
        "    branches: [main, master]",
        "  pull_request:",
        "    branches: [main, master]",
        "",
        "jobs:",
        "  ci:",
        "    runs-on: ubuntu-latest",
        "    steps:",
    ]

    # Add setup steps
    for step in steps:
        lines.append(f"      {step}")

    # Add dependency install
    if language in ("python",):
        lines.extend([
            "      - name: Install dependencies",
            "        run: |",
            "          python -m pip install --upgrade pip",
            "          pip install -e .[dev]",
        ])
    elif language in ("javascript", "typescript"):
        lines.extend([
            "      - name: Install dependencies",
            "        run: npm ci",
        ])
    elif language == "go":
        lines.extend([
            "      - name: Download dependencies",
            "        run: go mod download",
        ])
    elif language == "rust":
        lines.extend([
            "      - name: Cache cargo",
            "        uses: actions/cache@v4",
            "        with:",
            "          path: ~/.cargo",
            "          key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}",
        ])

    # Add lint step
    lines.extend([
        "      - name: Run linter",
        f"        run: {lint_cmd}",
    ])

    # Add test step
    lines.extend([
        "      - name: Run tests",
        f"        run: {test_cmd}",
    ])

    # Add build step if provided
    if build_cmd:
        lines.extend([
            "      - name: Build",
            f"        run: {build_cmd}",
        ])

    return "\n".join(lines)


def generate_gitlab_ci(
    language: str = "python",
    test_cmd: str = "pytest",
    lint_cmd: str = "ruff check .",
    build_cmd: str | None = None,
) -> str:
    """Generate GitLab CI configuration YAML.

    Args:
        language: Programming language
        test_cmd: Command to run tests
        lint_cmd: Command to run linter
        build_cmd: Optional build command

    Returns:
        GitLab CI config YAML as string
    """
    # Language-specific image
    images = {
        "python": "python:3.12",
        "javascript": "node:20",
        "typescript": "node:20",
        "go": "golang:1.22",
        "rust": "rust:1.78",
    }
    image = images.get(language, "python:3.12")

    # Cache paths
    cache_paths = {
        "python": [".cache/pip", "venv/"],
        "javascript": ["node_modules/"],
        "typescript": ["node_modules/"],
        "go": ["go/pkg/mod/"],
        "rust": ["target/", "~/.cargo/"],
    }

    lines = [
        f"image: {image}",
        "",
        "stages:",
        "  - lint",
        "  - test",
    ]

    if build_cmd:
        lines.append("  - build")
    lines.append("")

    # Cache config
    cache = cache_paths.get(language, [])
    if cache:
        lines.append("cache:")
        lines.append("  paths:")
        for path in cache:
            lines.append(f"    - {path}")
        lines.append("")

    # Lint job
    lines.extend([
        "lint:",
        "  stage: lint",
        "  script:",
        f"    - {lint_cmd}",
        "  allow_failure: false",
        "",
    ])

    # Test job
    lines.extend([
        "test:",
        "  stage: test",
        "  script:",
    ])

    if language == "python":
        lines.extend([
            "    - pip install --upgrade pip",
            "    - pip install -e .[dev]",
        ])
    elif language in ("javascript", "typescript"):
        lines.append("    - npm ci")
    elif language == "go":
        lines.append("    - go mod download")
    elif language == "rust":
        lines.append("    - cargo build")

    lines.append(f"    - {test_cmd}")
    lines.append("")

    # Build job
    if build_cmd:
        lines.extend([
            "build:",
            "  stage: build",
            "  script:",
            f"    - {build_cmd}",
            "  only:",
            "    - main",
            "    - master",
            "    - tags",
        ])

    return "\n".join(lines)


def register(reg, max_chars: int = 8000) -> None:
    def ci_cd_tool(
        language: str,
        test_cmd: str = "pytest",
        lint_cmd: str = "ruff check .",
        build_cmd: str = "",
        platform: str = "github",
    ) -> str:
        """Generate CI/CD pipeline configuration.

        Args:
            language: Language (python, javascript, typescript, go, rust)
            test_cmd: Test command
            lint_cmd: Lint command
            build_cmd: Build command (optional)
            platform: github or gitlab
        """
        if platform == "gitlab":
            return generate_gitlab_ci(language, test_cmd, lint_cmd, build_cmd or None)
        return generate_github_actions(language, test_cmd, lint_cmd, build_cmd or None)

    reg.register(
        "ci_cd",
        "Generate CI/CD pipeline config (GitHub Actions or GitLab CI) for a language.",
        {
            "language": {"type": "string", "required": True},
            "test_cmd": {"type": "string"},
            "lint_cmd": {"type": "string"},
            "build_cmd": {"type": "string"},
            "platform": {"type": "string"},
        },
        ci_cd_tool,
    )