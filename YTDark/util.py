# -*- coding: utf-8 -*-
"""Sortowanie, filtrowanie i formatowanie (czyste funkcje, bez Enigmy)."""
from __future__ import print_function
import re
import unicodedata

try:
    from html import unescape as _unescape
except ImportError:  # python 2
    from HTMLParser import HTMLParser
    _unescape = HTMLParser().unescape


def clean(text):
    text = re.sub(r'<[^>]+>', '', text or '')
    return re.sub(r'\s+', ' ', _unescape(text)).strip()


def fold(text):
    if not isinstance(text, type(u'')):
        text = text.decode('utf-8', 'ignore')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.replace(u'\u0142', 'l').lower()


def sort_key(name):
    name = re.sub(r'^\[[^\]]*\]\s*', '', name)  # pomija znaczniki typu [Kanał] / [Playlista]
    return re.sub(r'^[^0-9a-z]+', '', fold(name))


def sort_items(items, mode):
    """Pozycje oznaczone 'more' (wczytaj kolejna strone) zawsze zostaja na koncu."""
    main = [i for i in items if not i.get('more')]
    more = [i for i in items if i.get('more')]
    if mode == 'az':
        main = sorted(main, key=lambda i: sort_key(i['name']))
    elif mode == 'za':
        main = sorted(main, key=lambda i: sort_key(i['name']), reverse=True)
    elif mode == 'count':
        main = sorted(main, key=lambda i: (-(i.get('num') or 0), sort_key(i['name'])))
    return main + more


def filter_items(items, text):
    if not text:
        return list(items)
    needle = fold(text)
    return [i for i in items if i.get('more') or needle in fold(i['name'])]


def fmt_duration(sec):
    sec = int(sec or 0)
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)


def parse_iso_duration(text):
    m = re.match(r'^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', text or '')
    if not m:
        return 0
    d, h, mi, s = [int(x or 0) for x in m.groups()]
    return d * 86400 + h * 3600 + mi * 60 + s


def fmt_number(n):
    try:
        return '{:,}'.format(int(n)).replace(',', ' ')
    except (TypeError, ValueError):
        return ''
