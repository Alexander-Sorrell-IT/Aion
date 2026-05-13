#!/usr/bin/env bash
# install-aion.sh — one-line installer for aion.
#
# Does:
#   1. Checks Python >= 3.10 and pipx are available (with helpful errors)
#   2. Installs the aion-cli package globally via pipx (preferred) or pip
#   3. Runs install-defaults.sh to seed the user config dir with the
#      bundled marketplace + memory-git + plugin enable state
#   4. Verifies the binary is on PATH; prints next-step hints
#
# Usage:
#   ./install-aion.sh                  # install from this checkout
#   ./install-aion.sh --from-pypi      # install from PyPI (after publish)

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FROM_PYPI=0
for arg in "$@"; do
  case "$arg" in
    --from-pypi) FROM_PYPI=1 ;;
    --help|-h)
      sed -n '2,15p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  aion installer"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# ── 1. Prerequisites ─────────────────────────────────────────────────────────

echo "=== 1/4  Prerequisites ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✘ python3 not found. Install Python 3.10+ first."
  echo "    macOS: brew install python@3.12"
  echo "    Ubuntu: sudo apt install python3"
  exit 1
fi

PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYMAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
PYMINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 10 ]; }; then
  echo "  ✘ Python $PYVER is too old. aion needs Python 3.10+."
  exit 1
fi
echo "  ✓ python3 $PYVER"

INSTALL_VIA=""
if command -v pipx >/dev/null 2>&1; then
  echo "  ✓ pipx $(pipx --version)"
  INSTALL_VIA="pipx"
else
  echo "  ⚠ pipx not found — will fall back to pip --user (less isolated)."
  echo "    Recommended: install pipx with 'python3 -m pip install --user pipx'"
  INSTALL_VIA="pip"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "  ⚠ git not found — memory-git audit trail will be disabled."
  echo "    Install git to enable per-action commit history."
fi

# ── 2. Install the package ───────────────────────────────────────────────────

echo ""
echo "=== 2/4  Installing aion-cli ==="

if [ "$FROM_PYPI" = "1" ]; then
  SOURCE="aion-cli"
else
  SOURCE="$HERE"
  if [ ! -f "$HERE/pyproject.toml" ]; then
    echo "  ✘ pyproject.toml not found at $HERE — can't install from local checkout."
    echo "    Use --from-pypi to install the published package instead."
    exit 1
  fi
fi

if [ "$INSTALL_VIA" = "pipx" ]; then
  # pipx install --force lets us upgrade in place. For local checkouts we
  # add --editable so users can iterate without reinstalling.
  if [ "$FROM_PYPI" = "1" ]; then
    pipx install --force "$SOURCE" 2>&1 | tail -3
  else
    pipx install --force --editable "$SOURCE" 2>&1 | tail -3
  fi
else
  # pip fallback. Detect virtualenv — `pip install --user` fails inside one,
  # so we omit `--user` when in a venv. Outside a venv, `--user` puts the
  # binary in ~/.local/bin (usually on PATH).
  IN_VENV="$(python3 -c 'import sys; print("yes" if sys.prefix != sys.base_prefix else "no")')"
  if [ "$IN_VENV" = "yes" ]; then
    USER_FLAG=""
    echo "  Detected active virtualenv — installing into it (not --user)."
  else
    USER_FLAG="--user"
  fi
  if [ "$FROM_PYPI" = "1" ]; then
    python3 -m pip install $USER_FLAG --upgrade "$SOURCE" 2>&1 | tail -3
  else
    python3 -m pip install $USER_FLAG --upgrade -e "$SOURCE" 2>&1 | tail -3
  fi
fi

# Resolve the binary's brand-configured name. Falls back to "aion" if the
# brand.config.json is unreadable.
BRAND_BINARY="aion"
if [ -f "$HERE/brand.config.json" ]; then
  BRAND_BINARY="$(python3 -c "
import json
try:
    print(json.load(open('$HERE/brand.config.json')).get('binary', 'aion'))
except Exception:
    print('aion')
")"
fi

echo "  ✓ installed (binary name: $BRAND_BINARY)"

# ── 3. Seed user config dir with defaults ────────────────────────────────────

echo ""
echo "=== 3/4  Seeding bundled defaults ==="

if [ "$FROM_PYPI" = "1" ]; then
  echo "  Skipping defaults seed — when installing from PyPI, defaults are"
  echo "  bundled in the package. Run '$BRAND_BINARY --setup' to seed them."
elif [ -x "$HERE/scripts/install-defaults.sh" ]; then
  # Read configDir from brand.config.json
  CONFIG_DIR="$(python3 -c "
import json, os
d = json.load(open('$HERE/brand.config.json'))
print(os.path.expanduser(d.get('configDir', '~/.aion')))
")"
  "$HERE/scripts/install-defaults.sh" "$HERE" "$CONFIG_DIR" 2>&1 | sed 's/^/  /'
else
  echo "  ⚠ scripts/install-defaults.sh not found, skipping defaults seed"
fi

# ── 4. PATH check + next steps ───────────────────────────────────────────────

echo ""
echo "=== 4/4  Verification ==="

if command -v "$BRAND_BINARY" >/dev/null 2>&1; then
  WHICH="$(command -v "$BRAND_BINARY")"
  echo "  ✓ '$BRAND_BINARY' on PATH at $WHICH"
  VERSION_OUTPUT="$("$BRAND_BINARY" --version 2>&1 || true)"
  echo "  ✓ '$BRAND_BINARY --version': $VERSION_OUTPUT"
else
  echo "  ⚠ '$BRAND_BINARY' is NOT on PATH yet."
  if [ "$INSTALL_VIA" = "pipx" ]; then
    echo "    Run 'pipx ensurepath' and restart your shell, then try again."
  else
    echo "    Add ~/.local/bin to PATH:"
    echo "      echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "      source ~/.bashrc"
  fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Done."
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Try it:"
echo "  $BRAND_BINARY --version"
echo "  $BRAND_BINARY plugin list"
echo "  $BRAND_BINARY                  # interactive REPL"
echo "  $BRAND_BINARY run \"hello\"      # one-shot"
echo ""
echo "Set your API key in your shell env (one of):"
echo "  export OPENAI_API_KEY=..."
echo "  export ANTHROPIC_API_KEY=..."
echo "  export DEEPSEEK_API_KEY=..."
echo ""
