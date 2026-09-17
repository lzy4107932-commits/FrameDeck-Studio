# FrameDeck Studio v12.0.0 macOS Beta 1

This is the first unsigned public macOS test build of FrameDeck Studio.

## Package

- Architecture: Apple Silicon ARM64
- Minimum configured macOS version: macOS 12
- Formats: application ZIP and DMG
- Python is not required
- A SHA-256 checksum file is included

## Automated verification

The package is built on a GitHub-hosted macOS 14 ARM64 runner. The workflow:

- installs all production and packaging dependencies
- passes the full unit and macOS regression suite
- generates the native application bundle, ZIP, and DMG
- verifies the bundle structure and metadata
- launches the packaged application in offscreen mode for eight seconds
- publishes packages only after all checks pass

## Important testing notice

This build has not yet been manually tested on a physical Mac. It is not signed
with an Apple Developer ID and is not notarized. macOS Gatekeeper may block the
first launch.

In Finder, Control-click or right-click FrameDeck Studio.app, choose Open, and
confirm. Do not disable Gatekeeper system-wide.

Back up important projects and source images. Do not use this beta as the only
copy of production work.

See MACOS_BETA_TESTING.md in the repository for the test checklist and issue
reporting instructions.
