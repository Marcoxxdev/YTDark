# -*- coding: utf-8 -*-
"""Mini serwer HTTP tylko na 127.0.0.1: wystawia playlisty HLS zlozone przez plugin
(wybrana rozdzielczosc + sciezka dzwiekowa), zeby odtwarzacz dostal obraz Z dzwiekiem."""
from __future__ import print_function
import threading

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
except ImportError:  # python 2
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn

_files = {}
_order = []
_srv = None
_lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        text = _files.get(self.path.lstrip('/').split('?')[0])
        if text is None:
            self.send_response(404)
            self.end_headers()
            return
        data = text.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (IOError, OSError):
            pass  # odtwarzacz zamknal polaczenie - normalne

    def log_message(self, *args):
        pass


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass  # bez zrzutow wyjatkow do logu Enigmy


def put(name, text):
    """Zapisuje playliste i zwraca jej adres http://127.0.0.1:port/name."""
    global _srv
    with _lock:
        if _srv is None:
            _srv = _Server(('127.0.0.1', 0), _Handler)
            t = threading.Thread(target=_srv.serve_forever)
            t.daemon = True
            t.start()
        if name not in _files:
            _order.append(name)
        _files[name] = text
        while len(_order) > 60:
            _files.pop(_order.pop(0), None)
        return 'http://127.0.0.1:%d/%s' % (_srv.server_address[1], name)
