#!/bin/sh
# Buduje dist/YTDark.zip, dist/YTDark.zip.sha256 i dist/enigma2-plugin-extensions-ytdark_<wersja>_all.ipk
set -e
cd "$(dirname "$0")/.."
VER=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' YTDark/__init__.py)
[ -n "$VER" ] || { echo "Nie znaleziono __version__"; exit 1; }
rm -rf dist build
mkdir -p dist build/control build/data/usr/lib/enigma2/python/Plugins/Extensions

# czysta kopia bez cache
cp -r YTDark build/data/usr/lib/enigma2/python/Plugins/Extensions/YTDark
find build -name '__pycache__' -type d -prune -exec rm -rf {} +
find build -name '*.pyc' -delete

# ZIP (uzywany przez aktualizator w pluginie i install.sh)
mkdir -p build/zip && cp -r build/data/usr/lib/enigma2/python/Plugins/Extensions/YTDark build/zip/YTDark
(cd build/zip && zip -qr ../../dist/YTDark.zip YTDark)
(cd dist && sha256sum YTDark.zip > YTDark.zip.sha256)

# IPK
cat > build/control/control <<EOT
Package: enigma2-plugin-extensions-ytdark
Version: $VER
Architecture: all
Depends: python3-core
Maintainer: YTDark
Section: extra
Priority: optional
Description: YTDark - YouTube bez reklam (tryb goscia, wlasny odtwarzacz, SponsorBlock)
EOT
printf '#!/bin/sh\necho "YTDark zainstalowany. Zrestartuj interfejs (GUI)."\nexit 0\n' > build/control/postinst
chmod 755 build/control/postinst
(cd build/control && tar --owner=0 --group=0 -czf ../control.tar.gz .)
(cd build/data && tar --owner=0 --group=0 -czf ../data.tar.gz .)
printf '2.0\n' > build/debian-binary
(cd build && ar rc "../dist/enigma2-plugin-extensions-ytdark_${VER}_all.ipk" debian-binary control.tar.gz data.tar.gz)
rm -rf build
ls -l dist
