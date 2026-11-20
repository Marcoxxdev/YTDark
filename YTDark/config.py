# -*- coding: utf-8 -*-
"""Ustawienia, tokeny logowania, ulubione i historia - jeden plik JSON (chmod 600)."""
from __future__ import print_function
import json
import os

from . import ytlog

PATHS = ['/etc/enigma2/ytdark.json', '/tmp/ytdark.json']
IMPORT_PATHS = ['/media/usb/ytdark_credentials.json', '/media/hdd/ytdark_credentials.json',
                '/tmp/ytdark_credentials.json']
DEFAULTS = {
    'client_id': '', 'client_secret': '', 'api_key': '',
    'region': 'PL', 'sponsorblock': True, 'max_height': 720, 'player_type': 0,
    'tokens': {}, 'favs': [], 'history': [], 'searches': [], 'thumbs': True,
    'resume': {}, 'resume_on': True, 'autoplay': True, 'main_menu': False, 'update_check': True, 'ytdlp_prompt': True, 'update_last': 0,
}
_cache = {}


def _path():
    for p in PATHS:
        d = os.path.dirname(p)
        if os.path.isdir(d) and os.access(d, os.W_OK):
            return p
    return PATHS[-1]


def load(force=False):
    if _cache and not force:
        return _cache
    data = {}
    for p in PATHS:
        try:
            with open(p, 'r') as fh:
                data = json.load(fh)
            break
        except Exception:
            continue
    merged = dict(DEFAULTS)
    merged.update(data if isinstance(data, dict) else {})
    _cache.clear()
    _cache.update(merged)
    return _cache


def save():
    try:
        p = _path()
        with open(p, 'w') as fh:
            json.dump(_cache, fh, ensure_ascii=False, indent=1)
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        return True
    except Exception as e:
        ytlog.log('[YTDark] save error:', e)
        return False


def get(key):
    return load().get(key, DEFAULTS.get(key))


def put(key, value):
    load()[key] = value
    save()


def import_credentials():
    """Wczytuje client_id / client_secret / api_key z pliku na pendrivie lub w /tmp."""
    cfg = load()
    for p in IMPORT_PATHS:
        try:
            with open(p, 'r') as fh:
                data = json.load(fh)
        except Exception:
            continue
        found = False
        for k in ('client_id', 'client_secret', 'api_key'):
            if data.get(k):
                cfg[k] = data[k].strip()
                found = True
        if found:
            save()
            return p
    return None


# ---- historia i ulubione ----
def _entry(item):
    """Zapisujemy tez kanal i czas trwania, zeby lista lokalna dzialala bez internetu/klucza."""
    return {'id': item['id'], 'name': item['name'],
            'channel': item.get('channel') or u'', 'right': item.get('right') or u''}


def add_search(query, limit=12):
    cfg = load()
    cfg['searches'] = [query] + [q for q in cfg.get('searches', []) if q != query][:limit - 1]
    save()



def add_history(item, limit=60):
    cfg = load()
    entry = _entry(item)
    cfg['history'] = [entry] + [h for h in cfg['history'] if h['id'] != item['id']][:limit - 1]
    save()


def is_fav(vid):
    return any(f['id'] == vid for f in load()['favs'])


def toggle_fav(item):
    cfg = load()
    for f in list(cfg['favs']):
        if f['id'] == item['id']:
            cfg['favs'].remove(f)
            save()
            return False
    cfg['favs'].append(_entry(item))
    save()
    return True
