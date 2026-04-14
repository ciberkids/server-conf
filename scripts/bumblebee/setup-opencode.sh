#!/bin/bash
# Idempotent opencode updater — runs on every openclaw container start via ExecStartPost.
# Installs/updates the native opencode ELF binary into /opt/agents/.
# On first run this takes ~10s; subsequent runs check npm and exit fast if already current.

TARGET=/opt/agents/opencode

# Check if current binary is already a native ELF
if [ -f "$TARGET" ] && file "$TARGET" 2>/dev/null | grep -q "ELF 64-bit"; then
    CURRENT_VER=$("$TARGET" --version 2>/dev/null || echo "0")
    LATEST_VER=$(npm show opencode-ai version 2>/dev/null || echo "0")
    if [ "$CURRENT_VER" = "$LATEST_VER" ]; then
        echo "opencode $CURRENT_VER already up to date"
        exit 0
    fi
    echo "opencode $CURRENT_VER -> $LATEST_VER (updating)"
fi

# Install latest opencode-ai to a temp prefix (doesn't affect global node env)
TMPDIR=$(mktemp -d)
npm install -g --prefix "$TMPDIR" opencode-ai@latest 2>&1 | tail -1

# Find the native binary (opencode-linux-x64 optional dep)
NATIVE=$(find "$TMPDIR" -path "*/opencode-linux-x64/bin/opencode" -type f 2>/dev/null | head -1)
if [ -z "$NATIVE" ]; then
    echo "ERROR: native opencode binary not found after npm install"
    rm -rf "$TMPDIR"
    exit 1
fi

cp "$NATIVE" "$TARGET"
chmod +x "$TARGET"
rm -rf "$TMPDIR"
echo "opencode $("$TARGET" --version 2>/dev/null) installed to $TARGET"
