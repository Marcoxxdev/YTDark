# -*- coding: utf-8 -*-
"""Wybor zrodla list: domyslnie tryb goscia (bez klucza i logowania, innertube.py).
Oficjalne API (api.py) sluzy jako zapas - tylko jesli ktos skonfigurowal klucz / zalogowal sie."""
from __future__ import print_function

from . import api, auth, config, innertube
from .net import YTError


def _official_ready():
    return bool(config.get('api_key') or (auth.is_logged_in() and not auth.is_tv()))


def _run(guest, official=None):
    err = None
    try:
        items = guest()
        if items:
            return items
    except YTError as e:
        err = e
    except Exception as e:
        err = YTError(u'Nie udało się odczytać odpowiedzi YouTube (%s).' % (e,))
    if official is not None and _official_ready():
        return official()
    if err:
        raise err
    return []


def search(query, params=None):
    return _run(lambda: innertube.search(query, params),
                (lambda: api.search(query)) if not params else None)


def home():
    if auth.is_tv():  # polecane dla zalogowanego konta
        return _run(lambda: innertube.tv_first('FEwhat_to_watch'), innertube.home)
    return _run(innertube.home)


def trending():
    return _run(innertube.trending, api.trending)


def categories():
    return innertube.categories()


def subscriptions():
    return innertube.tv_first('FEsubscriptions') if auth.is_tv() else api.subscriptions()


def my_playlists():
    return innertube.tv_first('FEplaylist_aggregation', 'FElibrary') if auth.is_tv() else api.my_playlists()


def liked_videos():
    return innertube.tv_first('VLLL') if auth.is_tv() else api.liked_videos()


def watch_later():
    return innertube.tv_first('VLWL')


def yt_history():
    return innertube.tv_first('FEhistory')


def channel_videos(channel_id):
    return _run(lambda: innertube.channel_videos(channel_id), lambda: api.channel_videos(channel_id))


def playlist_items(playlist_id):
    if auth.is_tv():  # takze prywatne playlisty konta
        return _run(lambda: innertube.tv_first('VL' + playlist_id),
                    lambda: innertube.playlist_items(playlist_id))
    return _run(lambda: innertube.playlist_items(playlist_id), lambda: api.playlist_items(playlist_id))


def local_items(entries):
    """Historia / ulubione z pliku konfiguracji - bez zapytan do sieci."""
    out = []
    for e in entries:
        ch = e.get('channel') or u''
        out.append({'kind': 'video', 'id': e['id'], 'name': e['name'], 'sub': ch,
                    'right': e.get('right') or u'', 'num': 0, 'live': False, 'channel': ch,
                    'info': (u'Kanał: ' + ch) if ch else u'', 'thumb': innertube.thumb_url(e['id'])})
    return out
