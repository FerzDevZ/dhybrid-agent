#!/usr/bin/env bash
#
# dhybrid-agent — installer one-liner (auto-detect distro, sekali jalan full install)
#
#   curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
#
# Yang dilakukan otomatis (sekali jalan):
#   1. Deteksi distro & package manager (apt/dnf/yum/pacman/zypper/apk/brew)
#   2. Install prasyarat sistem bila belum ada: git, python3 >= 3.12, python3-venv/pip
#   3. Clone/update repo → buat venv → install dependensi (full, termasuk dev)
#   4. Symlink `dhybrid` ke PATH, set PATH permanen, shell completion, .env
#
# Variabel env opsional:
#   DHYBRID_REPO_URL    repo git (default: https://github.com/FerzDevZ/dhybrid-agent.git)
#   DHYBRID_BRANCH      branch (default: main)
#   DHYBRID_INSTALL_DIR direktori instalasi (default: ~/.dhybrid-agent)
#   DHYBRID_BIN_DIR     direktori symlink binary (default: ~/.local/bin)
#   DHYBRID_SKIP_ENV    1 = jangan buat .env dari .env.example
#   DHYBRID_SKIP_SYS    1 = lewati pemasangan paket sistem (pakai python yang ada)
#   DHYBRID_USE_UV      1 = gunakan uv untuk instalasi (lebih cepat)
#   DHYBRID_INSTALL_DEV 1 = install dev deps (default: 1)
#
# Aman dipakai via pipe (non-interaktif). Prompt sudo/selesai dibaca dari /dev/tty.

set -euo pipefail

# ---- fix: cwd broken (PWD dihapus/dipindah di shell lama) ----
if ! (cd "$(pwd -P 2>/dev/null)" 2>/dev/null); then
  printf 'ERROR: PWD broken (%s) — direktori sudah dihapus/dipindah.\nBuka terminal baru lalu jalankan ulang installer.\n' "${PWD:-unset}" >&2
  exit 1
fi
cd "$HOME" 2>/dev/null || { printf 'ERROR: tidak bisa cd ke $HOME.\n' >&2; exit 1; }

REPO_URL="${DHYBRID_REPO_URL:-https://github.com/FerizDevZ/dhybrid-agent.git}"
BRANCH="${DHYBRID_BRANCH:-main}"
INSTALL_DIR="${DHYBRID_INSTALL_DIR:-$HOME/.dhybrid-agent}"
BIN_DIR="${DHYBRID_BIN_DIR:-$HOME/.local/bin}"
USE_UV="${DHYBRID_USE_UV:-0}"
SKIP_SYS="${DHYBRID_SKIP_SYS:-0}"

# ---- warna (aman non-tty) ----
if [ -t 1 ]; then
  C_GREEN=$'\033[32m'; C_CYAN=$'\033[36m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_GREEN=""; C_CYAN=""; C_YELLOW=""; C_RED=""; C_BOLD=""; C_OFF=""
fi
say()  { printf '%s\n' "${C_GREEN}==>${C_OFF} $*"; }
info() { printf '%s\n' "${C_CYAN}    $*${C_OFF}"; }
warn() { printf '%s\n' "${C_YELLOW}    $*${C_OFF}"; }
die()  { printf '%s\n' "${C_RED}ERROR: $*${C_OFF}" >&2; exit 1; }

# ---- deteksi distro & package manager ----
detect_pm() {
  if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then echo "brew"; return; fi
  if command -v apt-get >/dev/null 2>&1; then     echo "apt";   return; fi
  if command -v dnf    >/dev/null 2>&1; then      echo "dnf";   return; fi
  if command -v yum    >/dev/null 2>&1; then      echo "yum";   return; fi
  if command -v pacman >/dev/null 2>&1; then      echo "pacman"; return; fi
  if command -v zypper >/dev/null 2>&1; then      echo "zypper"; return; fi
  if command -v apk    >/dev/null 2>&1; then      echo "apk";   return; fi
  echo "unknown"
}

PM="$(detect_pm)"
OS_ID="$(sed -n 's/^ID=//p' /etc/os-release 2>/dev/null | tr -d '"' | head -1 || true)"
DISTRO_LABEL="${OS_ID:-$(uname -s)}"

# ---- sudo (interaktif via /dev/tty, diam-diam via sudo -n) ----
run_root() {
  if [ "$(id -u)" -eq 0 ]; then "$@"; return; fi
  if [ "${DID_ROOT:-0}" = "1" ]; then die "sudo gagal — paket sistem belum terpasang. Jalankan manual: $*"; fi
  local args=("$@")
  if sudo -n "${args[@]}" 2>/dev/null; then return; fi
  if [ -e /dev/tty ]; then
    say "Butuh sudo untuk memasang paket sistem ($*)."
    sudo "${args[@]}"
    DID_ROOT=1
  else
    die "butuh sudo untuk: $* — jalankan installer dari terminal interaktif."
  fi
}

# ---- pilih interpreter python >= 3.12 ----
pick_python() {
  local c
  for c in python3.12 python3.13 python3 python3.11; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

install_system_pkgs() {
  # dibutuhkan: git + python3 >= 3.12 + python venv/pip. Otomatis per distro.
  local need_git=0 pyok=0
  command -v git >/dev/null 2>&1 || need_git=1
  [ -n "$(pick_python || true)" ] && pyok=1

  if [ "$need_git" = "0" ] && [ "$pyok" = "1" ]; then
    return 0  # semua ada
  fi

  if [ "$SKIP_SYS" = "1" ]; then
    command -v git >/dev/null 2>&1 || die "butuh 'git' (tapi DHYBRID_SKIP_SYS=1 — pasang manual)."
    [ -n "$(pick_python || true)" ] || die "butuh Python >= 3.12 (tapi DHYBRID_SKIP_SYS=1 — pasang manual)."
    return 0
  fi

  say "Mendeteksi distro: ${DISTRO_LABEL} — menyiapkan paket sistem (git, python3.12, venv...)"
  case "$PM" in
    apt)
      run_root apt-get update -qq
      run_root apt-get install -y -qq git python3 python3-pip python3-venv
      ;;
    dnf|yum)
      run_root "$PM" install -y git python3 python3-pip python3-devel
      ;;
    pacman)
      run_root pacman -Sy --noconfirm git python python-pip python-virtualenv
      ;;
    zypper)
      run_root zypper --non-interactive install git python3 python3-pip python3-virtualenv
      ;;
    apk)
      run_root apk add --no-cache git python3 python3-pip py3-virtualenv
      ;;
    brew)
      command -v brew >/dev/null 2>&1 || die "macOS: butuh Homebrew (https://brew.sh)."
      brew install git python@3.12 || brew install git python3
      ;;
    *)
      die "Distro '$PM' belum dikenali. Pasang manual: git, python3>=3.12, python3-venv lalu jalankan ulang dengan DHYBRID_SKIP_SYS=1."
      ;;
  esac
}

# ---- main ----
say "Memasang dhybrid-agent (hemat token, hybrid routing)"
info "distro    : $DISTRO_LABEL (pkg: $PM)"
info "repo      : $REPO_URL"
info "branch    : $BRANCH"
info "instal di : $INSTALL_DIR"

[ "$SKIP_SYS" = "1" ] && info "skip      : paket sistem (pakai yang sudah ada)"

install_system_pkgs

PY="$(pick_python)" || die "Python >= 3.12 tidak tersedia setelah instalasi paket. Coba jalankan ulang / cek package manager."

# ---- optional: uv ----
if [ "$USE_UV" = "1" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    warn "uv tidak ditemukan — pasang manual: curl -LsSf https://astral.sh/uv/install.sh | sh"
    info "Lanjut dengan pip standar..."
    USE_UV=0
  fi
fi

INSTALL_DEV="${DHYBRID_INSTALL_DEV:-1}"
info "mode      : full install (dev deps)"     ; [ "$INSTALL_DEV" = "1" ] || info "mode      : minimal (tanpa dev deps)"
[ "$USE_UV" = "1" ] && info "mode      : uv (cepat)"

# ---- clone / update ----
if [ -d "$INSTALL_DIR/.git" ]; then
  say "Repo sudah ada — memperbarui..."
  git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH" || true
  git -C "$INSTALL_DIR" reset --hard --quiet "origin/$BRANCH" 2>/dev/null \
    || git -C "$INSTALL_DIR" pull --quiet --ff-only || true
else
  say "Meng-clone repo..."
  mkdir -p "$INSTALL_DIR"
  git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" \
    || die "gagal clone $REPO_URL (cek koneksi / nama repo)"
fi

# ---- venv + dependensi ----
say "Menyiapkan venv & dependensi (sekali saja, ~30 detik)..."
if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
  "$PY" -m venv "$INSTALL_DIR/.venv" 2>/dev/null \
    || { "$PY" -m pip install --quiet --user virtualenv >/dev/null 2>&1 \
         && "$PY" -m virtualenv "$INSTALL_DIR/.venv" >/dev/null 2>&1; } \
    || die "gagal membuat venv — pasang python3-venv secara manual untuk distro Anda, lalu jalankan ulang installer."
else
  info "venv sudah ada — dipakai ulang."
fi

if [ "$USE_UV" = "1" ]; then
  say "Menggunakan uv untuk install dependensi (lebih cepat)..."
  "$INSTALL_DIR/.venv/bin/uv" pip install --quiet --upgrade pip
  if [ "$INSTALL_DEV" = "1" ]; then
    "$INSTALL_DIR/.venv/bin/uv" pip install --quiet -e "$INSTALL_DIR[dev]"
  else
    "$INSTALL_DIR/.venv/bin/uv" pip install --quiet -e "$INSTALL_DIR"
  fi
else
  "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
  if [ "$INSTALL_DEV" = "1" ]; then
    "$INSTALL_DIR/.venv/bin/pip" install --quiet -e "$INSTALL_DIR[dev]"
  else
    "$INSTALL_DIR/.venv/bin/pip" install --quiet -e "$INSTALL_DIR"
  fi
fi

# ---- binary di PATH ----
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/.venv/bin/dhybrid" "$BIN_DIR/dhybrid"
chmod +x "$INSTALL_DIR/.venv/bin/dhybrid"

# ---- .env (API key) ----
if [ "${DHYBRID_SKIP_ENV:-0}" != "1" ] && [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  info ".env dibuat — isi API key-mu: $INSTALL_DIR/.env"
fi

# ---- auto-check tools untuk sugges stack default ----
say "Mengecek tools development..."
AVAILABLE_TOOLS=""
for cmd in php composer node npm python3 pip3 uv go cargo dotnet java mvn gradle docker; do
    command -v "$cmd" >/dev/null 2>&1 && AVAILABLE_TOOLS="$AVAILABLE_TOOLS $cmd"
done
if [ -n "$AVAILABLE_TOOLS" ]; then
    info "Tools tersedia:$AVAILABLE_TOOLS"
else
    warn "Tidak ada development tools terdeteksi"
    info "Anda tetap bisa pakai dhybrid — tapi untuk coding butuh tools."
fi

# ---- PATH permanen (~/.bashrc / ~/.zshrc) ----
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$rc" ] && [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    if ! grep -q "dhybrid-agent PATH" "$rc" 2>/dev/null; then
      printf '\n# dhybrid-agent PATH\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$rc"
      info "PATH ditambahkan ke $rc"
    fi
  fi
done

# ---- shell completion ----
if [ -f "$HOME/.bashrc" ] && ! grep -q "dhybrid-completion" "$HOME/.bashrc" 2>/dev/null; then
  printf '\n# dhybrid-completion\nsource %s/scripts/completions.bash\n' "$INSTALL_DIR" >> "$HOME/.bashrc"
  info "completion bash ditambahkan ke ~/.bashrc"
fi
if [ -f "$HOME/.zshrc" ] && ! grep -q "dhybrid-completion" "$HOME/.zshrc" 2>/dev/null; then
  printf '\n# dhybrid-completion\nautoload -Uz compinit && compinit\nsource %s/scripts/completions.zsh\n' "$INSTALL_DIR" >> "$HOME/.zshrc"
  info "completion zsh ditambahkan ke ~/.zshrc"
fi

# ---- interaktif: tawarkan menjalankan dhybrid sekarang ----
if [ -e /dev/tty ]; then
  printf '\n%s=== Instalasi selesai! ===%s\n' "$C_BOLD" "$C_OFF" >/dev/tty
  printf 'Mau coba dhybrid sekarang? (Y/n) ' >/dev/tty
  read -r REPLY </dev/tty || REPLY=""
  if [[ -z "$REPLY" || "$REPLY" =~ ^[Yy]$ ]]; then
    say "Menjalankan dhybrid repl..."
    exec "$BIN_DIR/dhybrid" repl
  else
    say "${C_BOLD}Selesai!${C_OFF}"
    info "jalankan nanti: $BIN_DIR/dhybrid repl"
    info "atau buka terminal baru, lalu: dhybrid repl"
  fi
else
  say "${C_BOLD}Selesai!${C_OFF}"
  info "jalankan sekarang : $BIN_DIR/dhybrid repl"
  info "atau buka terminal baru, lalu: dhybrid repl"
fi

if [ -f "$INSTALL_DIR/.env" ] && ! grep -q "=" "$INSTALL_DIR/.env"; then
  warn "JANGAN LUPA: isi API key di $INSTALL_DIR/.env"
fi

# ---- tampilkan versi (non-interaktif) ----
if [ ! -t 0 ] || [ ! -t 1 ]; then
  "$BIN_DIR/dhybrid" --version 2>/dev/null || true
fi