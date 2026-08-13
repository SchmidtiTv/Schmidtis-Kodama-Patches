@echo off
echo === Kodama - Server Build ===
echo.

where uv >nul 2>&1
if errorlevel 1 (
  echo FEHLER: uv ist nicht installiert.
  exit /b 1
)

uv sync --locked --group build --quiet
if errorlevel 1 exit /b 1

REM Build the server executable with the correct Tauri platform suffix
echo Kompiliere server.py...
uv run --locked --group build pyinstaller --onefile ^
  --name kodama-server-x86_64-pc-windows-msvc ^
  --distpath ..\src-tauri\binaries ^
  --workpath .\build_tmp ^
  --specpath .\build_tmp ^
  --hidden-import=ytmusicapi ^
  --hidden-import=flask ^
  --hidden-import=flask_cors ^
  --hidden-import=yt_dlp ^
  --hidden-import=pykakasi ^
  --collect-all ytmusicapi ^
  --collect-all yt_dlp ^
  --collect-all pykakasi ^
  --add-data "..\.venv\Lib\site-packages\ytmusicapi\locales;ytmusicapi/locales" ^
  server.py

echo.
if exist "..\src-tauri\binaries\kodama-server-x86_64-pc-windows-msvc.exe" (
    echo Erfolgreich! kodama-server-x86_64-pc-windows-msvc.exe wurde erstellt.
) else (
    echo FEHLER: Die .exe wurde nicht erstellt!
)
echo Jetzt kannst du "npm run tauri build" ausfuehren.
pause
