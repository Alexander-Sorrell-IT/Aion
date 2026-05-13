#!/usr/bin/env bash
# install-defaults.sh — bootstrap aion's bundled defaults into the user's
# config dir. Equivalent of Proteus's install-defaults.sh.
#
# Reads brand.config.json's `defaults` and `memoryGit` blocks and:
#   1. Copies defaults/marketplace into <config>/plugins/marketplaces/<brand>/
#   2. Registers it in <config>/plugins/known_marketplaces.json
#   3. Marks each plugin in defaults.plugins.install as installed + enabled
#   4. Copies scripts/memory-autocommit.sh to <config>/scripts/ for hook use
#   5. Initializes <config>/memory/.git if memoryGit.enabled is true
#   6. Seeds <config>/settings.json (only if no existing file) with the
#      brand-templated hook commands
#
# Usage:
#   install-defaults.sh <install-dir> <config-dir>
#
# Both args required. install-dir is where aion is installed (contains
# brand.config.json + defaults/); config-dir is where ~/.aion (or whatever
# the brand configures) lives.

set -uo pipefail

INSTALL_DIR="${1:-}"
CONFIG_DIR="${2:-}"

if [ -z "$INSTALL_DIR" ] || [ -z "$CONFIG_DIR" ]; then
  echo "Usage: install-defaults.sh <install-dir> <config-dir>"
  exit 1
fi

if [ ! -f "$INSTALL_DIR/brand.config.json" ]; then
  echo "  [install-defaults] $INSTALL_DIR/brand.config.json not found, skipping"
  exit 0
fi

mkdir -p "$CONFIG_DIR"

# Use python to read the brand config consistently (no jq dependency).
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "  [install-defaults] python not found, can't read brand.config.json"
  exit 1
fi

# Read brand fields we need
BRAND_BINARY="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
print(d.get('binary', 'aion'))
")"

BRAND_DISPLAY="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
print(d.get('display', 'aion'))
")"

AUTOCOMMIT_FLAG="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
mg = d.get('memoryGit', {})
print('true' if mg.get('autoCommit', True) else 'false')
")"

AUTOPUSH_FLAG="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
mg = d.get('memoryGit', {})
print('true' if mg.get('autoPush', False) else 'false')
")"

MEMGIT_ENABLED="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
mg = d.get('memoryGit', {})
print('true' if mg.get('enabled', True) else 'false')
")"

MEMGIT_REMOTE="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
mg = d.get('memoryGit', {})
r = mg.get('remote')
print(r if r else '')
")"

MEMGIT_BRANCH="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
mg = d.get('memoryGit', {})
print(mg.get('branch', 'main'))
")"

PLUGINS_LIST="$(BRAND_PATH="$INSTALL_DIR/brand.config.json" "$PY" -c "
import json, os
d = json.load(open(os.environ['BRAND_PATH']))
for p in d.get('defaults', {}).get('plugins', {}).get('install', []):
    print(p)
")"

echo "  Brand:      $BRAND_DISPLAY (binary=$BRAND_BINARY)"
echo "  Target:     $CONFIG_DIR"
echo ""

# ── 1. Sync marketplace into the config dir ──────────────────────────────────

MARKETPLACE_SRC="$INSTALL_DIR/defaults/marketplace"
MARKETPLACE_DST="$CONFIG_DIR/plugins/marketplaces/$BRAND_BINARY"

if [ -d "$MARKETPLACE_SRC" ]; then
  echo "  Marketplace:"
  mkdir -p "$MARKETPLACE_DST"
  cp -a "$MARKETPLACE_SRC/." "$MARKETPLACE_DST/"
  echo "    [sync]  defaults/marketplace → $MARKETPLACE_DST"

  # Register in known_marketplaces.json (idempotent merge)
  KNOWN="$CONFIG_DIR/plugins/known_marketplaces.json"
  mkdir -p "$(dirname "$KNOWN")"
  KNOWN_PATH="$KNOWN" MP_NAME="$BRAND_BINARY" MP_DST="$MARKETPLACE_DST" "$PY" -c "
import json, os
from datetime import datetime, timezone

path = os.environ['KNOWN_PATH']
name = os.environ['MP_NAME']
loc = os.environ['MP_DST']

try:
    with open(path) as f: data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data[name] = {
    'source': {'source': 'directory', 'path': loc},
    'installLocation': loc,
    'lastUpdated': datetime.now(timezone.utc).isoformat(),
}

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
"
  echo "    [reg]   marketplace '$BRAND_BINARY' registered in known_marketplaces.json"
fi

# ── 2. Mark each default plugin as installed in installed_plugins.json ──────

if [ -n "$PLUGINS_LIST" ]; then
  echo ""
  echo "  Plugins:"
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    PLUGIN_PATH="$MARKETPLACE_DST/plugins/$p"
    if [ ! -d "$PLUGIN_PATH" ]; then
      echo "    [skip]  plugin '$p' — not present in marketplace"
      continue
    fi

    # Read version from plugin's own plugin.json
    VERSION="$(VPATH="$PLUGIN_PATH/.claude-plugin/plugin.json" "$PY" -c "
import json, os
try:
    with open(os.environ['VPATH']) as f: print(json.load(f).get('version', 'unknown'))
except Exception: print('unknown')
")"

    # Register install (idempotent)
    REG="$CONFIG_DIR/plugins/installed_plugins.json"
    mkdir -p "$(dirname "$REG")"
    REG_PATH="$REG" KEY="$p@$BRAND_BINARY" IPATH="$PLUGIN_PATH" V="$VERSION" "$PY" -c "
import json, os
from datetime import datetime, timezone

path = os.environ['REG_PATH']
key = os.environ['KEY']
ipath = os.environ['IPATH']
version = os.environ['V']
now = datetime.now(timezone.utc).isoformat()

try:
    with open(path) as f: data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {'version': 2, 'plugins': {}}

if 'plugins' not in data: data['plugins'] = {}
prior = data['plugins'].get(key, [{}])
data['plugins'][key] = [{
    'scope':       'user',
    'installPath': ipath,
    'version':     version,
    'installedAt': prior[0].get('installedAt', now),
    'lastUpdated': now,
}]

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
"
    # Marker dir (some lookup paths still expect this)
    mkdir -p "$CONFIG_DIR/plugins/data/${p}-${BRAND_BINARY}"
    echo "    [reg]   plugin '$p' v$VERSION → $PLUGIN_PATH"
  done <<< "$PLUGINS_LIST"
fi

# ── 3. Memory git init ───────────────────────────────────────────────────────

if [ "$MEMGIT_ENABLED" = "true" ] && command -v git >/dev/null 2>&1; then
  echo ""
  echo "  Memory git:"
  MEM_DIR="$CONFIG_DIR/memory"
  mkdir -p "$MEM_DIR"
  if [ -d "$MEM_DIR/.git" ]; then
    echo "    [keep]  $MEM_DIR/.git already exists"
  else
    (cd "$MEM_DIR" && git init --quiet --initial-branch="$MEMGIT_BRANCH" 2>/dev/null || git init --quiet)
    (cd "$MEM_DIR" && git symbolic-ref HEAD "refs/heads/$MEMGIT_BRANCH" 2>/dev/null || true)
    (cd "$MEM_DIR" && git config user.email "${BRAND_BINARY}@localhost" 2>/dev/null || true)
    (cd "$MEM_DIR" && git config user.name "${BRAND_DISPLAY} Memory Auto-commit" 2>/dev/null || true)
    cat > "$MEM_DIR/.gitignore" <<'GIT_IGNORE'
*.swp
*.swo
*~
.DS_Store
Thumbs.db
GIT_IGNORE
    (cd "$MEM_DIR" && git add -A 2>/dev/null && git commit -q -m "memory: initial commit (${BRAND_DISPLAY} install $(date -Iseconds))" 2>/dev/null) || true
    echo "    [init]  initialized $MEM_DIR/.git on branch '$MEMGIT_BRANCH'"
  fi

  if [ -n "$MEMGIT_REMOTE" ]; then
    (cd "$MEM_DIR" && git remote get-url origin >/dev/null 2>&1) || \
      (cd "$MEM_DIR" && git remote add origin "$MEMGIT_REMOTE" 2>/dev/null && echo "    [reg]   origin → $MEMGIT_REMOTE")
  fi
fi

# ── 4. Auto-enable bundled plugins in settings.json ──────────────────────────

if [ -n "$PLUGINS_LIST" ]; then
  echo ""
  echo "  Enable bundled plugins in settings.json:"
  SETTINGS="$CONFIG_DIR/settings.json"
  mkdir -p "$(dirname "$SETTINGS")"
  SETTINGS_PATH="$SETTINGS" MP_NAME="$BRAND_BINARY" "$PY" -c "
import json, os, sys
path = os.environ['SETTINGS_PATH']
marketplace = os.environ['MP_NAME']
plugins = [p for p in sys.stdin.read().splitlines() if p]

try:
    with open(path) as f: data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

ep = data.get('enabledPlugins') or {}
new_keys, kept_keys = [], []
for name in plugins:
    key = f'{name}@{marketplace}'
    if key in ep:
        kept_keys.append((key, ep[key]))
    else:
        ep[key] = True
        new_keys.append(key)

data['enabledPlugins'] = ep
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

for k in new_keys:     print(f'    [new]   enabled  {k}')
for k, v in kept_keys: print(f'    [keep]  settings already has  {k} = {v}')
" <<< "$PLUGINS_LIST"
fi

echo ""
echo "  ✓ Defaults installed for $BRAND_DISPLAY"
exit 0
