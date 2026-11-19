#!/bin/sh
# Instalator YTDark dla dekoderow z Enigma2:
#   wget -qO- https://raw.githubusercontent.com/Marcoxxdev/YTDark/main/install.sh | sh
REPO="Marcoxxdev/YTDark"
DEST="/usr/lib/enigma2/python/Plugins/Extensions"
TMP="/tmp/ytdark_install"
BASE="https://github.com/$REPO/releases/latest/download"

fetch() {  # fetch URL PLIK - najpierw z weryfikacja certyfikatu, potem awaryjnie bez (stare obrazy)
    wget -q -O "$2" "$1" 2>/dev/null && return 0
    curl -fsSL -o "$2" "$1" 2>/dev/null && return 0
    wget -q --no-check-certificate -O "$2" "$1" 2>/dev/null && return 0
    curl -fsSLk -o "$2" "$1" 2>/dev/null && return 0
    return 1
}

rm -rf "$TMP"; mkdir -p "$TMP" || exit 1
echo "Pobieram YTDark..."
fetch "$BASE/YTDark.zip" "$TMP/YTDark.zip" || { echo "Blad pobierania."; exit 1; }
if fetch "$BASE/YTDark.zip.sha256" "$TMP/YTDark.zip.sha256" && command -v sha256sum >/dev/null 2>&1; then
    WANT=$(cut -d' ' -f1 "$TMP/YTDark.zip.sha256")
    GOT=$(sha256sum "$TMP/YTDark.zip" | cut -d' ' -f1)
    [ "$WANT" = "$GOT" ] || { echo "Suma kontrolna sie nie zgadza - przerywam."; exit 1; }
    echo "Suma kontrolna OK."
fi

if command -v unzip >/dev/null 2>&1; then
    unzip -oq "$TMP/YTDark.zip" -d "$TMP/out" || exit 1
else
    PY=$(command -v python3 || command -v python)
    "$PY" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$TMP/YTDark.zip" "$TMP/out" || exit 1
fi
[ -f "$TMP/out/YTDark/plugin.py" ] || { echo "Nieprawidlowe archiwum."; exit 1; }

rm -rf "$DEST/YTDark"
cp -r "$TMP/out/YTDark" "$DEST/YTDark" || exit 1
rm -rf "$TMP"; sync
echo "Zainstalowano. Zrestartuj interfejs: killall -9 enigma2"
