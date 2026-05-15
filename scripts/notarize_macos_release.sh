#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Voice Reader"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="VoiceReader-macOS.dmg"
KEYCHAIN_PATH="$RUNNER_TEMP/app-signing.keychain-db"
CERT_PATH="$RUNNER_TEMP/developer-id-application.p12"

: "${APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_BASE64:?Missing certificate}"
: "${APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_PASSWORD:?Missing certificate password}"
: "${APPLE_TEAM_ID:?Missing Apple team id}"
: "${APPLE_ID:?Missing Apple ID}"
: "${APPLE_APP_SPECIFIC_PASSWORD:?Missing app-specific password}"

echo "$APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_BASE64" | base64 --decode > "$CERT_PATH"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security import "$CERT_PATH" -P "$APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN_PATH"
security list-keychain -d user -s "$KEYCHAIN_PATH"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"

SIGNING_IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN_PATH" | awk -F '"' '/Developer ID Application/ {print $2; exit}')"
if [[ -z "$SIGNING_IDENTITY" ]]; then
  echo "Developer ID Application signing identity not found." >&2
  exit 1
fi

codesign --force --options runtime --timestamp --deep --sign "$SIGNING_IDENTITY" "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "VoiceReader-macOS-notarize.zip"
xcrun notarytool submit "VoiceReader-macOS-notarize.zip" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait
xcrun stapler staple "$APP_PATH"

scripts/package_macos_release.sh

codesign --force --timestamp --sign "$SIGNING_IDENTITY" "$DMG_PATH"
xcrun notarytool submit "$DMG_PATH" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait
xcrun stapler staple "$DMG_PATH"

