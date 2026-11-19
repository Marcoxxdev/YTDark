# -*- coding: utf-8 -*-
"""Warstwa HTTP: GET/POST, odpowiedzi JSON, awaryjne wylaczenie weryfikacji SSL."""
from __future__ import print_function
import json
import ssl

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from urllib.parse import urlencode
except ImportError:  # python 2
    from urllib2 import Request, urlopen, HTTPError
    from urllib import urlencode

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/120.0 Safari/537.36')


class YTError(Exception):
    """Blad z komunikatem po polsku, gotowym do pokazania w interfejsie."""


def _do(req, timeout, ctx=None):
    try:
        resp = urlopen(req, timeout=timeout, context=ctx) if ctx else urlopen(req, timeout=timeout)
        try:
            return resp.getcode(), resp.read().decode('utf-8', 'ignore')
        finally:
            resp.close()
    except HTTPError as e:
        try:
            body = e.read().decode('utf-8', 'ignore')
        except Exception:
            body = ''
        return e.code, body


def request(url, data=None, headers=None, timeout=15, as_json=False):
    """Zwraca (status, tekst). Rzuca YTError przy braku polaczenia.
    data: dict -> form-urlencoded, albo (gdy as_json) dict -> JSON."""
    hdrs = {'User-Agent': UA}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        if as_json:
            body = json.dumps(data).encode('utf-8')
            hdrs['Content-Type'] = 'application/json'
        else:
            body = urlencode(data).encode('utf-8')
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
    req = Request(url, data=body, headers=hdrs)
    try:
        return _do(req, timeout)
    except Exception:
        try:
            return _do(req, timeout, ssl._create_unverified_context())
        except Exception as e:
            raise YTError(u'Brak połączenia z internetem lub serwer nie odpowiada (%s).' % e)


def get_json(url, headers=None, timeout=15):
    status, text = request(url, headers=headers, timeout=timeout)
    try:
        return status, json.loads(text) if text else {}
    except ValueError:
        return status, {}


def post_json(url, data, headers=None, timeout=15, as_json=False):
    status, text = request(url, data=data, headers=headers, timeout=timeout, as_json=as_json)
    try:
        return status, json.loads(text) if text else {}
    except ValueError:
        return status, {}


def get_bytes(url, headers=None, timeout=12):
    """Pobiera surowe bajty (miniatury). Zwraca None przy bledzie."""
    hdrs = {'User-Agent': UA}
    hdrs.update(headers or {})
    req = Request(url, headers=hdrs)
    for ctx in (None, ssl._create_unverified_context()):
        try:
            resp = urlopen(req, timeout=timeout, context=ctx) if ctx else urlopen(req, timeout=timeout)
            try:
                return resp.read()
            finally:
                resp.close()
        except Exception:
            continue
    return None
