# -*- coding: utf-8 -*-
"""Wykrywanie i instalacja yt-dlp (pakiet python3-yt-dlp) przez opkg - w tle, bez przerywania pracy pluginu."""
from __future__ import print_function

import os
import re
import subprocess
import sys
import threading

from . import ytlog

PACKAGE = 'python3-yt-dlp'
TIMEOUT = 420          # sekundy na jedno polecenie opkg
_lock = threading.Lock()
busy = False


def supported():
    """Pakiet python3-yt-dlp ma sens tylko w obrazach z Pythonem 3 i opkg."""
    return sys.version_info[0] >= 3 and opkg_path() is not None


def opkg_path():
    for folder in os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin').split(os.pathsep) + ['/usr/bin', '/bin']:
        path = os.path.join(folder, 'opkg')
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def installed():
    """Szybkie sprawdzenie, czy modul yt_dlp jest dostepny (bez jego importowania)."""
    try:
        import importlib.util
        return importlib.util.find_spec('yt_dlp') is not None
    except Exception:
        try:
            import imp
            imp.find_module('yt_dlp')
            return True
        except Exception:
            return False


def _run(args):
    """Uruchamia polecenie (bez powloki), zwraca (kod, ostatnie linie wyjscia)."""
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TIMEOUT)
        out = proc.stdout.decode('utf-8', 'replace')
        code = proc.returncode
    except subprocess.TimeoutExpired:
        return 124, u'Przekroczono limit czasu (%d s).' % TIMEOUT
    except Exception as e:
        return 1, u'%s' % (e,)
    ytlog.log('[YTDark] %s -> %s' % (' '.join(args), code))
    tail = u'\n'.join([l for l in out.splitlines() if l.strip()][-6:])
    return code, tail


def version():
    """Wersja zainstalowanego pakietu z opkg (albo pusty tekst)."""
    path = opkg_path()
    if not path:
        return u''
    code, out = _run([path, 'list-installed', PACKAGE])
    m = re.search(re.escape(PACKAGE) + r'\s+-\s+(\S+)', out)
    return m.group(1) if code == 0 and m else u''


def install_or_upgrade():
    """opkg update + install (albo upgrade, jesli juz jest). Zwraca (ok, komunikat). Dziala w watku."""
    global busy
    with _lock:
        if busy:
            return False, u'Instalacja już trwa.'
        busy = True
    try:
        path = opkg_path()
        if not path or sys.version_info[0] < 3:
            return False, u'Ten obraz nie obsługuje pakietu %s (wymaga Pythona 3 i opkg).' % PACKAGE
        was = installed()
        code, out = _run([path, 'update'])
        if code != 0:
            return False, u'Nie udało się pobrać list pakietów (opkg update).\nSprawdź internet.\n' + out
        code, out = _run([path, 'upgrade' if was else 'install', PACKAGE])
        low = out.lower()
        if code != 0 or 'unknown package' in low or 'cannot find package' in low:
            if 'unknown package' in low or 'cannot find package' in low:
                return False, u'W repozytorium Twojego obrazu nie ma pakietu %s.\nZainstaluj yt-dlp ręcznie.' % PACKAGE
            return False, u'Instalacja nie powiodła się:\n' + out
        for name in [n for n in sys.modules if n == 'yt_dlp' or n.startswith('yt_dlp.')]:
            del sys.modules[name]  # nastepne odtwarzanie zaladuje nowa wersje
        try:
            import importlib
            importlib.invalidate_caches()
        except Exception:
            pass
        if not installed():
            return False, u'Pakiet zainstalowany, ale moduł yt_dlp nie jest widoczny - zrestartuj interfejs.'
        ver = version()
        return True, (u'yt-dlp %s.' % (u'zaktualizowany' if was else u'zainstalowany')) + \
            (u' Wersja pakietu: %s.' % ver if ver else u'')
    finally:
        busy = False
