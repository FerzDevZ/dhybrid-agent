"""Tests for CI/CD integration tool."""
from dhybrid.tools.ci_cd import generate_github_actions, generate_gitlab_ci


def test_ci_cd_creates_github_actions_workflow():
    """Test generating GitHub Actions workflow."""
    workflow = generate_github_actions(
        language="python",
        test_cmd="pytest",
        lint_cmd="ruff check .",
    )
    assert "on:" in workflow
    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "pytest" in workflow
    assert "ruff check" in workflow
    assert "runs-on: ubuntu-latest" in workflow


def test_ci_cd_creates_gitlab_ci_config():
    """Test generating GitLab CI config."""
    config = generate_gitlab_ci(
        language="python",
        test_cmd="pytest",
        lint_cmd="ruff check .",
    )
    assert "stages:" in config
    assert "test" in config
    assert "lint" in config
    assert "pytest" in config
    assert "ruff check" in config


def test_ci_cd_javascript_workflow():
    """Test generating workflow for JavaScript/TypeScript."""
    workflow = generate_github_actions(
        language="javascript",
        test_cmd="npm test",
        lint_cmd="eslint .",
    )
    assert "npm test" in workflow
    assert "eslint" in workflow
    assert "actions/setup-node" in workflow


def test_ci_cd_go_workflow():
    """Test generating workflow for Go."""
    workflow = generate_github_actions(
        language="go",
        test_cmd="go test ./...",
        lint_cmd="golangci-lint run",
    )
    assert "go test" in workflow
    assert "golangci-lint" in workflow
    assert "actions/setup-go" in workflow


def test_ci_cd_rust_workflow():
    """Test generating workflow for Rust."""
    workflow = generate_github_actions(
        language="rust",
        test_cmd="cargo test",
        lint_cmd="cargo clippy",
    )
    assert "cargo test" in workflow
    assert "cargo clippy" in workflow
    assert "dtolnay/rust-toolchain" in workflow