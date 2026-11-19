# -*- coding: utf-8 -*-
"""Logowanie do konta Google kodem wyswietlanym na ekranie (bez hasla na pilocie).

Dwa tryby:
 - 'own': oficjalny OAuth 2.0 dla urzadzen z WLASNYM projektem Google (client_id/secret w README),
 - 'tv' : tak jak aplikacja YouTube na telewizorze (youtube.com/activate) - bez konfiguracji.
          Nieoficjalne: YouTube moze to zmienic. Stale ponizej latwo poprawic."""
from __future__ import print_function
import time

from . import config, net
from .net import YTError

DEVICE_URL = 'https://oauth2.googleapis.com/device/code'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
REVOKE_URL = 'https://oauth2.googleapis.com/revoke'
SCOPE = 'https://www.googleapis.com/auth/youtube.readonly'
TV_DEVICE_URL = 'https://www.youtube.com/o/oauth2/device/code'
TV_TOKEN_URL = 'https://www.youtube.com/o/oauth2/token'
# Publiczne dane klienta YouTube na TV (te same sa w otwartych projektach, np. yt-dlp-youtube-oauth2).
TV_CLIENT_ID = '861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com'
TV_CLIENT_SECRET = 'SboVhoG9s0rNafixCSGGKXAT'
TV_SCOPE = 'http://gdata.youtube.com https://www.googleapis.com/auth/youtube-paid-content'
NOT_CONFIGURED = (u'Logowanie jest opcjonalne i wymaga własnych danych Google (client_id / client_secret).\n'
                  u'Przeglądanie i wyszukiwanie działa bez logowania.\n'
                  u'Szczegóły: README_PL.txt.')


def has_credentials():
    return bool(config.get('client_id') and config.get('client_secret'))


def is_logged_in():
    return bool((config.get('tokens') or {}).get('refresh_token'))


def mode():
    """'tv' albo 'own' (tryb zapisany przy logowaniu)."""
    return (config.get('tokens') or {}).get('mode') or 'own'


def is_tv():
    return is_logged_in() and mode() == 'tv'


def _uuid():
    import uuid
    return uuid.uuid4().hex


def start_device_flow(login_mode='own'):
    """Zwraca dict: device_code, user_code, verification_url, expires_in, interval."""
    if login_mode == 'tv':
        status, data = net.post_json(TV_DEVICE_URL, {
            'client_id': TV_CLIENT_ID, 'scope': TV_SCOPE, 'device_id': _uuid(), 'model_name': 'ytlr::'})
        if status != 200 or 'device_code' not in data:
            raise YTError(u'YouTube odrzucił prośbę o kod (%s). Tryb TV mógł zostać zmieniony.'
                          % (data.get('error', status) if isinstance(data, dict) else status))
        data.setdefault('verification_url', 'https://www.youtube.com/activate')
        return data
    if not has_credentials():
        raise YTError(NOT_CONFIGURED)
    status, data = net.post_json(DEVICE_URL, {'client_id': config.get('client_id'), 'scope': SCOPE})
    if status != 200 or 'device_code' not in data:
        raise YTError(u'Google odrzucił prośbę o kod (%s). Sprawdź client_id i typ klienta '
                      u'(\"Telewizory i urządzenia z ograniczonym wejściem\").' % data.get('error', status))
    return data


def poll(device_code, login_mode='own'):
    """Jednorazowe sprawdzenie. Zwraca: 'ok' | 'pending' | 'slow' | 'denied' | 'expired' | 'error'."""
    if login_mode == 'tv':
        status, data = net.post_json(TV_TOKEN_URL, {
            'client_id': TV_CLIENT_ID, 'client_secret': TV_CLIENT_SECRET, 'code': device_code,
            'grant_type': 'http://oauth.net/grant_type/device/1.0'})
    else:
        status, data = net.post_json(TOKEN_URL, {
            'client_id': config.get('client_id'),
            'client_secret': config.get('client_secret'),
            'device_code': device_code,
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        })
    if status == 200 and data.get('access_token'):
        _store(data, login_mode)
        return 'ok'
    err = data.get('error', '')
    return {'authorization_pending': 'pending', 'slow_down': 'slow',
            'access_denied': 'denied', 'expired_token': 'expired'}.get(err, 'error')


def _store(data, login_mode=None):
    tokens = dict(config.get('tokens') or {})
    tokens['access_token'] = data['access_token']
    tokens['expires_at'] = time.time() + int(data.get('expires_in', 3600)) - 60
    if data.get('refresh_token'):
        tokens['refresh_token'] = data['refresh_token']
    if login_mode:
        tokens['mode'] = login_mode
    config.put('tokens', tokens)


def access_token():
    """Zwraca wazny access_token (odswieza w razie potrzeby) albo None, gdy niezalogowany."""
    tokens = config.get('tokens') or {}
    if not tokens.get('refresh_token'):
        return None
    if tokens.get('access_token') and tokens.get('expires_at', 0) > time.time():
        return tokens['access_token']
    if mode() == 'tv':
        status, data = net.post_json(TV_TOKEN_URL, {
            'client_id': TV_CLIENT_ID, 'client_secret': TV_CLIENT_SECRET,
            'refresh_token': tokens['refresh_token'], 'grant_type': 'refresh_token'})
    else:
        status, data = net.post_json(TOKEN_URL, {
            'client_id': config.get('client_id'),
            'client_secret': config.get('client_secret'),
            'refresh_token': tokens['refresh_token'],
            'grant_type': 'refresh_token',
        })
    if status == 200 and data.get('access_token'):
        _store(data)
        return data['access_token']
    if data.get('error') == 'invalid_grant':
        config.put('tokens', {})  # dostep cofniety - wymagane ponowne logowanie
        raise YTError(u'Sesja wygasła. Zaloguj się ponownie (Ustawienia).')
    raise YTError(u'Nie udało się odświeżyć logowania (%s).' % (data.get('error') or status))


def logout():
    tokens = config.get('tokens') or {}
    tok = tokens.get('refresh_token') or tokens.get('access_token')
    config.put('tokens', {})
    if tok:
        try:
            net.post_json(REVOKE_URL, {'token': tok}, timeout=8)
        except Exception:
            pass
