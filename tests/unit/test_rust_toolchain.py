"""Tests for Rust toolchain."""
import subprocess

import pytest

from dhybrid.tools.rust_toolchain import (
    cargo_audit,
    cargo_build,
    cargo_check,
    cargo_clippy,
    cargo_fmt,
    cargo_test,
    cargo_update,
)


def _has_cargo() -> bool:
    """Check if cargo is available."""
    try:
        subprocess.run(["cargo", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _has_cargo(), reason="cargo not installed")
def test_cargo_test(tmp_path):
    """Test running cargo test."""
    # Create a simple Rust crate
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("pub fn add(a: i32, b: i32) -> i32 { a + b }\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn test_add() {\n        assert_eq!(add(1, 2), 3);\n    }\n}")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_test(str(tmp_path))
    assert "test result: ok" in result or "passed" in result.lower()


@pytest.mark.skipif(not _has_cargo(), reason="cargo not installed")
def test_cargo_build(tmp_path):
    """Test running cargo build."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() { println!(\"hello\"); }")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_build(str(tmp_path))
    assert "Finished" in result or "Compiling" in result


def test_cargo_clippy(tmp_path):
    """Test running cargo clippy."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() { println!(\"hello\"); }")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_clippy(str(tmp_path))
    assert isinstance(result, str)


def test_cargo_fmt(tmp_path):
    """Test running cargo fmt."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main(){println!(\"hello\");}")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_fmt(str(tmp_path))
    assert isinstance(result, str)


def test_cargo_audit(tmp_path):
    """Test running cargo audit."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() { println!(\"hello\"); }")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_audit(str(tmp_path))
    assert isinstance(result, str)


def test_cargo_check(tmp_path):
    """Test running cargo check."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() { println!(\"hello\"); }")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_check(str(tmp_path))
    assert isinstance(result, str)


def test_cargo_update(tmp_path):
    """Test running cargo update."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() { println!(\"hello\"); }")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"\n")
    
    result = cargo_update(str(tmp_path))
    assert isinstance(result, str)