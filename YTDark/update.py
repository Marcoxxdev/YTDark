# -*- coding: utf-8 -*-
"""Aktualizacje pluginu z GitHub (Releases). Nic nie instaluje bez zgody uzytkownika.

Przebieg: sprawdz najnowsze wydanie -> pobierz YTDark.zip -> sprawdz sumy SHA-256 (jesli jest w wydaniu)
-> rozpakuj do katalogu tymczasowego -> sprawdz skladnie i wersje -> kopia zapasowa -> podmiana plikow.
Po podmianie wymagany jest restart GUI (stare moduly siedza w pamieci)."""
from __future__ import print_function

import hashlib
import io
import json
import os
import re
import shutil
import time
import zipfile

from . import UPDATE_REPO, __version__, config, net, ytlog
from .net import YTError

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
WORK = '/tmp/ytdark_update'
BACKUPS = ['/etc/enigma2/ytdark_backup', '/tmp/ytdark_backup']
CHECK_EVERY = 24 * 3600
MAX_SIZE = 5 * 1024 * 1024


def enabled():
    return bool(UPDATE_REPO) and not UPDATE_REPO.startswith('TWOJ_LOGIN') and '/' in UPDATE_REPO


def parse_ver(text):
    nums = re.findall(r'\d+', text or '')
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote, local=__version__):
    return parse_ver(remote) > parse_ver(local)


def latest():
    """Zwraca dict(version, notes, zip_url, sha_url) najnowszego wydania na GitHub."""
    if not enabled():
        raise YTError(u'Aktualizacje wyłączone: nie ustawiono repozytorium GitHub (UPDATE_REPO).')
    url = 'https://api.github.com/repos/%s/releases/latest' % UPDATE_REPO
    status, text = net.request(url, headers={'Accept': 'application/vnd.github+json',
                                             'User-Agent': 'YTDark-updater'}, timeout=15)
    if status == 404:
        raise YTError(u'Brak opublikowanych wydań w repozytorium.')
    if status != 200:
        raise YTError(u'GitHub nie odpowiada (kod %s).' % status)
    data = json.loads(text)
    zip_url = sha_url = None
    for a in data.get('assets') or []:
        name = a.get('name', '')
        if name == 'YTDark.zip':
            zip_url = a.get('browser_download_url')
        elif name == 'YTDark.zip.sha256':
            sha_url = a.get('browser_download_url')
    if not zip_url:
        raise YTError(u'W wydaniu brakuje pliku YTDark.zip.')
    tag = data.get('tag_name') or u''
    return {'version': tag.lstrip('vV'), 'notes': (data.get('body') or u'').strip(),
            'zip_url': zip_url, 'sha_url': sha_url}


def check(force=False):
    """None = nic nowego / za wczesnie na kolejne sprawdzenie; dict = dostepna nowsza wersja."""
    if not enabled():
        return None
    now = int(time.time())
    if not force and now - int(config.get('update_last') or 0) < CHECK_EVERY:
        return None
    config.put('update_last', now)
    info = latest()
    return info if is_newer(info['version']) else None


def _download(url):
    data = net.get_bytes(url, headers={'User-Agent': 'YTDark-updater'}, timeout=30)
    if not data:
        raise YTError(u'Nie udało się pobrać aktualizacji.')
    if len(data) > MAX_SIZE:
        raise YTError(u'Plik aktualizacji jest podejrzanie duży.')
    return data


def _extract(data, dest):
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in zf.namelist() if not n.endswith('/')]
    roots = [n[:-len('plugin.py')] for n in names if n.endswith('plugin.py')]
    if not roots:
        raise YTError(u'Archiwum nie zawiera pluginu.')
    root = min(roots, key=len)
    for n in names:
        if not n.startswith(root):
            continue
        rel = n[len(root):]
        if rel.startswith('/') or '..' in rel.split('/'):
            raise YTError(u'Archiwum zawiera niebezpieczne ścieżki.')
        target = os.path.join(dest, rel)
        folder = os.path.dirname(target)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(target, 'wb') as fh:
            fh.write(zf.read(n))


def _verify_tree(folder, version):
    for need in ('plugin.py', '__init__.py'):
        if not os.path.isfile(os.path.join(folder, need)):
            raise YTError(u'Archiwum jest niekompletne (brak %s).' % need)
    for base, _dirs, files in os.walk(folder):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(base, f)
                with open(path, 'rb') as fh:
                    try:
                        compile(fh.read(), path, 'exec')
                    except SyntaxError as e:
                        raise YTError(u'Błąd składni w nowej wersji (%s): %s' % (f, e))
    with open(os.path.join(folder, '__init__.py'), 'rb') as fh:
        m = re.search(br'__version__\s*=\s*["\']([^"\']+)["\']', fh.read())
    if not m or m.group(1).decode('ascii') != version:
        raise YTError(u'Wersja w archiwum nie zgadza się z wydaniem.')


def _clear(folder):
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def _backup():
    for target in BACKUPS:
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            shutil.copytree(PLUGIN_DIR, target)
            return target
        except Exception as e:
            ytlog.log('[YTDark] kopia zapasowa %s: %s' % (target, e))
    raise YTError(u'Nie udało się zrobić kopii zapasowej - przerywam.')


def _copy_in(src, dst):
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)


def install(info):
    """Pobiera i instaluje wydanie opisane przez latest(). Zwraca numer zainstalowanej wersji."""
    data = _download(info['zip_url'])
    if info.get('sha_url'):
        want = _download(info['sha_url']).decode('ascii', 'ignore').split()[:1]
        got = hashlib.sha256(data).hexdigest()
        if not want or want[0].lower() != got:
            raise YTError(u'Suma kontrolna się nie zgadza - aktualizacja odrzucona.')
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    new = os.path.join(WORK, 'new')
    os.makedirs(new)
    try:
        _extract(data, new)
        _verify_tree(new, info['version'])
        backup = _backup()
        try:
            _clear(PLUGIN_DIR)
            _copy_in(new, PLUGIN_DIR)
        except Exception:
            ytlog.log('[YTDark] blad podmiany - przywracam kopie')
            _clear(PLUGIN_DIR)
            _copy_in(backup, PLUGIN_DIR)
            raise
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    ytlog.log('[YTDark] zaktualizowano do %s (kopia: %s)' % (info['version'], backup))
    return info['version']


def rollback():
    """Przywraca kopie zapasowa sprzed ostatniej aktualizacji."""
    for target in BACKUPS:
        if os.path.isfile(os.path.join(target, 'plugin.py')):
            _clear(PLUGIN_DIR)
            _copy_in(target, PLUGIN_DIR)
            return True
    return False
