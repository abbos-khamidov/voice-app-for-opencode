#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Voice Reader"
BUNDLE_ID="${BUNDLE_ID:-com.adamsmidov.voicereader}"
ICON_SOURCE="assets/logo.png"

pyinstaller \
  -y \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_SOURCE" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --add-data "assets/logo.png:assets" \
  main.py
