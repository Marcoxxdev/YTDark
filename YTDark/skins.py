# -*- coding: utf-8 -*-
"""Ciemna skorka w stylu YouTube (grafit + czerwien), bez plikow graficznych;
skaluje sie do HD/FHD/UHD. Prawy panel pokazuje miniature zaznaczonego filmu."""

BG = '#0f0f0f'
PANEL = '#161616'
BORDER = '#2b2b2b'
RED = '#e62117'
TXT = '#f1f1f1'
MUTED = '#aaaaaa'
SEL_BG = '#2a2a2a'
BAR = '#0b0b0b'
PH = '#1f1f1f'


class _B(object):
    def __init__(self, width):
        self.k = width / 1920.0
        self.W = int(round(1920 * self.k))
        self.H = int(round(1080 * self.k))

    def s(self, v):
        return int(round(v * self.k))

    def pos(self, x, y):
        return '%d,%d' % (self.s(x), self.s(y))

    def size(self, w, h):
        return '%d,%d' % (self.s(w), self.s(h))

    def font(self, n):
        return 'Regular;%d' % max(12, self.s(n))

    def rect(self, x, y, w, h, color, z=0):
        return '<eLabel position="%s" size="%s" backgroundColor="%s" zPosition="%d" />' % (
            self.pos(x, y), self.size(w, h), color, z)

    def text(self, t, x, y, w, h, n, color, halign='left', z=4):
        return ('<eLabel text="%s" position="%s" size="%s" font="%s" foregroundColor="%s" '
                'backgroundColor="%s" transparent="1" halign="%s" valign="center" zPosition="%d" />') % (
            t, self.pos(x, y), self.size(w, h), self.font(n), color, BG, halign, z)

    def label(self, name, x, y, w, h, n, color, halign='left', valign='center', bg=BG, extra=''):
        return ('<widget name="%s" position="%s" size="%s" font="%s" foregroundColor="%s" '
                'backgroundColor="%s" transparent="1" halign="%s" valign="%s" zPosition="4" %s/>') % (
            name, self.pos(x, y), self.size(w, h), self.font(n), color, bg, halign, valign, extra)

    def header(self, name_title, name_sub=None, name_mode=None):
        out = [self.rect(80, 34, 72, 50, RED, 3),
               self.text(u'\u25B6', 80, 34, 72, 50, 30, '#ffffff', 'center', 4),
               self.label(name_title, 176, 24, 1100, 56, 48, TXT, extra='noWrap="1" ')]
        if name_sub:
            out.append(self.label(name_sub, 176, 80, 1100, 34, 26, MUTED, extra='noWrap="1" '))
        if name_mode:
            out.append(self.label(name_mode, 1340, 44, 500, 40, 26, MUTED, 'right', extra='noWrap="1" '))
        out.append(self.rect(80, 128, 1760, 2, BORDER, 3))
        return out

    def buttons(self, specs):
        out = [self.rect(0, 1000, 1920, 80, BAR, 0), self.rect(0, 1000, 1920, 2, BORDER, 1)]
        for i, (name, color) in enumerate(specs):
            x = 80 + i * 440
            out.append(self.rect(x, 1028, 24, 24, color, 3))
            out.append(self.label(name, x + 40, 1020, 380, 40, 28, TXT))
        return out


def build(width):
    b = _B(width)
    L = ['<screen name="YTDark" position="0,0" size="%d,%d" title="YTDark" backgroundColor="%s" '
         'flags="wfNoBorder">' % (b.W, b.H, BG)]
    L += b.header('title', 'subtitle', 'mode')
    L.append(b.rect(80, 150, 1180, 830, BORDER, 1))
    L.append(b.rect(82, 152, 1176, 826, PANEL, 2))
    L.append('<widget name="list" position="%s" size="%s" foregroundColor="%s" backgroundColor="%s" '
             'foregroundColorSelected="%s" backgroundColorSelected="%s" scrollbarMode="showOnDemand" '
             'transparent="0" zPosition="4" />' % (b.pos(88, 158), b.size(1164, 814), TXT, PANEL, '#ffffff', SEL_BG))
    L.append(b.rect(1280, 150, 560, 830, BORDER, 1))
    L.append(b.rect(1282, 152, 556, 826, PANEL, 2))
    L.append(b.rect(1305, 176, 510, 287, PH, 3))
    L.append('<widget name="thumb" position="%s" size="%s" backgroundColor="%s" alphatest="on" '
             'transparent="1" zPosition="5" />' % (b.pos(1305, 176), b.size(510, 287), PH))
    L.append(b.label('sel', 1305, 480, 510, 124, 32, TXT, valign='top', bg=PANEL))
    L.append(b.rect(1305, 614, 510, 2, BORDER, 3))
    L.append(b.label('stat', 1305, 628, 510, 340, 25, MUTED, valign='top', bg=PANEL))
    L += b.buttons((('key_red', '#c0392b'), ('key_green', '#2e9e5b'),
                    ('key_yellow', '#d4a72c'), ('key_blue', '#2f6fbf')))
    L.append('</screen>')
    return '\n'.join(L)


def login(width):
    b = _B(width)
    L = ['<screen name="YTDarkLogin" position="0,0" size="%d,%d" title="Logowanie" backgroundColor="%s" '
         'flags="wfNoBorder">' % (b.W, b.H, BG)]
    L += b.header('title')
    L.append(b.rect(300, 200, 1320, 700, BORDER, 1))
    L.append(b.rect(302, 202, 1316, 696, PANEL, 2))
    L.append(b.label('line1', 340, 240, 1240, 60, 34, TXT, 'center', bg=PANEL))
    L.append(b.label('url', 340, 320, 1240, 90, 56, RED, 'center', bg=PANEL))
    L.append(b.label('line2', 340, 440, 1240, 60, 34, TXT, 'center', bg=PANEL))
    L.append(b.label('code', 340, 510, 1240, 140, 110, '#ffffff', 'center', bg=PANEL))
    L.append(b.label('status', 340, 720, 1240, 120, 30, MUTED, 'center', 'top', bg=PANEL))
    L += b.buttons((('key_red', '#c0392b'),))
    L.append('</screen>')
    return '\n'.join(L)


def player(width):
    """Pasek odtwarzania nakladany na obraz (przezroczysty ekran)."""
    b = _B(width)
    L = ['<screen name="YTPlayer" position="0,0" size="%d,%d" title="YTPlayer" backgroundColor="transparent" '
         'flags="wfNoBorder">' % (b.W, b.H)]
    L.append('<widget name="panel" position="%s" size="%s" backgroundColor="#e60f0f0f" zPosition="1" />'
             % (b.pos(0, 800), b.size(1920, 280)))
    L.append('<widget name="accent" position="%s" size="%s" backgroundColor="%s" zPosition="2" />'
             % (b.pos(0, 800), b.size(1920, 4), RED))
    def lab(name, x, y, w, h, n, color, halign='left'):
        return ('<widget name="%s" position="%s" size="%s" font="%s" foregroundColor="%s" '
                'backgroundColor="#0f0f0f" transparent="1" halign="%s" valign="center" zPosition="4" noWrap="1" />'
                % (name, b.pos(x, y), b.size(w, h), b.font(n), color, halign))
    L.append(lab('p_title', 80, 818, 1480, 54, 40, TXT))
    L.append(lab('p_sub', 80, 872, 1480, 36, 26, MUTED))
    L.append(lab('p_state', 1500, 818, 340, 54, 34, '#ffffff', 'right'))
    L.append('<widget name="progress" position="%s" size="%s" foregroundColor="%s" backgroundColor="#3a3a3a" '
             'borderWidth="0" zPosition="4" />' % (b.pos(80, 930), b.size(1760, 12), RED))
    L.append(lab('p_pos', 80, 950, 300, 38, 28, TXT))
    L.append(lab('p_msg', 560, 950, 800, 38, 28, '#ffd24a', 'center'))
    L.append(lab('p_len', 1540, 950, 300, 38, 28, TXT, 'right'))
    # kolorowe "pinezki" przyciskow pilota + opisy
    pins = (('red', '#e5382b', 80, 200), ('green', '#2e9e5b', 330, 260),
            ('yellow', '#f0b429', 640, 400), ('blue', '#2f7de1', 1080, 240))
    for key, color, x, w in pins:
        L.append(lab('k_' + key, x, 1004, 40, 46, 40, color, 'center'))
        L.append(lab('kt_' + key, x + 48, 1006, w - 48, 44, 26, TXT))
    L.append(lab('p_keys', 1340, 1006, 500, 44, 22, MUTED, 'right'))
    L.append('</screen>')
    return '\n'.join(L)


def search(width):
    """Ekran wyszukiwania: pole tekstowe, klawiatura ekranowa (lewo) i podpowiedzi (prawo)."""
    b = _B(width)
    L = ['<screen name="YTDarkSearch" position="0,0" size="%d,%d" title="Szukaj" backgroundColor="%s" '
         'flags="wfNoBorder">' % (b.W, b.H, BG)]
    L += b.header('title', 'subtitle', 'mode')
    # pole tekstowe
    L.append(b.rect(80, 150, 1760, 92, BORDER, 1))
    L.append(b.rect(82, 152, 1756, 88, PANEL, 2))
    L.append(b.label('input', 110, 158, 1700, 76, 46, TXT, bg=PANEL, extra='noWrap="1" '))
    # klawiatura ekranowa (kafelki rysuje plugin)
    L.append(b.rect(80, 262, 760, 452, BORDER, 1))
    L.append(b.rect(82, 264, 756, 448, PANEL, 2))
    L.append('<widget name="kb" position="%s" size="%s" foregroundColor="%s" backgroundColor="%s" '
             'foregroundColorSelected="%s" backgroundColorSelected="%s" scrollbarMode="showNever" '
             'transparent="0" zPosition="4" />' % (b.pos(88, 270), b.size(744, 432), TXT, PANEL, TXT, PANEL))
    L.append(b.label('help', 80, 730, 760, 250, 24, MUTED, valign='top'))
    # podpowiedzi
    L.append(b.rect(860, 262, 980, 718, BORDER, 1))
    L.append(b.rect(862, 264, 976, 714, PANEL, 2))
    L.append('<widget name="list" position="%s" size="%s" foregroundColor="%s" backgroundColor="%s" '
             'foregroundColorSelected="%s" backgroundColorSelected="%s" scrollbarMode="showNever" '
             'transparent="0" zPosition="4" />' % (b.pos(868, 270), b.size(964, 704), TXT, PANEL, '#ffffff', SEL_BG))
    L += b.buttons((('key_red', '#c0392b'), ('key_green', '#2e9e5b'),
                    ('key_yellow', '#d4a72c'), ('key_blue', '#2f6fbf')))
    L.append('</screen>')
    return '\n'.join(L)
