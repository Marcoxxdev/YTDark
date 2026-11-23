# -*- coding: utf-8 -*-
"""Tryb goscia: wyszukiwanie i przegladanie YouTube BEZ klucza API i BEZ logowania.

Korzysta z tego samego wewnetrznego interfejsu (youtubei), ktorego uzywa strona youtube.com
w przegladarce dla niezalogowanego widza. Odpowiedzi sa duze i zmienne, wiec parser nie
zaklada stalego ukladu - przeszukuje JSON i wylapuje znane typy kafelkow. Reklamy
(adSlotRenderer, promoted...) oraz Shorts sa pomijane.

Gdy YouTube zmieni format, wystarczy poprawic stale ponizej (WEB_VERSION) albo parser."""
from __future__ import print_function

import re

from . import ytlog
from . import auth, config, net, util
from .net import YTError

try:
    string_types = basestring  # noqa: F821  (python 2)
except NameError:
    string_types = str

BASE = 'https://www.youtube.com/youtubei/v1/'
# Publiczny klucz klienta WWW (ten sam jest w kodzie strony youtube.com - nie jest tajny).
WEB_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
WEB_VERSION = '2.20250925.01.00'
TV_VERSION = '7.20250923.13.00'
TV_UA = 'Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version'

# filtry wyszukiwania (parametr "sp" z adresu youtube.com)
SP_WEEK_VIEWS_VIDEO = 'CAMSBAgDEAE='   # ten tydzien + filmy + wg liczby wyswietlen
SP_LIVE = 'EgJAAQ=='                   # tylko transmisje na zywo

CATEGORIES = [
    (u'Muzyka', u'muzyka nowości hity', SP_WEEK_VIEWS_VIDEO),
    (u'Gry', u'gry gameplay', SP_WEEK_VIEWS_VIDEO),
    (u'Sport', u'sport skrót meczu', SP_WEEK_VIEWS_VIDEO),
    (u'Wiadomości', u'wiadomości najnowsze', SP_WEEK_VIEWS_VIDEO),
    (u'Filmy i seriale', u'zwiastun premiera', SP_WEEK_VIEWS_VIDEO),
    (u'Nauka i technika', u'nauka technologia', SP_WEEK_VIEWS_VIDEO),
    (u'Komedia', u'kabaret stand-up', SP_WEEK_VIEWS_VIDEO),
    (u'Kuchnia', u'przepisy gotowanie', SP_WEEK_VIEWS_VIDEO),
    (u'Podróże', u'podróże vlog', SP_WEEK_VIEWS_VIDEO),
    (u'Motoryzacja', u'motoryzacja test', SP_WEEK_VIEWS_VIDEO),
    (u'Dla dzieci', u'bajki dla dzieci', SP_WEEK_VIEWS_VIDEO),
    (u'Na żywo', u'na żywo', SP_LIVE),
]

SKIP_KEYS = set([
    'adSlotRenderer', 'promotedSparklesWebRenderer', 'promotedVideoRenderer', 'searchPyvRenderer',
    'compactPromotedVideoRenderer', 'displayAdRenderer', 'bannerPromoRenderer',
    'reelShelfRenderer', 'reelItemRenderer', 'shortsLockupViewModel',
])
VIDEO_KEYS = ('videoRenderer', 'gridVideoRenderer', 'compactVideoRenderer', 'playlistVideoRenderer',
              'playlistPanelVideoRenderer')
CHANNEL_KEYS = ('channelRenderer', 'gridChannelRenderer')
PLAYLIST_KEYS = ('playlistRenderer', 'gridPlaylistRenderer')


# ---------------------------------------------------------------- HTTP
def _context(tv=False):
    return {'client': {'clientName': 'TVHTML5' if tv else 'WEB',
                       'clientVersion': TV_VERSION if tv else WEB_VERSION, 'hl': 'pl',
                       'gl': config.get('region') or 'PL'}}


def _post(endpoint, body, tv=False):
    """tv=True: klient telewizyjny z tokenem zalogowanego konta (listy osobiste)."""
    body = dict((k, v) for k, v in body.items() if v not in (None, ''))
    body['context'] = _context(tv)
    headers = {'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/',
               'Accept-Language': 'pl-PL,pl;q=0.9', 'Cookie': 'SOCS=CAI'}
    if tv:
        headers.update({'User-Agent': TV_UA, 'X-YouTube-Client-Name': '7',
                        'X-YouTube-Client-Version': TV_VERSION})
        token = auth.access_token()
        if token:
            headers['Authorization'] = 'Bearer ' + token
        url = BASE + endpoint + '?prettyPrint=false'
    else:
        headers.update({'X-YouTube-Client-Name': '1', 'X-YouTube-Client-Version': WEB_VERSION})
        url = BASE + endpoint + '?prettyPrint=false&key=' + WEB_KEY
    status, data = net.post_json(url, body, headers=headers, as_json=True)
    if status != 200:
        ytlog.log('[YTDark] youtubei %s -> %s: %s | %s' % (endpoint, status, str(data)[:300],
                                                       dict((k, v) for k, v in body.items() if k != 'context')))
    if status == 401 and tv:
        raise YTError(u'Sesja wygasła. Zaloguj się ponownie (Ustawienia).')
    if status != 200 or not isinstance(data, dict) or not data:
        raise YTError(u'YouTube nie odpowiada poprawnie (kod %s).' % status)
    return data


# ---------------------------------------------------------------- pomocnicze
def _t(node):
    """Tekst z roznych form YouTube: simpleText / runs / content."""
    if node is None:
        return u''
    if isinstance(node, string_types):
        return node
    if isinstance(node, dict):
        if 'simpleText' in node:
            return node['simpleText']
        if 'content' in node:
            return node['content']
        if 'runs' in node:
            return u''.join(r.get('text', u'') for r in node['runs'])
    return u''


def thumb_url(video_id):
    return 'https://i.ytimg.com/vi/%s/mqdefault.jpg' % video_id


def _fix_url(url):
    if url and url.startswith('//'):
        return 'https:' + url
    return url or u''


def _clock(text):
    """'1:02:03' -> sekundy (0 gdy to nie jest zapis czasu)."""
    if not text or ':' not in text or not re.match(r'^\d+(:\d{1,2})+$', text.strip()):
        return 0
    sec = 0
    for part in text.strip().split(':'):
        sec = sec * 60 + int(part)
    return sec


def _video_item(vid, title, channel, views, when, length, live, desc=u''):
    secs = _clock(length)
    sub = u' • '.join(x for x in (channel, views, when) if x)
    info = [u'Kanał: ' + channel if channel else u'',
            views, u'Opublikowano: ' + when if when else u'']
    if length and not live:
        info.append(u'Czas: ' + length)
    if desc:
        info += [u'', desc]
    return {'kind': 'video', 'id': vid, 'name': util.clean(title), 'sub': sub,
            'right': u'NA ŻYWO' if live else (length or u''), 'num': secs,
            'info': u'\n'.join(i for i in info if i is not None), 'live': bool(live),
            'channel': channel, 'thumb': thumb_url(vid)}


def _more_item(loader):
    return {'name': u'Wczytaj więcej  ▼', 'sub': u'Kolejna strona wyników', 'more': loader,
            'kind': 'more'}


# ---------------------------------------------------------------- parsery kafelkow
def _from_video_renderer(r):
    vid = r.get('videoId')
    if not vid:
        return None
    title = _t(r.get('title')) or _t(r.get('headline'))
    channel = util.clean(_t(r.get('ownerText') or r.get('longBylineText') or r.get('shortBylineText')))
    views = _t(r.get('viewCountText') or r.get('shortViewCountText'))
    when = _t(r.get('publishedTimeText'))
    length = _t(r.get('lengthText'))
    if not views and r.get('videoInfo'):  # playlistVideoRenderer: "123 wyswietlenia • 2 lata temu"
        bits = [b.strip() for b in _t(r['videoInfo']).split(u'•')]
        views = bits[0] if bits else u''
        when = bits[1] if len(bits) > 1 else when
    live = False
    for ov in r.get('thumbnailOverlays') or []:
        tr = ov.get('thumbnailOverlayTimeStatusRenderer')
        if tr:
            if tr.get('style') == 'LIVE':
                live = True
            if not length:
                length = _t(tr.get('text'))
    for b in r.get('badges') or []:
        if (b.get('metadataBadgeRenderer') or {}).get('style') == 'BADGE_STYLE_TYPE_LIVE_NOW':
            live = True
    if not length and r.get('lengthSeconds'):
        length = util.fmt_duration(int(r['lengthSeconds']))
    if r.get('upcomingEventData') and not length:
        when, length = u'Zapowiedź', u'wkrótce'
    snippet = u''
    for m in r.get('detailedMetadataSnippets') or []:
        snippet = util.clean(_t(m.get('snippetText')))
        break
    if not snippet:
        snippet = util.clean(_t(r.get('descriptionSnippet')))
    return _video_item(vid, title, channel, views, when, length.strip() if length else u'', live, snippet)


def _from_lockup(lv):
    cid = lv.get('contentId')
    if not cid:
        return None
    ctype = lv.get('contentType', '')
    meta = (lv.get('metadata') or {}).get('lockupMetadataViewModel') or {}
    title = util.clean(_t(meta.get('title')))
    rows = []
    for row in (((meta.get('metadata') or {}).get('contentMetadataViewModel') or {})
                .get('metadataRows') or []):
        rows.append([_t(p.get('text')) for p in row.get('metadataParts') or [] if _t(p.get('text'))])
    image = lv.get('contentImage') or {}
    tvm = (image.get('thumbnailViewModel')
           or ((image.get('collectionThumbnailViewModel') or {}).get('primaryThumbnail') or {})
           .get('thumbnailViewModel') or {})
    badges = []
    for ov in tvm.get('overlays') or []:
        for b in (ov.get('thumbnailOverlayBadgeViewModel') or {}).get('thumbnailBadges') or []:
            txt = _t((b.get('thumbnailBadgeViewModel') or {}).get('text'))
            if txt:
                badges.append(txt)
    sources = (tvm.get('image') or {}).get('sources') or []
    img = _fix_url(sources[0].get('url')) if sources else u''
    if 'PLAYLIST' in ctype or cid[:2] in ('PL', 'RD', 'OL'):
        count = badges[0] if badges else u''
        owner = rows[0][0] if rows and rows[0] else u''
        return {'kind': 'playlist', 'id': cid, 'name': u'[Playlista] ' + title, 'sub': owner,
                'right': count, 'num': 0, 'info': u'Playlista\n' + owner, 'thumb': img}
    if 'VIDEO' not in ctype and len(cid) != 11:
        return None
    channel = rows[0][0] if rows and rows[0] else u''
    views = rows[1][0] if len(rows) > 1 and rows[1] else u''
    when = rows[1][1] if len(rows) > 1 and len(rows[1]) > 1 else u''
    length = u''
    live = False
    for b in badges:
        if _clock(b):
            length = b
        elif b.upper() in (u'NA ŻYWO', u'LIVE'):
            live = True
    return _video_item(cid, title, channel, views, when, length, live)


def _from_channel(r):
    cid = r.get('channelId')
    if not cid:
        return None
    title = util.clean(_t(r.get('title')))
    bits = [util.clean(_t(r.get('subscriberCountText'))), util.clean(_t(r.get('videoCountText')))]
    bits = [b for b in bits if b]
    thumbs = (r.get('thumbnail') or {}).get('thumbnails') or []
    img = _fix_url(thumbs[-1].get('url')) if thumbs else u''
    desc = util.clean(_t(r.get('descriptionSnippet')))
    return {'kind': 'channel', 'id': cid, 'name': u'[Kanał] ' + title, 'sub': u' • '.join(bits),
            'right': u'', 'num': 0, 'info': u'\n'.join(bits + ([u'', desc] if desc else [])),
            'thumb': img}


def _from_playlist(r):
    pid = r.get('playlistId')
    if not pid:
        return None
    title = util.clean(_t(r.get('title')))
    owner = util.clean(_t(r.get('longBylineText') or r.get('shortBylineText')))
    count = _t(r.get('videoCountText')) or _t(r.get('videoCount'))
    thumbs = ((r.get('thumbnails') or [{}])[0].get('thumbnails')) or []
    img = _fix_url(thumbs[-1].get('url')) if thumbs else u''
    return {'kind': 'playlist', 'id': pid, 'name': u'[Playlista] ' + title, 'sub': owner,
            'right': count, 'num': int(re.sub(r'\D', '', count) or 0) if count else 0,
            'info': u'Playlista\n' + owner, 'thumb': img}


def _from_tile(t):
    """Kafelek z interfejsu telewizyjnego (listy konta: subskrypcje, historia, playlisty)."""
    cid = t.get('contentId')
    ctype = t.get('contentType', '')
    if not cid:
        return None
    meta = (t.get('metadata') or {}).get('tileMetadataRenderer') or {}
    title = util.clean(_t(meta.get('title')))
    lines = []
    for ln in meta.get('lines') or []:
        parts = []
        for it in (ln.get('lineRenderer') or {}).get('items') or []:
            txt = util.clean(_t((it.get('lineItemRenderer') or {}).get('text')))
            if txt and txt != u'\u2022':
                parts.append(txt)
        lines.append(parts)
    header = (t.get('header') or {}).get('tileHeaderRenderer') or {}
    thumbs = (header.get('thumbnail') or {}).get('thumbnails') or []
    img = _fix_url(thumbs[-1].get('url')) if thumbs else u''
    length, live = u'', False
    for ov in header.get('thumbnailOverlays') or []:
        tr = ov.get('thumbnailOverlayTimeStatusRenderer')
        if tr:
            live = live or tr.get('style') == 'LIVE'
            length = _t(tr.get('text'))
    first = lines[0][0] if lines and lines[0] else u''
    if 'PLAYLIST' in ctype:
        pid = cid[2:] if cid.startswith('VL') else cid
        return {'kind': 'playlist', 'id': pid, 'name': u'[Playlista] ' + title, 'sub': first,
                'right': length, 'num': 0, 'info': u'Playlista\n' + first, 'thumb': img}
    if 'CHANNEL' in ctype:
        return {'kind': 'channel', 'id': cid, 'name': u'[Kanał] ' + title, 'sub': first,
                'right': u'', 'num': 0, 'info': first, 'thumb': img}
    if 'VIDEO' not in ctype and len(cid) != 11:
        return None
    views = lines[1][0] if len(lines) > 1 and lines[1] else u''
    when = lines[1][1] if len(lines) > 1 and len(lines[1]) > 1 else u''
    it = _video_item(cid, title, first, views, when, length, live)
    return it


def _token_of(renderer):
    ep = renderer.get('continuationEndpoint') or (
        (renderer.get('button') or {}).get('buttonRenderer') or {}).get('command') or {}
    return (ep.get('continuationCommand') or {}).get('token')


def _walk(node, out, tokens):
    if isinstance(node, list):
        for n in node:
            _walk(n, out, tokens)
        return
    if not isinstance(node, dict):
        return
    for key, val in node.items():
        if key in SKIP_KEYS:
            continue
        item = None
        if key in VIDEO_KEYS and isinstance(val, dict):
            item = _from_video_renderer(val)
        elif key == 'lockupViewModel' and isinstance(val, dict):
            item = _from_lockup(val)
        elif key == 'tileRenderer' and isinstance(val, dict):
            item = _from_tile(val)
        elif key == 'nextContinuationData' and isinstance(val, dict):
            if val.get('continuation'):
                tokens.append(val['continuation'])
            continue
        elif key in CHANNEL_KEYS and isinstance(val, dict):
            item = _from_channel(val)
        elif key in PLAYLIST_KEYS and isinstance(val, dict):
            item = _from_playlist(val)
        elif key == 'continuationItemRenderer' and isinstance(val, dict):
            tok = _token_of(val)
            if tok:
                tokens.append(tok)
            continue
        elif key in ('nextContinuationData', 'nextRadioContinuationData') and isinstance(val, dict):
            if val.get('continuation'):  # starszy zapis kolejnych stron: playlisty i kolejki odtwarzania
                tokens.append(val['continuation'])
            continue
        elif isinstance(val, (dict, list)):
            _walk(val, out, tokens)
            continue
        else:
            continue
        if item:
            out.append(item)


def extract(data):
    """Zwraca (lista pozycji bez duplikatow, token nastepnej strony albo None)."""
    out, tokens = [], []
    _walk(data, out, tokens)
    seen, items = set(), []
    for it in out:
        key = (it['kind'], it['id'])
        if key not in seen:
            seen.add(key)
            items.append(it)
    return items, (tokens[-1] if tokens else None)


# ---------------------------------------------------------------- listy
def _list(endpoint, body, tv=False):
    data = _post(endpoint, body, tv)
    try:
        items, token = extract(data)
    except Exception as e:
        ytlog.log('[YTDark] blad parsera:', e)
        raise YTError(u'Nie udało się odczytać odpowiedzi YouTube (zmienił się format).')
    ytlog.log('[YTDark] lista %s: %d pozycji, kolejna strona: %s' % (endpoint, len(items), 'tak' if token else 'nie'))
    if items and token:
        items.append(_more_item(lambda: _list(endpoint, {'continuation': token}, tv)))
    return items


def _follow(items, pages=4):
    """Doczytuje kolejne strony od razu (np. playlista 18 filmow oddana w dwoch partiach po 9),
    zeby uzytkownik nie musial szukac pozycji 'Wczytaj wiecej'. Przy bledzie zostawia to, co jest."""
    while pages > 0 and items and items[-1].get('kind') == 'more':
        more = items.pop()
        try:
            nxt = more['more']()
        except YTError as e:
            ytlog.log('[YTDark] doczytywanie strony: %s' % (e,))
            items.append(more)
            break
        seen = set((i['kind'], i['id']) for i in items if i.get('kind') != 'more')
        items += [i for i in nxt if i.get('kind') == 'more' or (i['kind'], i['id']) not in seen]
        pages -= 1
    return items


def search(query, params=None):
    return _list('search', {'query': query, 'params': params})


def home():
    """Strona glowna goscia; gdy YouTube jej nie poda - popularne z tego tygodnia."""
    try:
        items = _list('browse', {'browseId': 'FEwhat_to_watch'})
    except YTError:
        items = []
    return items or search(u'popularne', SP_WEEK_VIEWS_VIDEO)


def trending():
    try:
        items = _list('browse', {'browseId': 'FEtrending'})
        if items:
            return items
    except YTError:
        pass
    return home()


def _playlist_via_next(playlist_id):
    """Playlisty bez zwyklej strony (Mix 'RD...', czesc list automatycznych) otwiera sie jak kolejke odtwarzania."""
    body = {'playlistId': playlist_id}
    if (playlist_id.startswith('RD') and len(playlist_id) == 13
            and playlist_id[2:4] not in ('MM', 'EM', 'QM', 'CL', 'GM', 'AM')):  # 'RD' + id filmu, z ktorego startuje Mix
        body['videoId'] = playlist_id[2:]
    return _list('next', body)


def playlist_items(playlist_id, expand=True):
    """expand=True: doczytuje do kilku stron (dla playlist); kanaly maja setki filmow - tam zostaje 'Wczytaj wiecej'."""
    def done(items):
        return _follow(items) if expand else items
    if playlist_id.startswith('RD'):  # Mix: strona playlisty nie istnieje (zwraca blad 400)
        return done(_playlist_via_next(playlist_id))
    error = None
    try:
        items = _list('browse', {'browseId': 'VL' + playlist_id})
        if items:
            return done(items)
    except YTError as e:
        error = e
    try:  # zapas: ta sama playlista jako kolejka odtwarzania
        items = _playlist_via_next(playlist_id)
        if items:
            return done(items)
    except YTError as e:
        error = error or e
    if error:
        raise error
    return []


def channel_videos(channel_id):
    # playlista "przeslane" kanalu ma id kanalu z UC -> UU
    if channel_id.startswith('UC'):
        return playlist_items('UU' + channel_id[2:], expand=False)
    return _list('browse', {'browseId': channel_id, 'params': 'EgZ2aWRlb3PyBgQKAjoA'})


def categories():
    return [{'kind': 'category', 'id': q, 'name': name, 'sub': u'Najpopularniejsze w tym tygodniu'
             if sp == SP_WEEK_VIEWS_VIDEO else u'Transmisje na żywo', 'right': u'', 'num': 0,
             'info': name, 'q': q, 'sp': sp} for name, q, sp in CATEGORIES]


# ---------------------------------------------------------------- konto (tryb TV, po zalogowaniu)
def tv_browse(browse_id):
    return _list('browse', {'browseId': browse_id}, tv=True)


def tv_first(*browse_ids):
    """Pierwsza z kolejnych stron konta, ktora cos zwroci (YouTube bywa zmienny)."""
    last = None
    for bid in browse_ids:
        try:
            items = tv_browse(bid)
            if items:
                return items
        except YTError as e:
            last = e
    if last:
        raise last
    return []
