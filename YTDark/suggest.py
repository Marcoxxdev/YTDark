# -*- coding: utf-8 -*-
"""Podpowiedzi wyszukiwania YouTube (bez klucza i logowania)."""
from __future__ import print_function

import json

try:
    from urllib.parse import quote
except ImportError:  # python 2
    from urllib import quote

from . import config, net, ytlog

try:
    string_types = basestring  # noqa: F821
except NameError:
    string_types = str

_cache = {}


def fetch(query, limit=9):
    """Lista podpowiedzi (teksty) dla wpisanej frazy; pusta lista przy bledzie."""
    q = (query or u'').strip()
    if not q:
        return []
    if q in _cache:
        return _cache[q]
    url = ('https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=pl&gl=%s&q=%s'
           % ((config.get('region') or 'PL'), quote(q.encode('utf-8'))))
    try:
        status, text = net.request(url, timeout=6)
        if status != 200:
            return []
        data = json.loads(text)
        out = []
        for s in (data[1] if len(data) > 1 else []):
            if isinstance(s, string_types) and s.strip() and s.strip().lower() != q.lower() and s not in out:
                out.append(s.strip())
    except Exception as e:
        ytlog.log('[YTDark] podpowiedzi:', e)
        return []
    out = out[:limit]
    if len(_cache) > 200:
        _cache.clear()
    _cache[q] = out
    return out
