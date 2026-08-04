#!/usr/bin/env bash
#
# dhybrid-agent — installer one-liner
#
#   curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
#
# Variabel env opsional:
#   DHYBRID_REPO_URL    repo git (default: https://github.com/FerzDevZ/dhybrid-agent.git)
#   DHYBRID_BRANCH      branch (default: main)
#   DHYBRID_INSTALL_DIR direktori instalasi (default: ~/.dhybrid-agent)
#   DHYBRID_BIN_DIR     direktori symlink binary (default: ~/.local/bin)
#   DHYBRID_SKIP_ENV    1 = jangan buat .env dari .env.example
#
# Aman dipakai via pipe (non-interaktif, tidak ada prompt).

set -euo pipefail

# ---- fix: cwd broken (stale PWD di shell lama / direktori dihapus/dipindah)
# bikin semua operasi error "No such file or directory" — termasuk pip install
# di dalam venv yang diciptakan di cwd broken. Deteksi via subshell sebelum cd:
#   - `pwd -P` tak bisa resolve → broken
#   - `[ -d . ]` gagal di cwd yang hilang
# Paksa ke $HOME & pastikan resolve OK, semua operasi pakai path absolut. ----
if ! (cd "$(pwd -P 2>/dev/null)" 2>/dev/null); then
  printf 'ERROR: PWD broken (%s di shell ini) — direktori sudah dihapus/dipindah\natau shell lama (tmux/screen). Buka terminal baru, lalu jalankan ulang installer.\n' "${PWD:-unset}" >&2
  exit 1
fi
cd "$HOME" 2>/dev/null || { printf 'ERROR: tidak bisa cd ke $HOME — periksa mount/home.\n' >&2; exit 1; }

REPO_URL="${DHYBRID_REPO_URL:-https://github.com/FerzDevZ/dhybrid-agent.git}"
BRANCH="${DHYBRID_BRANCH:-main}"
INSTALL_DIR="${DHYBRID_INSTALL_DIR:-$HOME/.dhybrid-agent}"
BIN_DIR="${DHYBRID_BIN_DIR:-$HOME/.local/bin}"

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

# ---- prasyarat ----
command -v git >/dev/null 2>&1 || die "butuh 'git' (sudo apt install git)"
command -v python3 >/dev/null 2>&1 || die "butuh 'python3'"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || die "butuh Python >= 3.12 (punya: $(python3 --version 2>&1))"

say "Memasang dhybrid-agent (hemat token, hybrid routing)"
info "repo     : $REPO_URL"
info "instal di: $INSTALL_DIR"

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
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -e "$INSTALL_DIR"

# ---- binary di PATH ----
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/.venv/bin/dhybrid" "$BIN_DIR/dhybrid"
chmod +x "$INSTALL_DIR/.venv/bin/dhybrid"

# ---- .env (API key) ----
if [ "${DHYBRID_SKIP_ENV:-0}" != "1" ] && [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  info ".env dibuat — isi API key-mu: $INSTALL_DIR/.env"
fi

# ---- auto-check tools untuk suggerensi stack default ----
say "Mengecek tools development..."
AVAILABLE_TOOLS=""
for cmd in php composer node npm python3 pip3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        AVAILABLE_TOOLS="$AVAILABLE_TOOLS $cmd"
    fi
done
if [ -n "$AVAILABLE_TOOLS" ]; then
    info "Tools tersedia:$AVAILABLE_TOOLS"
else
    warn "Tidak ada development tools terdeteksi (php, node, python, dll.)"
    info "Anda tetap bisa pakai dhybrid — tapi untuk coding butuh tools."
fi

# ---- PATH permanen (~/.bashrc) ----
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  if ! grep -q "dhybrid-agent PATH" "$HOME/.bashrc" 2>/dev/null; then
    printf '\n# dhybrid-agent PATH\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$HOME/.bashrc"
    info "PATH ditambahkan ke ~/.bashrc"
  fi
fi

# ---- shell completion ----
case "${SHELL##*/}" in
  bash)
    if ! grep -q "dhybrid-completion" "$HOME/.bashrc" 2>/dev/null; then
      printf '\n# dhybrid-completion\nsource %s/scripts/completions.bash\n' "$INSTALL_DIR" >> "$HOME/.bashrc"
      info "completion bash ditambahkan ke ~/.bashrc"
    fi ;;
  zsh)
    if ! grep -q "dhybrid-completion" "$HOME/.zshrc" 2>/dev/null; then
      printf '\n# dhybrid-completion\nautoload -Uz compinit && compinit\nsource %s/scripts/completions.zsh\n' "$INSTALL_DIR" >> "$HOME/.zshrc"
      info "completion zsh ditambahkan ke ~/.zshrc"
    fi ;;
esac

# ---- selesai ----
say "${C_BOLD}Selesai!${C_OFF}"
info "jalankan sekarang : $BIN_DIR/dhybrid repl"
info "atau buka terminal baru, lalu: dhybrid repl"
if [ -f "$INSTALL_DIR/.env" ] && ! grep -q "=" "$INSTALL_DIR/.env"; then
  warn "JANGAN LUPA: isi API key di $INSTALL_DIR/.env"
fi
