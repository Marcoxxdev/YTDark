# -*- coding: utf-8 -*-
"""Miniatury filmow: pobieranie do /tmp z prostym czyszczeniem pamieci podrecznej."""
from __future__ import print_function
import hashlib
import os

from . import net

DIR = '/tmp/ytdark_thumbs'
MAX_FILES = 160


def path_for(url):
    return os.path.join(DIR, hashlib.md5(url.encode('utf-8')).hexdigest() + '.jpg')


def cached(url):
    p = path_for(url)
    return p if os.path.isfile(p) and os.path.getsize(p) > 500 else None


def _trim():
    try:
        files = [os.path.join(DIR, f) for f in os.listdir(DIR) if f.endswith('.jpg')]
        if len(files) > MAX_FILES:
            files.sort(key=os.path.getmtime)
            for f in files[:len(files) - MAX_FILES + 40]:
                os.remove(f)
    except Exception:
        pass


def fetch(url):
    """Zwraca sciezke do pliku JPG albo None (blokuje - wolac z watku)."""
    p = cached(url)
    if p:
        return p
    try:
        os.makedirs(DIR)
    except OSError:
        pass
    data = net.get_bytes(url, timeout=10)
    if not data or len(data) < 500:
        return None
    tmp = path_for(url) + '.part'
    try:
        with open(tmp, 'wb') as fh:
            fh.write(data)
        os.rename(tmp, path_for(url))
    except Exception:
        return None
    _trim()
    return path_for(url)
