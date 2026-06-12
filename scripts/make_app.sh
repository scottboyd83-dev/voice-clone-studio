#!/bin/zsh
# Build "Voice Clone Studio.app" into /Applications (or $1 if given).
# A stay-open applet: launching starts the backend + frontend (if down) and
# opens the studio; quitting the app (Cmd-Q / Dock > Quit) stops the servers
# and unloads every model process. Run from anywhere inside the repo.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/Applications}/Voice Clone Studio.app"

echo "Building $DEST (repo: $REPO)"
rm -rf "$DEST"
WORK="$(mktemp -d)"

# ---- applet: run/reopen start the studio, quit tears it down ----
cat > "$WORK/applet.applescript" <<'APPLESCRIPT'
on resourceScript(name)
	return quoted form of (POSIX path of (path to me) & "Contents/Resources/" & name)
end resourceScript

on run
	do shell script resourceScript("start.sh")
end run

on reopen
	do shell script resourceScript("start.sh")
end reopen

on quit
	do shell script resourceScript("stop.sh")
	continue quit
end quit
APPLESCRIPT
osacompile -s -o "$DEST" "$WORK/applet.applescript"

# ---- start.sh: bring servers up if needed, open the studio ----
cat > "$DEST/Contents/Resources/start.sh" <<START
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
START

# ---- stop.sh: kill servers + every engine/model process ----
cat > "$DEST/Contents/Resources/stop.sh" <<STOP
#!/bin/zsh
# Exactly the studio stack, nothing else that happens to live in the repo:
# backend (uvicorn, holds F5-TTS), the vite frontend + its esbuild, and the
# engine subprocesses (GPT-SoVITS api_v2, Seed-VC worker) in third_party venvs.
pkill -f "uvicorn server.app" 2>/dev/null
pkill -f "$REPO/frontend" 2>/dev/null
pkill -f "$REPO/third_party" 2>/dev/null
exit 0
STOP
chmod +x "$DEST/Contents/Resources/start.sh" "$DEST/Contents/Resources/stop.sh"

# ---- icon + identity ----
ICONSET="$WORK/icon.iconset"
mkdir -p "$ICONSET"
for sz in 16 32 64 128 256 512; do
  sips -z $sz $sz "$REPO/assets/icon.png" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
  dbl=$((sz * 2))
  sips -z $dbl $dbl "$REPO/assets/icon.png" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$DEST/Contents/Resources/applet.icns"

PLIST="$DEST/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string 'Voice Clone Studio'" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName 'Voice Clone Studio'" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleName 'Voice Clone Studio'" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.voice-clone-studio" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.voice-clone-studio" "$PLIST"
rm -rf "$WORK"

echo "Done — open it from /Applications. While the studio is running the app"
echo "stays in the Dock; quit it (Cmd-Q) to stop the servers and unload models."
