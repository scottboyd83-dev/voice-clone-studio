#!/bin/zsh
# Build "Voice Clone Studio.app" into /Applications (or $1 if given).
# The app starts the backend + frontend if they aren't running and opens
# the studio in the default browser. Run from anywhere inside the repo.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/Applications}/Voice Clone Studio.app"

echo "Building $DEST (repo: $REPO)"
rm -rf "$DEST"
mkdir -p "$DEST/Contents/MacOS" "$DEST/Contents/Resources"

# ---- icon: PNG -> icns ----
ICONSET="$(mktemp -d)/icon.iconset"
mkdir -p "$ICONSET"
for sz in 16 32 64 128 256 512; do
  sips -z $sz $sz "$REPO/assets/icon.png" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
  dbl=$((sz * 2))
  sips -z $dbl $dbl "$REPO/assets/icon.png" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$DEST/Contents/Resources/icon.icns"

# ---- Info.plist ----
cat > "$DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Voice Clone Studio</string>
  <key>CFBundleDisplayName</key><string>Voice Clone Studio</string>
  <key>CFBundleIdentifier</key><string>local.voice-clone-studio</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
</dict>
</plist>
PLIST

# ---- launcher executable (repo path baked in at build time) ----
cat > "$DEST/Contents/MacOS/launcher" <<LAUNCH
#!/bin/zsh
# GUI apps don't inherit the shell PATH — add homebrew, uv's default
# install dir, and standard bins.
export PATH="/opt/homebrew/bin:\$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
DIR="$REPO"
URL="http://localhost:5173"

up() { curl -s -o /dev/null --max-time 1 "\$URL"; }

if ! up; then
  mkdir -p "\$DIR/data"
  ( cd "\$DIR" && nohup uv run uvicorn server.app:app --port 8000 >> data/launcher.log 2>&1 & )
  ( cd "\$DIR/frontend" && nohup npm run dev >> ../data/launcher.log 2>&1 & )
  for i in {1..90}; do
    up && break
    sleep 1
  done
fi
open "\$URL"
LAUNCH
chmod +x "$DEST/Contents/MacOS/launcher"

echo "Done — open it from /Applications (servers keep running in the background;"
echo "stop them anytime with: pkill -f 'uvicorn server.app' ; pkill -f vite)"
