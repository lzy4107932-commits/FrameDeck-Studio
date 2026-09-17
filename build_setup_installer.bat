@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\FrameDeck Studio V12 Stable.exe" (
  echo Portable EXE not found. Run build_portable_exe.bat first.
  pause
  exit /b 1
)
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 was not found.
  echo Install Inno Setup, then run this script again.
  pause
  exit /b 1
)
"%ISCC%" "installer\FrameDeck_Studio_V12.iss"
pause
