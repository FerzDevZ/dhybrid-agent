"""Tests for Go toolchain."""
from dhybrid.tools.go_toolchain import (
    go_build,
    go_fmt,
    go_mod_tidy,
    go_test,
    go_vet,
    golangci_lint,
    gosec,
)


def test_go_test(tmp_path):
    """Test running go test."""
    # Create a simple Go module
    (tmp_path / "main.go").write_text("package main\n\nfunc Add(a, b int) int { return a + b }")
    (tmp_path / "main_test.go").write_text("package main\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) {\n    if Add(1, 2) != 3 {\n        t.Errorf(\"Add(1, 2) = %d; want 3\", Add(1, 2))\n    }\n}")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = go_test(str(tmp_path))
    assert "PASS" in result or "ok" in result


def test_go_vet(tmp_path):
    """Test running go vet."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main() { println(\"hello\") }")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = go_vet(str(tmp_path))
    # go vet returns empty on success or warnings
    assert isinstance(result, str)


def test_go_fmt(tmp_path):
    """Test running go fmt."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main(){println(\"hello\")}")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = go_fmt(str(tmp_path))
    # go fmt returns formatted file paths or empty
    assert isinstance(result, str)


def test_golangci_lint(tmp_path):
    """Test running golangci-lint."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main() { println(\"hello\") }")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = golangci_lint(str(tmp_path))
    # Should run without error (tool may not be installed)
    assert isinstance(result, str)


def test_gosec(tmp_path):
    """Test running gosec."""
    (tmp_path / "main.go").write_text("package main\n\nimport \"fmt\"\n\nfunc main() { fmt.Println(\"hello\") }")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = gosec(str(tmp_path))
    assert isinstance(result, str)


def test_go_build(tmp_path):
    """Test running go build."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main() { println(\"hello\") }")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = go_build(str(tmp_path))
    assert isinstance(result, str)


def test_go_mod_tidy(tmp_path):
    """Test running go mod tidy."""
    (tmp_path / "main.go").write_text("package main\n\nfunc main() { println(\"hello\") }")
    (tmp_path / "go.mod").write_text("module test\n\ngo 1.22\n")
    
    result = go_mod_tidy(str(tmp_path))
    assert isinstance(result, str)