# dhybrid-agent — Multi-Language Guide

## Overview

dhybrid-agent supports multiple programming languages through dedicated toolchains. Each language has native tools for testing, linting, formatting, building, and security analysis.

## Supported Languages

| Language | Tools | Package Manager | Build System |
|----------|-------|-----------------|--------------|
| **Go** | 7 | go mod | go build |
| **Rust** | 8 | cargo | cargo build |
| **TypeScript/Node** | 9 | npm/yarn/pnpm | tsc/vite/esbuild |
| **Java** | 10 | Maven/Gradle | mvn/gradle |
| **C#/.NET** | 9 | NuGet | dotnet CLI |

---

## Go

### Available Tools

```bash
go_test        # Run tests (go test ./...)
go_vet         # Static analysis (go vet ./...)
go_fmt         # Format code (go fmt ./...)
go_build       # Build project (go build ./...)
go_mod_tidy    # Clean dependencies (go mod tidy)
golangci_lint  # Comprehensive linting (golangci-lint run)
gosec          # Security analysis (gosec ./...)
```

### Typical Workflow

```bash
# 1. Initialize project
go mod init myproject

# 2. Write code
# Agent creates main.go, handlers, tests

# 3. Run tests
go_test

# 4. Lint and format
go_vet
go_fmt
golangci_lint

# 5. Security check
gosec

# 6. Build
go_build
```

### Configuration

```yaml
# config/default.yaml — Go
tool:
  allowlist: [..., go_test, go_vet, go_fmt, go_build, go_mod_tidy, golangci_lint, gosec]
```

### Common Patterns

**Project Structure:**

```
myproject/
├── go.mod
├── go.sum
├── main.go
├── internal/
│   ├── handlers/
│   ├── services/
│   └── repositories/
├── pkg/
│   └── utils/
└── tests/
    └── integration_test.go
```

**Test File Naming:** `*_test.go`

**Run Specific Test:**

```bash
go_test --args "-run TestUserLogin"
```

---

## Rust

### Available Tools

```bash
cargo_test       # Run tests (cargo test)
cargo_build      # Build project (cargo build)
cargo_check      # Quick type-check (cargo check)
cargo_fmt        # Format (cargo fmt)
cargo_clippy     # Linting (cargo clippy)
cargo_audit      # Security audit (cargo audit)
cargo_update     # Update dependencies (cargo update)
cargo_outdated   # Check outdated (cargo outdated)
```

### Typical Workflow

```bash
# 1. Initialize project
cargo new myproject --bin  # or --lib

# 2. Add dependencies
# Agent edits Cargo.toml

# 3. Quick check during development
cargo_check

# 4. Run tests
cargo_test

# 5. Lint and format
cargo_clippy
cargo_fmt

# 6. Security audit
cargo_audit

# 7. Build release
cargo_build --release
```

### Configuration

```yaml
tool:
  allowlist: [..., cargo_test, cargo_build, cargo_check, cargo_fmt, cargo_clippy, cargo_audit, cargo_update, cargo_outdated]
```

### Common Patterns

**Project Structure:**

```
myproject/
├── Cargo.toml
├── Cargo.lock
├── src/
│   ├── main.rs
│   ├── lib.rs
│   ├── handlers/
│   ├── models/
│   └── services/
├── tests/
│   └── integration_tests.rs
└── benches/
```

**Test Organization:**

- Unit tests: `#[cfg(test)] mod tests { ... }` di file yang sama
- Integration tests: `tests/*.rs`

**Run Specific Test:**

```bash
cargo_test -- test_user_login
```

---

## TypeScript / Node.js

### Available Tools

```bash
npm_test         # Run tests (npm test)
npm_build        # Build (npm run build)
npm_install      # Install deps (npm install)
npm_audit        # Security audit (npm audit)
tsc_check        # Type check (tsc --noEmit)
eslint_check     # Lint (eslint .)
jest_test        # Jest tests (jest)
vitest_test      # Vitest tests (vitest run)
prettier_fmt     # Format (prettier --write .)
```

### Typical Workflow

```bash
# 1. Initialize project
npm init -y
# Agent sets up package.json dengan scripts

# 2. Install dependencies
npm_install

# 3. Type check during development
tsc_check

# 4. Lint
eslint_check

# 5. Run tests
npm_test          # Uses package.json "test" script
jest_test         # Direct jest
vitest_test       # Direct vitest

# 6. Format
prettier_fmt

# 7. Build
npm_build

# 8. Security audit
npm_audit
```

### Configuration

```yaml
tool:
  allowlist: [..., npm_test, npm_build, npm_install, npm_audit, tsc_check, eslint_check, jest_test, vitest_test, prettier_fmt]
```

### Common Patterns

**Project Structure (TypeScript):**

```
myproject/
├── package.json
├── tsconfig.json
├── .eslintrc.js
├── .prettierrc
├── src/
│   ├── index.ts
│   ├── routes/
│   ├── services/
│   ├── middleware/
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
└── dist/           # Build output
```

**package.json Scripts:**

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "build": "tsc",
    "lint": "eslint src --ext .ts",
    "format": "prettier --write \"src/**/*.ts\"",
    "typecheck": "tsc --noEmit"
  }
}
```

---

## Java (Maven & Gradle)

### Available Tools

```bash
# Maven
mvn_test         # mvn test
mvn_build        # mvn compile
mvn_compile      # mvn compile
mvn_package      # mvn package
mvn_clean        # mvn clean

# Gradle
gradle_test      # gradle test
gradle_build     # gradle build
gradle_check     # gradle check (includes checkstyle, spotbugs)

# Static Analysis
spotbugs_check   # SpotBugs analysis
checkstyle_check # Checkstyle analysis
```

### Typical Workflow (Maven)

```bash
# 1. Create project
mvn archetype:generate -DgroupId=com.example -DartifactId=myproject

# 2. Add dependencies to pom.xml

# 3. Compile
mvn_compile

# 4. Run tests
mvn_test

# 5. Package
mvn_package

# 6. Static analysis
spotbugs_check
checkstyle_check
```

### Typical Workflow (Gradle)

```bash
# 1. Initialize
gradle init --type java-application

# 2. Configure build.gradle.kts

# 3. Quick check
gradle_build

# 4. Run tests
gradle_test

# 5. Full check (tests + linting)
gradle_check
```

### Configuration

```yaml
tool:
  allowlist: [..., mvn_test, mvn_build, mvn_compile, mvn_package, mvn_clean, gradle_test, gradle_build, gradle_check, spotbugs_check, checkstyle_check]
```

### Common Patterns

**Maven Structure:**

```
myproject/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/example/
│   │   └── resources/
│   └── test/
│       ├── java/com/example/
│       └── resources/
└── target/
```

**Gradle Structure:**

```
myproject/
├── build.gradle.kts
├── settings.gradle.kts
├── src/
│   ├── main/
│   │   ├── java/com/example/
│   │   └── resources/
│   └── test/
│       ├── java/com/example/
│       └── resources/
└── build/
```

---

## C# / .NET

### Available Tools

```bash
dotnet_test          # dotnet test
dotnet_build         # dotnet build
dotnet_restore       # dotnet restore
dotnet_clean         # dotnet clean
dotnet_fmt           # dotnet format
dotnet_format        # Alias for dotnet_fmt
dotnet_tool_install  # Install global tools (dotnet-ef, etc.)
dotnet_outdated      # Check outdated packages
dotnet_ef_migrations # EF Core migrations
```

### Typical Workflow

```bash
# 1. Create project
dotnet new webapi -n MyApi
cd MyApi

# 2. Add packages
dotnet add package Microsoft.EntityFrameworkCore.Sqlite

# 3. Restore
dotnet_restore

# 4. Build
dotnet_build

# 5. Run tests
dotnet_test

# 6. Format
dotnet_fmt

# 7. EF Core migrations
dotnet_tool_install --tool dotnet-ef
dotnet_ef_migrations "add InitialCreate"

# 8. Check outdated
dotnet_outdated
```

### Configuration

```yaml
tool:
  allowlist: [..., dotnet_test, dotnet_build, dotnet_restore, dotnet_clean, dotnet_fmt, dotnet_format, dotnet_tool_install, dotnet_outdated, dotnet_ef_migrations]
```

### Common Patterns

**Project Structure:**

```
MySolution/
├── MySolution.sln
├── src/
│   ├── MyApi/
│   │   ├── MyApi.csproj
│   │   ├── Program.cs
│   │   ├── Controllers/
│   │   ├── Services/
│   │   └── Models/
│   └── MyApi.Tests/
│       ├── MyApi.Tests.csproj
│       └── UnitTests/
└── tests/
```

---

## Cross-Language Workflows

### Monorepo with Multiple Languages

```bash
# Root workspace
my-monorepo/
├── go-service/
├── rust-service/
├── typescript-app/
├── java-service/
└── dotnet-service/

# Agent dapat bekerja lintas bahasa
dhybrid repl
> "add health check endpoint to all services"
# Agent detects each language and uses appropriate tools
```

### Language Detection

Agent mendeteksi bahasa secara otomatis berdasarkan:

1. Project files (`go.mod`, `Cargo.toml`, `package.json`, `pom.xml`, `*.csproj`)
2. File extensions di workspace
3. Existing tool configurations

### Shared Patterns Across Languages

| Task | Go | Rust | TypeScript | Java | C# |
|------|-----|------|------------|------|-----|
| Test | `go_test` | `cargo_test` | `npm_test` | `mvn_test` | `dotnet_test` |
| Build | `go_build` | `cargo_build` | `npm_build` | `mvn_build` | `dotnet_build` |
| Lint | `golangci_lint` | `cargo_clippy` | `eslint_check` | `checkstyle_check` | `dotnet_fmt` |
| Format | `go_fmt` | `cargo_fmt` | `prettier_fmt` | - | `dotnet_fmt` |
| Security | `gosec` | `cargo_audit` | `npm_audit` | `spotbugs_check` | `dotnet_outdated` |
| Dependencies | `go_mod_tidy` | `cargo_update` | `npm_install` | `mvn_clean` | `dotnet_restore` |

---

## CI/CD for Each Language

### GitHub Actions Examples

**Go:**

```yaml
- name: Test
  run: go test ./...
- name: Lint
  run: golangci-lint run
```

**Rust:**

```yaml
- name: Check
  run: cargo check
- name: Test
  run: cargo test
- name: Clippy
  run: cargo clippy -- -D warnings
```

**TypeScript:**

```yaml
- name: Install
  run: npm ci
- name: Type Check
  run: npx tsc --noEmit
- name: Lint
  run: npx eslint src
- name: Test
  run: npm test
```

**Java (Maven):**

```yaml
- name: Test
  run: mvn test
- name: SpotBugs
  run: mvn spotbugs:check
```

**C#:**

```yaml
- name: Restore
  run: dotnet restore
- name: Build
  run: dotnet build --no-restore
- name: Test
  run: dotnet test --no-build
```

---

## Troubleshooting by Language

### Go

| Issue | Solution |
|-------|----------|
| "go: command not found" | Install Go dari golang.org |
| "golangci-lint not found" | `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest` |
| Module not found | Run `go mod tidy` |

### Rust

| Issue | Solution |
|-------|----------|
| "cargo: command not found" | Install dari rustup.rs |
| "clippy not found" | `rustup component add clippy` |
| "cargo-audit not found" | `cargo install cargo-audit` |

### TypeScript

| Issue | Solution |
|-------|----------|
| "npm: command not found" | Install Node.js dari nodejs.org |
| "tsc: command not found" | `npm install -g typescript` |
| "eslint: command not found" | `npm install -g eslint` |

### Java

| Issue | Solution |
|-------|----------|
| "mvn: command not found" | Install Maven dari maven.apache.org |
| "gradle: command not found" | Install dari gradle.org |
| "spotbugs not found" | Add ke build.gradle.kts plugins |

### C#

| Issue | Solution |
|-------|----------|
| "dotnet: command not found" | Install .NET SDK dari dotnet.microsoft.com |
| "dotnet-ef not found" | `dotnet tool install --global dotnet-ef` |

---

## Best Practices

1. **Gunakan tool per bahasa** — Jangan pakai shell command kalau ada native tools
2. **Jalankan check berurutan** — Format → Lint → Type-check → Test → Build
3. **Pin versi tool** — Pakai lockfiles (`go.sum`, `Cargo.lock`, `package-lock.json`)
4. **Config di repo** — Simpan `golangci.yml`, `.eslintrc`, `checkstyle.xml` di version control
5. **Otomasi di CI** — Jalankan semua check di setiap PR

---

## Quick Reference Card

```bash
# Go
go_test && go_vet && go_fmt && golangci_lint && gosec && go_build

# Rust
cargo_check && cargo_test && cargo_clippy && cargo_fmt && cargo_audit && cargo_build

# TypeScript
tsc_check && eslint_check && npm_test && prettier_fmt && npm_build

# Java (Maven)
mvn_clean && mvn_test && spotbugs_check && checkstyle_check && mvn_package

# C#
dotnet_restore && dotnet_build && dotnet_test && dotnet_fmt && dotnet_outdated
```