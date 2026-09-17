# FrameDeck Studio

FrameDeck Studio is a desktop tool for arranging image collections
into PowerPoint, PDF, and page-image exports.

## v12.0.0 highlights

- Auto Layout continuously fills the current rows × columns grid.
- Confirm Layout keeps the generated page boundaries so later edits do not
  pull images forward. Cancelling restores the pre-layout version.
- Page-aware image movement across pages.
- Project clipboard copy, cut, and paste.
- Editable crop export keeps the original image embedded in the PPT.
- Batch titles, spacing controls, bilingual Chinese/English UI, and five themes.
- HEIF/HEIC import when `pillow-heif` is available.

## Download for Windows

Download the portable EXE and installer from the [v12.0.0 GitHub Release](https://github.com/lzy4107932-commits/FrameDeck-Studio/releases/tag/v12.0.0).

- **Portable**: run directly without Python.
- **Installer**: installs the application and creates optional shortcuts.

Windows 10/11 x64 is supported. The first release may show the Windows
SmartScreen unknown-publisher prompt because the binaries are not code-signed.

## Run from source

```powershell
python -m pip install -r requirements.txt
python main.py
```

Run the test suite:

```powershell
python -m unittest discover -s tests
```

## Build Windows packages

```powershell
python FrameDeck_UI05_51A_packaging_preflight.py --build-portable --smoke-exe
```

Install Inno Setup 6, build the portable EXE first, then run:

```powershell
build_setup_installer.bat
```

Portable output is written to `dist/`. Installer output is written to
`installer/output/`. Generated builds and user projects are excluded by
`.gitignore`.

## License

FrameDeck Studio source code is released under the [MIT License](LICENSE).
See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for dependency notices.

## macOS unsigned beta

Download the [v12.0.0 macOS Beta 1 pre-release](https://github.com/lzy4107932-commits/FrameDeck-Studio/releases/tag/v12.0.0-macos-beta.1).

- **DMG**: recommended for normal installation.
- **ZIP**: contains the application bundle directly.
- **Architecture**: Apple Silicon ARM64 (M1, M2, M3, M4, and later).
- **Minimum configured version**: macOS 12.

This beta is not code-signed or notarized and has not yet been manually tested
on a physical Mac. Gatekeeper may block its first launch. Control-click or
right-click the application in Finder, choose **Open**, and confirm. Do not
disable Gatekeeper system-wide.

Read the [macOS beta testing guide](MACOS_BETA_TESTING.md) before installing.
Report a problem with the repository's **macOS Beta problem** issue form. Do
not upload confidential projects or private source images.

Build locally on macOS with:

    python3 -m pip install -r requirements-build.txt
    bash build_macos.sh
