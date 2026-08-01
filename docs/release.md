# Release guide

## What version 0.7.0 is

Selects 0.7.0 is a reusable local alpha: one or more footage folders, full-source playback, several exact ranges per source, comments, alternates, immutable cut versions, low-resolution previews, optional LLM proposals, and a 4K Resolve handoff linked to originals.

The Pyrenees recipes remain a reference case and are not loaded by the generic app.

## Local Mac build

```bash
./scripts/build_selects_macos_app.sh
```

This produces:

```text
dist/selects/Selects.app
dist/Selects-0.7.0-macos-x86_64.zip
```

The build verifies pinned FFmpeg/ffprobe checksums, bundles the tools, signs every executable, verifies the bundle, and creates a Finder-safe zip. Without `SELECTS_SIGN_IDENTITY`, it uses an ad-hoc signature suitable for local testing.

## Public Mac build

Public distribution requires an Apple Developer ID Application certificate and a configured notarytool keychain profile:

```bash
export SELECTS_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
./scripts/build_selects_macos_app.sh
xcrun notarytool submit dist/Selects-0.7.0-macos-x86_64.zip \
  --keychain-profile Selects --wait
xcrun stapler staple "dist/selects/Selects.app"
xcrun stapler validate "dist/selects/Selects.app"
spctl --assess --type execute --verbose "dist/selects/Selects.app"
```

Do not call a build public-ready until Gatekeeper assessment succeeds on a clean Mac. The current checked-in build targets Intel (`x86_64`). Ship an Apple-silicon build, or a verified universal build, before presenting Selects as broadly compatible.

## Release checklist

- Run `make test`, Python compilation, JavaScript syntax checks, and shell syntax checks.
- Complete the reusable acceptance project in `docs/reusable-pre-editor-spec.md`.
- Test installation outside the repository and with a clean application-data directory.
- Test a disconnected/reconnected source folder and a database backup.
- Inspect a generated FCPXML in DaVinci Resolve and compare at least three frame-level ranges with the preview manifest.
- Review `PRIVACY.md`, `SECURITY.md`, bundled FFmpeg license notice, and release notes.
- Sign, notarize, staple, and test with Gatekeeper on both supported Mac architectures.
