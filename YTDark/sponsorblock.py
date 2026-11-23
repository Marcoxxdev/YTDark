# -*- coding: utf-8 -*-
"""SponsorBlock - pomijanie sponsorow/autopromocji wewnatrz filmu (spolecznosciowa baza
sponsor.ajay.app). Zapytanie wysylane jest przez prefiks hasha ID filmu (prywatnosc)."""
from __future__ import print_function
import hashlib
import json

from . import net

API = 'https://sponsor.ajay.app/api/skipSegments/%s'
CATEGORIES = ['sponsor', 'selfpromo', 'interaction']


def segments(video_id):
    """Lista (start, koniec, kategoria) w sekundach; pusta lista przy braku danych/bledzie."""
    prefix = hashlib.sha256(video_id.encode('utf-8')).hexdigest()[:4]
    url = API % prefix + '?' + net.urlencode({
        'categories': json.dumps(CATEGORIES), 'actionTypes': json.dumps(['skip'])})
    try:
        status, data = net.get_json(url, timeout=6)
    except Exception:
        return []
    if status != 200 or not isinstance(data, list):
        return []
    out = []
    for entry in data:
        if entry.get('videoID') != video_id:
            continue
        for seg in entry.get('segments', []):
            sp = seg.get('segment') or []
            if len(sp) == 2 and sp[1] > sp[0]:
                out.append((float(sp[0]), float(sp[1]), seg.get('category', '')))
    return sorted(out)
