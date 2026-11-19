# -*- coding: utf-8 -*-
"""Wlasny dziennik pluginu: /tmp/ytdark.log (dziala w kazdym obrazie, bez wlaczania logow debug)."""
from __future__ import print_function
import time

PATH = '/tmp/ytdark.log'


def log(*args):
    try:
        print(*args)
    except Exception:
        pass
    try:
        line = u' '.join(a if isinstance(a, type(u'')) else u'%s' % (a,) for a in args)
        with open(PATH, 'ab') as fh:
            fh.write((u'%s %s\n' % (time.strftime('%H:%M:%S'), line)).encode('utf-8'))
        import os
        if os.path.getsize(PATH) > 200000:
            os.remove(PATH)
    except Exception:
        pass
