#!/bin/sh
# Uzycie: sh tools/set_repo.sh login/nazwa-repo   (ustawia repozytorium w pluginie, README i install.sh)
set -e
[ -n "$1" ] || { echo "Podaj repozytorium, np.: sh tools/set_repo.sh jankowalski/YTDark"; exit 1; }
cd "$(dirname "$0")/.."
sed -i "s#TWOJ_LOGIN/YTDark#$1#g" YTDark/__init__.py install.sh README.md
echo "Ustawiono repozytorium: $1"
