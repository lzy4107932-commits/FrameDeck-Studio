# macOS Beta Testing

FrameDeck Studio for macOS is currently an unsigned public beta. The package is
built and automatically tested on a GitHub-hosted macOS runner, but it has not
yet been manually verified on a physical Mac.

## Before downloading

- Check the package architecture in its filename: arm64 is for Apple Silicon;
  x86_64 is for Intel Macs.
- Verify the downloaded file against the included SHA-256 checksum.
- Keep important .fds projects and source images backed up while testing.
- Do not use the beta as the only copy of production work.

## Opening an unsigned build

The application is not signed or notarized, so macOS Gatekeeper may block the
first launch. In Finder, Control-click or right-click FrameDeck Studio.app,
choose Open, and confirm that you want to open it. Do not disable Gatekeeper
system-wide.

## Priority test checklist

1. Launch the app and switch between Chinese and English.
2. Import JPG, PNG, HEIC, and folders containing many images.
3. Reorder images within one page and across different pages.
4. Copy, cut, and paste images into a selected page.
5. Use Auto Layout, then test both Confirm Layout and cancel/restore behavior.
6. Crop images and export an editable PPT; reopen it and verify recropping.
7. Save, close, and reopen an .fds project.
8. Export PowerPoint, PDF, and page images.
9. Check Retina scaling, fonts, dialogs, shortcuts, and light/dark appearance.

## Reporting a problem

Open a GitHub issue and include:

- Mac model and processor (Apple Silicon or Intel)
- macOS version
- downloaded package filename
- exact steps to reproduce
- expected and actual result
- screenshot or screen recording when useful
- crash log from ~/Library/Application Support/FrameDeck Studio/logs

Do not upload confidential projects or private source images. A minimal sample
project is preferred.