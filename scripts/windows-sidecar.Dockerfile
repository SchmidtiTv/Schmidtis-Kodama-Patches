# Windows Python 3.12 under Wine, for building the PyInstaller sidecar on macOS.
#
# The image's Wine 9.17 lacks ucrtbase.crealf, which numpy's OpenBLAS calls on import, so
# PyInstaller's hook discovery crashes. Microsoft's own ucrtbase.dll (from the VC++ 2019
# redistributable, via winetricks) provides it. Newer pywine tags ship Wine 11, which has
# crealf but aborts under Docker Desktop's amd64 emulation on Apple Silicon.
FROM tobix/pywine:3.12

ARG WINETRICKS_VERSION=20250102

RUN apt-get update \
  && apt-get install -y --no-install-recommends cabextract \
  && rm -rf /var/lib/apt/lists/* \
  && curl --fail -sSL -o /usr/local/bin/winetricks \
    "https://raw.githubusercontent.com/Winetricks/winetricks/${WINETRICKS_VERSION}/src/winetricks" \
  && chmod +x /usr/local/bin/winetricks \
  && xvfb-run sh -c "winetricks -q ucrtbase2019; wineserver -w" \
  && rm -rf /root/.cache/winetricks
