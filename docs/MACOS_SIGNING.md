# macOS Signing and Notarization

macOS Gatekeeper blocks or warns about unsigned apps downloaded from the internet. A DMG layout can make installation convenient, but it cannot remove the security warning by itself.

To make Voice Reader open normally for users, the macOS app must be:

1. Signed with an Apple Developer ID Application certificate.
2. Submitted to Apple notarization.
3. Stapled after notarization.
4. Packaged into DMG/ZIP after the app is signed and stapled.

The `Build Downloadable Apps` workflow already supports this flow. Add these GitHub repository secrets:

- `APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_BASE64`
- `APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_PASSWORD`
- `APPLE_TEAM_ID`
- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `MACOS_KEYCHAIN_PASSWORD` optional, used for the temporary CI keychain

## Certificate Secret

Export the Developer ID Application certificate as a `.p12` file from Keychain Access, then encode it:

```bash
base64 -i DeveloperIDApplication.p12 | pbcopy
```

Paste the copied value into `APPLE_DEVELOPER_ID_APPLICATION_CERTIFICATE_BASE64`.

## Apple App-Specific Password

Create an app-specific password at:

https://appleid.apple.com/account/manage

Use that value for `APPLE_APP_SPECIFIC_PASSWORD`.

## Unsigned Builds

If the secrets are not configured, the workflow still builds:

- `VoiceReader-macOS.zip`
- `VoiceReader-macOS.dmg`

Those builds are useful for testing, but macOS can show a Gatekeeper warning because they are not notarized.

The warning usually says Apple could not verify that the app is free of malware. That warning is expected for unsigned or non-notarized downloads and cannot be removed by changing the DMG layout.

For public tag releases (`v*`), the workflow intentionally fails when Apple signing secrets are missing. This prevents publishing a macOS DMG that looks ready for users but is blocked by Gatekeeper.
