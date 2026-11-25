# -*- coding: utf-8 -*-
"""Wykrywanie i instalacja pakietow wymaganych przez plugin (opkg), tylko za zgoda uzytkownika.

Sprawdzamy: moduly Pythona, odtwarzacz HLS (ServiceApp + exteplayer3 albo gstreamer z HLS), yt-dlp, certyfikaty HTTPS.
Nazwy pakietow roznia sie miedzy obrazami, wiec dla kazdego braku mamy liste kandydatow - instalujemy pierwszy,
ktory istnieje w repozytorium obrazu (sprawdzane przez `opkg info`)."""
from __future__ import print_function

import glob
import importlib
import os
import re
import subprocess
import sys
import threading

from . import ytdlp_setup, ytlog

SERVICEAPP_DIR = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ServiceApp'
TIMEOUT = 420
_lock = threading.Lock()
busy = False

# (modul, [pakiety-kandydaci])
PY_MODULES = [
    ('json', ['python3-json']),
    ('ssl', ['python3-ssl']),
    ('zipfile', ['python3-zipfile', 'python3-compression']),
    ('hashlib', ['python3-crypt', 'python3-hashlib']),
    ('http.server', ['python3-netserver']),
    ('socketserver', ['python3-netserver']),
    ('subprocess', ['python3-subprocess']),
    ('importlib.util', ['python3-importlib']),
]
# pakiety, po ktorych trzeba zrestartowac interfejs (nowe uslugi / wtyczki Enigmy)
NEEDS_RESTART = ('serviceapp', 'gstreamer')


def _exists(paths):
    return any(os.path.exists(p) for p in paths)


def have_exteplayer3_binary():
    return _exists(('/usr/bin/exteplayer3', '/usr/local/bin/exteplayer3'))


def have_serviceapp():
    """ServiceApp rejestruje w Enigmie usluge 5002 (exteplayer3) - bez niej sam program nic nie odtworzy."""
    return os.path.isdir(SERVICEAPP_DIR)


def exteplayer3_ready():
    return have_exteplayer3_binary() and have_serviceapp()


def have_gst_hls():
    for pattern in ('/usr/lib/gstreamer-1.0/libgsthls.so*', '/usr/lib/gstreamer-1.0/libgstadaptivedemux2.so*',
                    '/usr/lib*/gstreamer-1.0/libgsthls*', '/usr/lib*/gstreamer-1.0/libgstadaptivedemux*'):
        if glob.glob(pattern):
            return True
    return False


def have_certs():
    return _exists(('/etc/ssl/certs/ca-certificates.crt', '/etc/ssl/certs/ca-bundle.crt',
                    '/etc/ssl/certs/ca-certificates'))


def missing_py_modules():
    out = []
    for mod, candidates in PY_MODULES:
        try:
            importlib.import_module(mod)
        except Exception:
            out.append((mod, candidates))
    return out


def scan():
    """Lista brakow: dict(id, label, why, candidates, critical). Pusta lista = wszystko jest."""
    problems = []
    if sys.version_info[0] < 3:
        return problems
    for mod, candidates in missing_py_modules():
        problems.append({'id': 'py:' + mod, 'label': u'moduł Pythona „%s”' % mod,
                         'why': u'wymagany do działania pluginu', 'candidates': candidates, 'critical': True})
    if not (exteplayer3_ready() or have_gst_hls()):
        problems.append({
            'id': 'player', 'label': u'odtwarzacz HLS (ServiceApp z exteplayer3 albo gstreamer z HLS)',
            'why': u'bez niego film się pobierze, ale nie zacznie grać',
            'candidates': ['enigma2-plugin-systemplugins-serviceapp', 'gstreamer1.0-plugins-bad-adaptivedemux2',
                           'gstreamer1.0-plugins-bad-hls'], 'critical': True})
    if ytdlp_setup.supported() and not ytdlp_setup.installed():
        problems.append({'id': 'ytdlp', 'label': u'yt-dlp (%s)' % ytdlp_setup.PACKAGE,
                         'why': u'zapas, gdy własne metody pobierania zawiodą (np. filmy z ograniczeniem wieku)',
                         'candidates': [ytdlp_setup.PACKAGE], 'critical': False})
    if not have_certs():
        problems.append({'id': 'certs', 'label': u'certyfikaty HTTPS (ca-certificates)',
                         'why': u'bezpieczne połączenia z YouTube i GitHub', 'candidates': ['ca-certificates'],
                         'critical': False})
    return problems


def describe(problems):
    return u'\n'.join(u'\u2022 %s - %s' % (p['label'], p['why']) for p in problems)


def environment():
    """Jedna linia do logu: z niej widac, czego brakuje na danym obrazie."""
    image = u''
    for path in ('/etc/image-version', '/etc/issue'):
        try:
            with open(path, 'rb') as fh:
                lines = [l.strip() for l in fh.read().decode('utf-8', 'replace').splitlines() if l.strip()]
            image = u' / '.join(lines[:3])
            break
        except Exception:
            continue
    return (u'srodowisko: python %s | obraz: %s | exteplayer3 bin=%s serviceapp=%s | gst_hls=%s | yt-dlp=%s | '
            u'certs=%s | opkg=%s' % (sys.version.split()[0], image[:120], have_exteplayer3_binary(),
                                     have_serviceapp(), have_gst_hls(), ytdlp_setup.installed(), have_certs(),
                                     bool(ytdlp_setup.opkg_path())))


def can_install():
    return sys.version_info[0] >= 3 and ytdlp_setup.opkg_path() is not None


def _run(args):
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TIMEOUT)
        return proc.returncode, proc.stdout.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 124, u'Przekroczono limit czasu (%d s).' % TIMEOUT
    except Exception as e:
        return 1, u'%s' % (e,)


def available(opkg, pkg):
    code, out = _run([opkg, 'info', pkg])
    return code == 0 and re.search(r'^Package:\s*%s\s*$' % re.escape(pkg), out, re.M) is not None


def install(problems):
    """Instaluje braki (opkg). Zwraca (wszystko_ok, tekst_podsumowania, czy_potrzebny_restart_GUI). Dziala w watku."""
    global busy
    with _lock:
        if busy:
            return False, u'Instalacja już trwa.', False
        busy = True
    try:
        opkg = ytdlp_setup.opkg_path()
        if not opkg or sys.version_info[0] < 3:
            return False, u'Ten obraz nie obsługuje instalacji pakietów przez opkg.', False
        code, out = _run([opkg, 'update'])
        if code != 0:
            return False, u'Nie udało się pobrać list pakietów (opkg update).\nSprawdź internet.', False
        lines, ok_all, restart = [], True, False
        for pr in problems:
            if pr['id'] == 'ytdlp':  # ma wlasna obsluge (zeruje pomiar czasu, czysci moduly)
                ok, msg = ytdlp_setup.install_or_upgrade()
                lines.append(u'%s %s' % (u'\u2714' if ok else u'\u2716', msg.split(u'\n')[0]))
                ok_all = ok_all and ok
                continue
            done = False
            tried = False
            for pkg in pr['candidates']:
                if not available(opkg, pkg):
                    continue
                tried = True
                code, out = _run([opkg, 'install', pkg])
                ytlog.log('[YTDark] opkg install %s -> %s' % (pkg, code))
                if code == 0:
                    lines.append(u'\u2714 zainstalowano %s' % pkg)
                    restart = restart or any(k in pkg for k in NEEDS_RESTART)
                    done = True
                    break
                lines.append(u'\u2716 %s: %s' % (pkg, u' '.join(out.split())[-80:]))
            if not done:
                ok_all = False
                if not tried:
                    lines.append(u'\u2716 %s: brak pakietu w repozytorium tego obrazu' % pr['label'])
        try:
            importlib.invalidate_caches()
        except Exception:
            pass
        return ok_all, u'\n'.join(lines), restart
    finally:
        busy = False
