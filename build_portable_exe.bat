@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON_CMD=py") else (set "PYTHON_CMD=python")
for /f "delims=" %%I in ('%PYTHON_CMD% -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE goto :error
echo [1/3] Installing dependencies...
"%PYTHON_EXE%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :error
echo [2/3] Cleaning old build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "FrameDeck Studio V12 Stable.spec" del /q "FrameDeck Studio V12 Stable.spec"
echo [3/3] Building portable EXE...
rem Keep unrelated developer tools from supplying same-named DLLs to PyInstaller.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0"
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "FrameDeck Studio V12 Stable" --icon "resources\icon.ico" --add-data "resources;resources" --add-data "Template;Template" --add-data "LICENSE;." --add-data "THIRD_PARTY_LICENSES.md;." --collect-all PySide6 --collect-all pillow_heif main.py
if errorlevel 1 goto :error
echo Build completed.
start "" "%~dp0dist"
pause
exit /b 0
:error
echo Build failed. Review the messages above.
pause
exit /b 1
