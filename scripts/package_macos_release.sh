#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Voice Reader"
APP_PATH="dist/${APP_NAME}.app"
ZIP_PATH="VoiceReader-macOS.zip"
DMG_PATH="VoiceReader-macOS.dmg"
DMG_ROOT="release/dmg-root"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

rm -rf release
mkdir -p "$DMG_ROOT"

cp -R "$APP_PATH" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"
cp README.md PRIVACY.md LICENSE "$DMG_ROOT/"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_ROOT" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

