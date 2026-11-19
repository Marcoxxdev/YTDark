# -*- coding: utf-8 -*-
"""Oficjalne YouTube Data API v3. Listy z API nie zawieraja reklam
(brak wynikow sponsorowanych), a filmy sa odtwarzane przez strumien bezposredni."""
from __future__ import print_function

from . import auth, config, net, util
from .net import YTError

BASE = 'https://www.googleapis.com/youtube/v3/'
SETUP_MSG = (u'Brak klucza API i logowania.\nUstaw api_key albo client_id/client_secret '
             u'(README_PL.txt).')
ERRORS = {
    'quotaExceeded': u'Dzienny limit zapytań YouTube API został wyczerpany. Spróbuj jutro.',
    'keyInvalid': u'Nieprawidłowy klucz API.',
    'forbidden': u'Brak uprawnień do tej listy.',
    'accessNotConfigured': u'W projekcie Google nie włączono YouTube Data API v3.',
    'insufficientPermissions': u'Brak uprawnień - zaloguj się ponownie.',
    'playlistNotFound': u'Nie znaleziono playlisty.',
}


def call(endpoint, params, need_login=False):
    params = dict((k, v) for k, v in params.items() if v not in (None, ''))
    headers = {}
    token = auth.access_token() if (need_login or auth.is_logged_in()) and not auth.is_tv() else None
    if token:
        headers['Authorization'] = 'Bearer ' + token
    elif need_login:
        raise YTError(u'Ta lista wymaga zalogowania (Ustawienia → Zaloguj).')
    else:
        key = config.get('api_key')
        if not key:
            raise YTError(SETUP_MSG)
        params['key'] = key
    qs = net.urlencode(params)
    status, data = net.get_json(BASE + endpoint + '?' + qs, headers=headers)
    if status != 200:
        err = data.get('error', {}) if isinstance(data, dict) else {}
        reasons = [e.get('reason') for e in err.get('errors', [])]
        for r in reasons:
            if r in ERRORS:
                raise YTError(ERRORS[r])
        raise YTError(u'Błąd YouTube API (%s): %s' % (status, err.get('message', u'nieznany')))
    return data


# ---------------------------------------------------------------- budowa pozycji
def _info(lines):
    return u'\n'.join(l for l in lines if l)


def _video_item(vid, title, channel, published=u'', live=False):
    info = _info([u'Kanał: ' + channel if channel else u'',
                  u'Data: ' + published[:10] if published else u''])
    return {'kind': 'video', 'id': vid, 'name': util.clean(title), 'right': u'', 'num': 0,
            'info': info, 'live': live, 'channel': channel}


def _more_item(loader):
    return {'name': u'Wczytaj więcej  ▼', 'more': loader, 'kind': 'more'}


def _enrich(items):
    """Dolacza czas trwania i liczbe wyswietlen (1 zapytanie na 50 filmow)."""
    vids = [i for i in items if i['kind'] == 'video']
    for n in range(0, len(vids), 50):
        chunk = vids[n:n + 50]
        data = call('videos', {'part': 'contentDetails,statistics,snippet',
                               'id': ','.join(v['id'] for v in chunk)})
        det = dict((x['id'], x) for x in data.get('items', []))
        for v in chunk:
            d = det.get(v['id'])
            if not d:
                continue
            secs = util.parse_iso_duration(d.get('contentDetails', {}).get('duration'))
            live = d.get('snippet', {}).get('liveBroadcastContent') == 'live'
            v['num'] = secs
            v['right'] = u'NA ŻYWO' if live else util.fmt_duration(secs)
            v['live'] = live
            views = util.fmt_number(d.get('statistics', {}).get('viewCount'))
            v['info'] = _info([v['info'], u'Wyświetlenia: ' + views if views else u''])
    return items


# ---------------------------------------------------------------- listy
def search(query, page_token=None):
    data = call('search', {'part': 'snippet', 'q': query, 'type': 'video,channel,playlist',
                           'maxResults': 25, 'pageToken': page_token,
                           'regionCode': config.get('region')})
    items = []
    for r in data.get('items', []):
        sn, rid = r.get('snippet', {}), r.get('id', {})
        kind = rid.get('kind', '')
        title = util.clean(sn.get('title', ''))
        if kind == 'youtube#video':
            items.append(_video_item(rid['videoId'], title, util.clean(sn.get('channelTitle', '')),
                                     sn.get('publishedAt', ''), sn.get('liveBroadcastContent') == 'live'))
        elif kind == 'youtube#channel':
            items.append({'kind': 'channel', 'id': rid['channelId'], 'name': u'[Kanał] ' + title,
                          'right': u'', 'num': 0, 'info': u'Kanał YouTube'})
        elif kind == 'youtube#playlist':
            items.append({'kind': 'playlist', 'id': rid['playlistId'], 'name': u'[Playlista] ' + title,
                          'right': u'', 'num': 0,
                          'info': u'Kanał: ' + util.clean(sn.get('channelTitle', ''))})
    _enrich(items)
    nxt = data.get('nextPageToken')
    if nxt:
        items.append(_more_item(lambda: search(query, nxt)))
    return items


def _videos_from_videos_list(data):
    items = []
    for r in data.get('items', []):
        sn = r.get('snippet', {})
        v = _video_item(r['id'], sn.get('title', ''), util.clean(sn.get('channelTitle', '')),
                        sn.get('publishedAt', ''), sn.get('liveBroadcastContent') == 'live')
        secs = util.parse_iso_duration(r.get('contentDetails', {}).get('duration'))
        v['num'] = secs
        v['right'] = u'NA ŻYWO' if v['live'] else util.fmt_duration(secs)
        views = util.fmt_number(r.get('statistics', {}).get('viewCount'))
        if views:
            v['info'] = _info([v['info'], u'Wyświetlenia: ' + views])
        items.append(v)
    return items


def trending(category=None, page_token=None):
    data = call('videos', {'part': 'snippet,contentDetails,statistics', 'chart': 'mostPopular',
                           'regionCode': config.get('region'), 'videoCategoryId': category,
                           'maxResults': 50, 'pageToken': page_token})
    items = _videos_from_videos_list(data)
    nxt = data.get('nextPageToken')
    if nxt:
        items.append(_more_item(lambda: trending(category, nxt)))
    return items


def categories():
    data = call('videoCategories', {'part': 'snippet', 'regionCode': config.get('region'), 'hl': 'pl'})
    out = []
    for r in data.get('items', []):
        if r.get('snippet', {}).get('assignable'):
            out.append({'kind': 'category', 'id': r['id'], 'name': util.clean(r['snippet']['title']),
                        'right': u'', 'num': 0, 'info': u'Najpopularniejsze w kategorii'})
    return out


def subscriptions(page_token=None):
    data = call('subscriptions', {'part': 'snippet,contentDetails', 'mine': 'true', 'maxResults': 50,
                                  'order': 'alphabetical', 'pageToken': page_token}, need_login=True)
    items = []
    for r in data.get('items', []):
        sn = r.get('snippet', {})
        n = int(r.get('contentDetails', {}).get('totalItemCount', 0) or 0)
        items.append({'kind': 'channel', 'id': sn.get('resourceId', {}).get('channelId'),
                      'name': util.clean(sn.get('title', '')), 'right': u'%d' % n if n else u'',
                      'num': n, 'info': u'Subskrybowany kanał'})
    nxt = data.get('nextPageToken')
    if nxt:
        items.append(_more_item(lambda: subscriptions(nxt)))
    return items


def my_playlists(page_token=None):
    data = call('playlists', {'part': 'snippet,contentDetails', 'mine': 'true', 'maxResults': 50,
                              'pageToken': page_token}, need_login=True)
    items = []
    for r in data.get('items', []):
        n = int(r.get('contentDetails', {}).get('itemCount', 0) or 0)
        items.append({'kind': 'playlist', 'id': r['id'], 'name': util.clean(r['snippet']['title']),
                      'right': u'%d' % n, 'num': n, 'info': u'Twoja playlista'})
    nxt = data.get('nextPageToken')
    if nxt:
        items.append(_more_item(lambda: my_playlists(nxt)))
    return items


def playlist_items(playlist_id, page_token=None):
    data = call('playlistItems', {'part': 'snippet,contentDetails', 'playlistId': playlist_id,
                                  'maxResults': 50, 'pageToken': page_token})
    items = []
    for r in data.get('items', []):
        sn = r.get('snippet', {})
        title = sn.get('title', '')
        vid = r.get('contentDetails', {}).get('videoId')
        if not vid or title in ('Private video', 'Deleted video'):
            continue
        items.append(_video_item(vid, title, util.clean(sn.get('videoOwnerChannelTitle', '')),
                                 r.get('contentDetails', {}).get('videoPublishedAt', '')))
    _enrich(items)
    nxt = data.get('nextPageToken')
    if nxt:
        items.append(_more_item(lambda: playlist_items(playlist_id, nxt)))
    return items


def uploads_playlist(channel_id=None):
    """ID playlisty 'przeslane' kanalu (albo wlasnego kanalu po zalogowaniu)."""
    params = {'part': 'contentDetails'}
    if channel_id:
        params['id'] = channel_id
    else:
        params['mine'] = 'true'
    data = call('channels', params, need_login=not channel_id)
    for r in data.get('items', []):
        return r.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')
    raise YTError(u'Nie znaleziono kanału.')


def channel_videos(channel_id):
    pid = uploads_playlist(channel_id)
    if not pid:
        raise YTError(u'Kanał nie ma publicznych filmów.')
    return playlist_items(pid)


def liked_videos():
    data = call('channels', {'part': 'contentDetails', 'mine': 'true'}, need_login=True)
    for r in data.get('items', []):
        pid = r.get('contentDetails', {}).get('relatedPlaylists', {}).get('likes')
        if pid:
            return playlist_items(pid)
    raise YTError(u'Nie znaleziono listy polubionych.')


def my_uploads():
    return playlist_items(uploads_playlist(None))


def by_ids(entries):
    """Historia / ulubione (zapisane lokalnie) -> pozycje z czasem trwania."""
    items = [_video_item(e['id'], e['name'], u'') for e in entries]
    if items:
        try:
            _enrich(items)
        except Exception:
            pass  # brak internetu/klucza: lista lokalna dziala bez szczegolow
    return items
