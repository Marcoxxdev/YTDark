# -*- coding: utf-8 -*-
"""Pobieranie bezposredniego adresu strumienia filmu (bez odtwarzacza WWW = bez reklam).

Kolejnosc prob:
 1. yt-dlp / youtube_dl, jesli zainstalowany na odbiorniku (najlepiej utrzymywany sposob),
 2. wbudowany klient 'ANDROID_VR' (youtubei). To jest czesc, ktora YouTube zmienia
    najczesciej - przy zmianie wystarczy poprawic stale ponizej."""
from __future__ import print_function

import os
import re
import threading
import time

try:
    from urllib.parse import urljoin
except ImportError:  # python 2
    from urlparse import urljoin

from . import auth, config, localsrv, net, ytdlp_setup, ytlog
from .net import YTError

WATCH = 'https://www.youtube.com/watch?v='
PLAYER_URL = 'https://www.youtube.com/youtubei/v1/player?prettyPrint=false'
VR_VERSION = '1.60.19'
VR_UA = ('com.google.android.apps.youtube.vr.oculus/%s (Linux; U; Android 12L; eureka-user '
         'Build/SQ3A.220605.009.A1) gzip' % VR_VERSION)


def _label(height, kind):
    return (u'%dp' % height if height else u'auto') + (u' (HLS)' if kind == 'hls' else u'')


def _streams_from_info(info, video_id):
    out, seen = [], set()
    for f in info.get('formats', []):
        url = f.get('url')
        if not url:
            continue
        has_v = f.get('vcodec') not in (None, 'none')
        has_a = f.get('acodec') not in (None, 'none')
        if not (has_v and has_a):  # sam obraz albo sam dzwiek = brak dzwieku / brak obrazu
            continue
        hls = 'm3u8' in (f.get('protocol') or '')
        kind = 'hls' if hls else 'mp4'
        h = f.get('height') or 0
        if (h, kind) in seen:  # yt-dlp daje duplikaty tej samej rozdzielczosci
            continue
        seen.add((h, kind))
        ua = (f.get('http_headers') or {}).get('User-Agent') or (info.get('http_headers') or {}).get('User-Agent')
        out.append({'name': _label(h, kind), 'url': url, 'height': h, 'kind': kind, 'ua': ua})
    masters = []
    for f in info.get('formats', []):
        m = f.get('manifest_url')
        if m and 'm3u8' in (f.get('protocol') or '') and m not in [x[0] for x in masters]:
            masters.append((m, (f.get('http_headers') or {}).get('User-Agent')
                            or (info.get('http_headers') or {}).get('User-Agent')))
    for m, ua in masters[:2]:
        for st in hls_variants(m, ua, video_id):
            key = (st['height'], st['kind'])
            if key not in seen or not st['height']:
                if not st['height'] and any(o['url'] == st['url'] for o in out):
                    continue
                seen.add(key)
                out.append(st)
    return out


last_seconds = [0.0]   # czas ostatniego (nie z pamieci podrecznej) pobrania strumienia - do decyzji o podgladzie w tle
_ANSI = re.compile(r'\x1b\[[0-9;]*m')


class _YtdlpLog(object):
    """Logger przekazywany do yt-dlp: do ytdark.log trafia kazdy krok z czasem od startu - widac, co trwa."""

    def __init__(self):
        self.t0 = time.time()

    def _put(self, prefix, msg):
        msg = _ANSI.sub('', u'%s' % (msg,)).strip()
        if msg:
            ytlog.log('[YTDark] yt-dlp +%.1fs %s%s' % (time.time() - self.t0, prefix, msg[:170]))

    def debug(self, msg):
        if not (u'%s' % (msg,)).startswith('[debug]'):
            self._put('', msg)

    def info(self, msg):
        self._put('', msg)

    def warning(self, msg):
        self._put('! ', msg)

    def error(self, msg):
        self._put('!! ', msg)


YTDLP_SLOW = 20.0              # s: jesli yt-dlp trwal dluzej, najpierw probujemy szybkich wlasnych klientow
_innertube_blocked_until = [0.0]   # po blokadzie "bota" przez jakis czas nie tracimy czasu na wlasnych klientow
_ytdlp_error = [u'']   # tekst ostatniego bledu yt-dlp (do rozpoznania ograniczenia wiekowego)


def _ytdlp_cache_dir():
    """Stala, zapisywalna pamiec podreczna yt-dlp (wyniki rozwiazywania skryptow JS odtwarzacza).
    Plugin dziala w procesie Enigmy, gdzie domyslny katalog (~/.cache) bywa niezapisywalny."""
    for path in ('/etc/enigma2/ytdlp_cache', '/tmp/ytdlp_cache'):
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
            if os.access(path, os.W_OK):
                return path
        except Exception:
            continue
    return None


def via_ytdlp(video_id):
    mod = None
    for name in ('yt_dlp', 'youtube_dl'):
        try:
            mod = __import__(name)
            break
        except Exception:
            continue
    if mod is None:
        return None
    _ytdlp_error[0] = u''
    opts = {'quiet': True, 'skip_download': True, 'noplaylist': True, 'logger': _YtdlpLog(),
            'socket_timeout': 10, 'retries': 1, 'extractor_retries': 1}
    cache = _ytdlp_cache_dir()
    if cache:
        opts['cachedir'] = cache
    t0 = time.time()
    try:
        with mod.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(WATCH + video_id, download=False)
        out = _streams_from_info(info, video_id)
    except Exception as e:
        _ytdlp_error[0] = u'%s' % (e,)
        ytlog.log('[YTDark] yt-dlp blad: %s' % (e,))
        return None
    ytlog.log('[YTDark] yt-dlp: %.1f s, %d strumieni z dzwiekiem' % (time.time() - t0, len(out)))
    return out or None


# Klienci youtubei po kolei: YouTube sprawdza "czy to bot" osobno dla kazdego klienta,
# wiec to, co odrzuca jeden, bywa przepuszczone przez inny.
CLIENTS = [
    {'name': 'ANDROID_VR', 'id': '28', 'version': VR_VERSION, 'ua': VR_UA,
     'extra': {'deviceMake': 'Oculus', 'deviceModel': 'Quest 3', 'osName': 'Android',
               'osVersion': '12L', 'androidSdkVersion': 32}},
    {'name': 'IOS', 'id': '5', 'version': '20.10.4',
     'ua': 'com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)',
     'extra': {'deviceMake': 'Apple', 'deviceModel': 'iPhone16,2', 'osName': 'iPhone',
               'osVersion': '18.3.2.22D82'}},
    {'name': 'TVHTML5_SIMPLY_EMBEDDED_PLAYER', 'id': '85', 'version': '2.0', 'ua': None,
     'embed': True, 'extra': {}},
    {'name': 'WEB_EMBEDDED_PLAYER', 'id': '56', 'version': '1.20250924.01.00', 'ua': None,
     'embed': True, 'extra': {}},
    {'name': 'TVHTML5', 'id': '7', 'version': '7.20250923.13.00',
     'ua': 'Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version', 'auth': True, 'extra': {}},
]


def _try_client(video_id, c):
    client = {'clientName': c['name'], 'clientVersion': c['version'], 'hl': 'pl', 'gl': 'PL'}
    client.update(c['extra'])
    ctx = {'client': client}
    if c.get('embed'):
        ctx['thirdParty'] = {'embedUrl': 'https://www.youtube.com/'}
    body = {'videoId': video_id, 'contentCheckOk': True, 'racyCheckOk': True, 'context': ctx}
    headers = {'X-YouTube-Client-Name': c['id'], 'X-YouTube-Client-Version': c['version'],
               'Origin': 'https://www.youtube.com'}
    if c['ua']:
        headers['User-Agent'] = c['ua']
    if c.get('auth') and auth.is_tv():
        try:
            headers['Authorization'] = 'Bearer ' + auth.access_token()
        except Exception:
            pass
    status, data = net.post_json(PLAYER_URL, body, headers=headers, as_json=True)
    play = (data or {}).get('playabilityStatus', {})
    if play.get('status') not in (None, 'OK'):
        raise YTError(play.get('reason') or play.get('status') or u'brak odpowiedzi')
    sd = data.get('streamingData', {})
    out = []
    for f in sd.get('formats', []):  # polaczone audio+wideo (progresywne)
        if f.get('url'):
            h = f.get('height') or 0
            out.append({'name': _label(h, 'mp4'), 'url': f['url'], 'height': h, 'kind': 'mp4',
                        'ua': c['ua']})
    if sd.get('hlsManifestUrl'):
        out.append({'name': u'auto (HLS)', 'url': sd['hlsManifestUrl'], 'height': 0, 'kind': 'hls',
                    'ua': c['ua']})
    return out or None


AGE_MARKERS = ('confirm your age', 'swój wiek', 'wiekow', 'inappropriate for some', 'nieodpowiedni dla niektórych',
               'age-restricted')


def is_age_restricted(text):
    low = (text or u'').lower()
    return any(m in low for m in AGE_MARKERS)


def age_help():
    if auth.is_logged_in():
        return (u'Ten film ma ograniczenie wiekowe, a YouTube nie pozwala go odtworzyć na tym koncie.\n'
                u'Konto musi mieć potwierdzony wiek w YouTube.')
    return (u'Ten film ma ograniczenie wiekowe i wymaga zalogowanego konta.\n'
            u'Zaloguj się w Ustawieniach (kodem) - konto musi mieć potwierdzony wiek w YouTube.')


BOT_HELP = (u'YouTube blokuje to połączenie jako „bota” - to blokada adresu IP, nie błąd pluginu.\n'
            u'Spróbuj: wyłączyć VPN/proxy/filtr DNS, zrestartować router (nowy adres IP), '
            u'zainstalować yt-dlp na odbiorniku albo spróbować za kilka godzin.')


def hls_variants(master_url, ua, video_id):
    """Z glownej playlisty HLS robi liste rozdzielczosci, zawsze Z dzwiekiem:
    - warianty z dzwiekiem w srodku (mp4a w CODECS) -> bezposredni adres wariantu,
    - dzwiek w osobnej sciezce (typowe dla YouTube) -> lokalna playlista (obraz + audio).
    Na koncu zawsze 'auto (HLS)' = oryginalna playlista."""
    out = []
    try:
        status, text = net.request(master_url, headers={'User-Agent': ua} if ua else None, timeout=10)
    except Exception as e:
        ytlog.log('[YTDark] playlista HLS: %s' % (e,))
        return []
    if status != 200 or '#EXT-X-STREAM-INF' not in (text or ''):
        ytlog.log('[YTDark] playlista HLS: brak wariantow (kod %s)' % status)
        return []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    media = [l for l in lines if l.startswith('#EXT-X-MEDIA') and 'TYPE=AUDIO' in l]
    variants = []
    for i, line in enumerate(lines):
        if not line.startswith('#EXT-X-STREAM-INF'):
            continue
        url = next((x for x in lines[i + 1:] if not x.startswith('#')), None)
        m = re.search(r'RESOLUTION=\d+x(\d+)', line)
        if not url or not m:
            continue
        cod = re.search(r'CODECS="([^"]*)"', line)
        grp = re.search(r'AUDIO="([^"]*)"', line)
        variants.append({'h': int(m.group(1)), 'line': line, 'url': urljoin(master_url, url),
                         'codecs': cod.group(1) if cod else u'',
                         'group': grp.group(1) if grp else None})
    seen = set()
    for want_avc in (True, False):
        for v in variants:
            if v['h'] in seen or (want_avc and 'avc1' not in v['codecs']):
                continue
            if v['group']:  # dzwiek osobno -> skladamy wlasna playliste
                mine = [re.sub(r'URI="([^"]+)"', lambda mm: 'URI="%s"' % urljoin(master_url, mm.group(1)), l)
                        for l in media if 'GROUP-ID="%s"' % v['group'] in l]
                if not mine:
                    continue
                vline = re.sub(r',SUBTITLES="[^"]*"', '', v['line'])
                body = u'\n'.join([u'#EXTM3U', u'#EXT-X-INDEPENDENT-SEGMENTS'] + mine + [vline, v['url']]) + u'\n'
                url = localsrv.put('%s_%d.m3u8' % (video_id, v['h']), body)
                out.append({'name': _label(v['h'], 'hls'), 'url': url, 'height': v['h'], 'kind': 'hls',
                            'ua': None})
            elif re.search(r'mp4a|opus|ac-3|ec-3', v['codecs']):  # dzwiek w srodku
                out.append({'name': _label(v['h'], 'hls'), 'url': v['url'], 'height': v['h'],
                            'kind': 'hls', 'ua': ua})
            else:
                continue  # sam obraz - pomijamy
            seen.add(v['h'])
    out.append({'name': u'auto (HLS)', 'url': master_url, 'height': 0, 'kind': 'hls', 'ua': ua})
    return out


def via_innertube(video_id):
    reasons = []
    clients = CLIENTS[-1:] + CLIENTS[:-1] if auth.is_tv() else CLIENTS  # zalogowany klient TV najpierw
    for c in clients:
        try:
            streams = _try_client(video_id, c)
        except Exception as e:
            ytlog.log('[YTDark] klient %s: %s' % (c['name'], e))
            reasons.append(u'%s' % (e,))
            continue
        if streams:
            for st in list(streams):
                if st['kind'] == 'hls' and not st['height']:
                    streams.remove(st)
                    streams += hls_variants(st['url'], st.get('ua'), video_id) or [st]
            return streams
        reasons.append(u'brak strumieni')
    text = u' | '.join(reasons)
    low = text.lower()
    if is_age_restricted(text):
        raise YTError(age_help())
    if 'bot' in low or 'sign in' in low or 'zaloguj' in low:
        raise YTError(BOT_HELP)
    raise YTError(u'YouTube nie udostępnia tego filmu: %s' % (reasons[0] if reasons else u'?'))


CACHE_TTL = 20 * 60   # adresy strumieni zyja godzinami; 20 min z zapasem
CACHE_MAX = 12        # ile filmow trzymamy (lokalne playlisty HLS tez sa ograniczone w localsrv)
_cache = {}
_locks = {}


def is_cached(video_id):
    hit = _cache.get(video_id)
    return bool(hit and time.time() - hit[0] < CACHE_TTL)


def _method_order():
    methods = ('ytdlp', 'innertube')
    mode = config.get('resolver_mode')  # reczny wybor w Ustawieniach: 'ytdlp' / 'own'; inaczej automat
    if mode == 'ytdlp':
        return ['ytdlp', 'innertube']
    if mode == 'own':
        return ['innertube', 'ytdlp']
    # zapamietujemy, ktora metoda dzialala ostatnio, i nia zaczynamy (nie tracimy czasu na odrzucane)
    first = config.get('resolver_first')
    if first not in methods:
        first = 'ytdlp' if ytdlp_setup.installed() else 'innertube'
    # yt-dlp potrafi liczyc kilkadziesiat sekund (rozwiazywanie skryptow JS YouTube na slabym procesorze) -
    # wtedy wlasni klienci (ok. 1-3 s) idą pierwsi, a yt-dlp zostaje zapasem (np. dla filmow z ograniczeniem wieku)
    if (float(config.get('ytdlp_secs') or 0) > YTDLP_SLOW and time.time() > _innertube_blocked_until[0]):
        first = 'innertube'
    return [first] + [m for m in methods if m != first]


def _resolve_uncached(video_id):
    methods = {'ytdlp': via_ytdlp, 'innertube': via_innertube}
    order = _method_order()
    last_error = None
    for name in order:
        t0 = time.time()
        try:
            streams = methods[name](video_id)
        except YTError as e:
            last_error = e
            ytlog.log('[YTDark] %s: %s (%.1f s)' % (name, e, time.time() - t0))
            if name == 'innertube' and str(e).startswith(BOT_HELP[:30]):
                _innertube_blocked_until[0] = time.time() + 600  # 10 min bez prob wlasnych klientow
            continue
        if streams:
            ytlog.log('[YTDark] resolve %s przez %s: %.1f s' % (video_id, name, time.time() - t0))
            last_seconds[0] = time.time() - t0
            if name == 'ytdlp':  # zapamietujemy czas yt-dlp (tez po restarcie), zeby wiedziec, czy jest wolny
                old = float(config.get('ytdlp_secs') or 0)
                if abs(last_seconds[0] - old) > 5:
                    config.put('ytdlp_secs', round(last_seconds[0], 1))
            if config.get('resolver_first') != name:
                config.put('resolver_first', name)
            streams.sort(key=lambda s: (-s['height'], s['kind']))
            ytlog.log('[YTDark] strumienie: %s' % ', '.join(s['name'] for s in streams))
            return streams
    if is_age_restricted(_ytdlp_error[0]):  # yt-dlp rozpoznal ograniczenie wiekowe, wlasne klienty nie
        raise YTError(age_help())
    if last_error:
        raise last_error
    raise YTError(u'Nie udało się pobrać adresu strumienia (YouTube zmienił zabezpieczenia).\n'
                  u'Zainstaluj yt-dlp na odbiorniku lub zaktualizuj plugin.')


def resolve(video_id):
    """Lista strumieni (od najwyzszej rozdzielczosci). Wynik trafia do pamieci podrecznej, a rownolegle
    wywolania dla tego samego filmu (np. podglad w tle + klikniecie OK) czekaja na jedno wspolne pobieranie."""
    def copies(streams):
        return [dict(s) for s in streams]
    hit = _cache.get(video_id)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return copies(hit[1])
    lock = _locks.setdefault(video_id, threading.Lock())
    with lock:
        hit = _cache.get(video_id)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return copies(hit[1])
        streams = _resolve_uncached(video_id)
        _cache[video_id] = (time.time(), streams)
        while len(_cache) > CACHE_MAX:
            del _cache[min(_cache, key=lambda k: _cache[k][0])]
    _locks.pop(video_id, None)
    return copies(streams)


def pick(streams, max_height):
    """Najlepszy strumien nie wyzszy niz max_height; 0 = brak limitu (zwraca None => pytaj)."""
    if not max_height:
        return None
    ok = [s for s in streams if s['height'] and s['height'] <= max_height]
    if ok:
        return ok[0]
    return streams[-1] if streams else None
