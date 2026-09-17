@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON_CMD=py") else (set "PYTHON_CMD=python")
for /f "delims=" %%I in ('%PYTHON_CMD% -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE goto :error
rem Keep unrelated developer tools from supplying same-named DLLs to PyInstaller.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0"
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onedir --console --name "FrameDeck Studio V12 Debug" --icon "resources\icon.ico" --add-data "resources;resources" --add-data "Template;Template" --collect-all PySide6 --collect-all pillow_heif main.py
if errorlevel 1 goto :error
echo Debug build completed.
pause
exit /b 0
:error
echo Debug build failed. Review the messages above.
pause
exit /b 1
