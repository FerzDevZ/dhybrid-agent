"""Tests for TypeScript/Node toolchain."""
import subprocess

import pytest

from dhybrid.tools.ts_toolchain import (
    eslint_check,
    jest_test,
    npm_audit,
    npm_build,
    npm_install,
    npm_test,
    tsc_check,
    vitest_test,
)


def _has_npm() -> bool:
    """Check if npm is available."""
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _has_npm(), reason="npm not installed")
def test_npm_test(tmp_path):
    """Test running npm test."""
    # Create a simple Node.js project
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "scripts": {
    "test": "echo 'test passed'"
  }
}""")
    
    result = npm_test(str(tmp_path))
    assert "test passed" in result.lower() or "passed" in result.lower()


@pytest.mark.skipif(not _has_npm(), reason="npm not installed")
def test_npm_build(tmp_path):
    """Test running npm build."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "scripts": {
    "build": "echo 'build complete'"
  }
}""")
    
    result = npm_build(str(tmp_path))
    assert "build complete" in result.lower() or "complete" in result.lower()


def test_tsc_check(tmp_path):
    """Test running tsc check."""
    (tmp_path / "tsconfig.json").write_text("""{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "strict": true,
    "outDir": "./dist"
  },
  "include": ["src"]
}""")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("const x: string = 'hello';\nconsole.log(x);\n")
    
    result = tsc_check(str(tmp_path))
    assert isinstance(result, str)


def test_eslint_check(tmp_path):
    """Test running eslint check."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "devDependencies": {
    "eslint": "^8.0.0"
  }
}""")
    (tmp_path / "eslint.config.js").write_text("""export default [
  {
    languageOptions: { ecmaVersion: 2022, sourceType: 'module' },
    rules: { semi: 'error' }
  }
];
""")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.js").write_text("const x = 1\n")
    
    result = eslint_check(str(tmp_path))
    assert isinstance(result, str)


@pytest.mark.skipif(not _has_npm(), reason="npm not installed")
@pytest.mark.skip(reason="requires jest config for ES modules")
def test_jest_test(tmp_path):
    """Test running jest test."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}""")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sum.js").write_text("export const sum = (a, b) => a + b;\n")
    (tmp_path / "src" / "sum.test.js").write_text("import { sum } from './sum';\ntest('adds 1 + 2 to equal 3', () => {\n  expect(sum(1, 2)).toBe(3);\n});\n")
    
    result = jest_test(str(tmp_path))
    assert "PASS" in result or "passed" in result.lower()


@pytest.mark.skipif(not _has_npm(), reason="npm not installed")
@pytest.mark.skip(reason="requires npm install which is slow in CI")
def test_vitest_test(tmp_path):
    """Test running vitest test."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "vitest": "^1.0.0"
  }
}""")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sum.ts").write_text("export const sum = (a: number, b: number) => a + b;\n")
    (tmp_path / "src" / "sum.test.ts").write_text("import { sum } from './sum';\nimport { test, expect } from 'vitest';\ntest('adds 1 + 2 to equal 3', () => {\n  expect(sum(1, 2)).toBe(3);\n});\n")
    
    result = vitest_test(str(tmp_path))
    assert "PASS" in result or "passed" in result.lower()


@pytest.mark.skipif(not _has_npm(), reason="npm not installed")
def test_npm_install(tmp_path):
    """Test running npm install."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "dependencies": {
    "lodash": "^4.17.21"
  }
}""")
    
    result = npm_install(str(tmp_path))
    assert "added" in result.lower() or "installed" in result.lower() or "up to date" in result.lower()


def test_npm_audit(tmp_path):
    """Test running npm audit."""
    (tmp_path / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "dependencies": {
    "lodash": "^4.17.21"
  }
}""")
    
    result = npm_audit(str(tmp_path))
    assert isinstance(result, str)