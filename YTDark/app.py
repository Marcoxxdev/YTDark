# -*- coding: utf-8 -*-
"""YTDark - klient YouTube dla Enigma2: logowanie do konta Google (OAuth dla urzadzen),
listy z oficjalnego API, odtwarzanie strumienia bezposredniego (bez reklam)
i pomijanie sponsorow w filmach (SponsorBlock)."""
from __future__ import print_function

import os

import time

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.Pixmap import Pixmap
from Components.Slider import Slider
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.Screen import Screen
from Screens.VirtualKeyBoard import VirtualKeyBoard
from enigma import (
    RT_HALIGN_CENTER,
    RT_HALIGN_LEFT,
    RT_HALIGN_RIGHT,
    RT_VALIGN_CENTER,
    eListboxPythonMultiContent,
    ePicLoad,
    eServiceReference,
    eTimer,
    getDesktop,
    gFont,
)
try:
    from enigma import eActionMap
except Exception:
    eActionMap = None
try:
    from enigma import getPrevAsciiCode
except Exception:
    getPrevAsciiCode = None
try:
    from Tools.Notifications import AddPopup
except Exception:
    AddPopup = None
from twisted.internet import threads

try:
    from Components.ServiceEventTracker import ServiceEventTracker
    from enigma import iPlayableService
except Exception:
    ServiceEventTracker = None

from . import ytlog
from . import __version__, api, auth, config, suggest, update, ytdlp_setup, innertube, resolver, skins, source, sponsorblock, thumbs, util
from .net import YTError

WIDTH = getDesktop(0).size().width()
K = WIDTH / 1920.0


def S(v):
    return int(round(v * K))


SORT_LABELS = {
    'orig': u'kolejność YouTube',
    'az': u'A → Z',
    'za': u'Z → A',
    'count': u'czas / liczba ↓',
}
C_TEXT, C_SEL, C_MUTED, C_SUBSEL, C_RED, C_ACCENT = 0xf1f1f1, 0xffffff, 0xaaaaaa, 0xcccccc, 0xff4e45, 0xe62117
QUALITIES = [360, 480, 720, 1080, 0]
REGIONS = ['PL', 'US', 'GB', 'DE', 'FR']


def err_text(err):
    """Komunikat bledu do pokazania w UI (nasze bledy po polsku, reszta z prefiksem)."""
    value = getattr(err, 'value', err)
    try:
        txt = u'%s' % (value,)
    except Exception:
        txt = repr(value)
    if not isinstance(value, YTError):
        txt = u'Błąd: ' + (txt or u'nieznany')
    return txt


def connect_timer(timer, fn, holder):
    """Zgodne z OpenATV/OpenPLi (callback) i DreamOS (timeout.connect)."""
    try:
        timer.callback.append(fn)
    except AttributeError:
        holder.append(timer.timeout.connect(fn))


# ================================================================== lista
ROW_H = 88


class HubMenu(MenuList):
    def __init__(self):
        MenuList.__init__(self, [], False, eListboxPythonMultiContent)
        self.l.setItemHeight(S(ROW_H))
        self.l.setFont(0, gFont('Regular', S(32)))
        self.l.setFont(1, gFont('Regular', S(25)))
        self.l.setFont(2, gFont('Regular', S(26)))


def make_entry(item, width):
    """Dwa wiersze jak w YouTube: tytul, pod nim kanal / wyswietlenia / data; czas po prawej."""
    sub = item.get('sub')
    if sub is None:
        sub = u' \u2022 '.join(l for l in (item.get('info') or u'').split(u'\n') if l)
    right = item.get('right') or u''
    live = bool(item.get('live'))
    left = S(26)
    text_w = width - left - S(190)
    flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
    return [
        item,
        MultiContentEntryText(pos=(0, S(8)), size=(S(6), S(ROW_H - 16)), font=0, flags=flags,
                              text=u'', backcolor_sel=C_ACCENT),
        MultiContentEntryText(pos=(left, S(8)), size=(text_w, S(40)), font=0, flags=flags,
                              text=item['name'], color=C_TEXT, color_sel=C_SEL),
        MultiContentEntryText(pos=(left, S(48)), size=(text_w, S(32)), font=1, flags=flags,
                              text=sub, color=C_MUTED, color_sel=C_SUBSEL),
        MultiContentEntryText(pos=(width - S(170), S(8)), size=(S(150), S(40)), font=2,
                              flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text=right,
                              color=C_RED if live else C_MUTED, color_sel=C_RED if live else C_TEXT),
    ]


class HubList(Screen):
    """Uniwersalna lista (menu, kategorie, filmy...) z sortowaniem, filtrem i 'wczytaj wiecej'."""

    def __init__(self, session, title, subtitle, items=None, loader=None, on_ok=None,
                 sorts=('orig',), sort='orig', favmode=False, green_label=u'Otwórz'):
        Screen.__init__(self, session)
        self.skin = skins.build(WIDTH)
        self.on_ok = on_ok
        self.loader = loader
        self.sorts = list(sorts)
        self.sort = sort if sort in self.sorts else self.sorts[0]
        self.favmode = favmode
        self.green_label = green_label
        self.all, self.view = [], []
        self.flt = u''
        self.alive = True
        self.loading = False
        self.preset = items
        self['title'] = Label(title)
        self['subtitle'] = Label(subtitle)
        self['sel'] = Label('')
        self['stat'] = Label('')
        self['mode'] = Label(u'\u25CF Zalogowano' if auth.is_logged_in() else u'\u25CF Tryb go\u015bcia')
        self['thumb'] = Pixmap()
        self.want = None
        self.pic_holder = []
        self.thumb_timer = eTimer()
        connect_timer(self.thumb_timer, self.load_thumb, self.pic_holder)
        self.picload = ePicLoad()
        try:
            self.picload.PictureData.get().append(self.pic_ready)
        except AttributeError:
            self.pic_holder.append(self.picload.PictureData.connect(self.pic_ready))
        self.onClose.append(self.thumb_timer.stop)
        self['key_red'] = Label(u'Wstecz')
        self['key_green'] = Label(green_label)
        self['key_yellow'] = Label('')
        self['key_blue'] = Label(u'Filtr')
        self['list'] = HubMenu()
        self['actions'] = ActionMap(
            ['OkCancelActions', 'ColorActions', 'DirectionActions'],
            {'ok': self.key_ok, 'cancel': self.exit, 'red': self.exit,
             'green': self.key_green, 'yellow': self.cycle_sort, 'blue': self.ask_filter,
             'up': self.up, 'down': self.down, 'left': self.page_up, 'right': self.page_down}, -1)
        self.onLayoutFinish.append(self.start)

    # ---------------------------------------------------------- ladowanie
    def start(self):
        if self.preset is not None:
            self.set_items(self.preset)
            return
        self['sel'].setText(u'Pobieranie listy…')
        self.run(self.loader, self.loaded)

    def run(self, fn, ok_cb):
        self.loading = True
        d = threads.deferToThread(fn)
        d.addCallback(ok_cb)
        d.addErrback(self.failed)

    def loaded(self, items):
        self.loading = False
        if self.alive:
            self.set_items(items)

    def failed(self, err):
        self.loading = False
        if not self.alive:
            return
        ytlog.log('[YTDark] blad listy:', err)
        self['sel'].setText(err_text(err))

    def set_items(self, items, keep=False):
        """keep=True: po odswiezeniu kursor zostaje na tej samej pozycji (np. w Ustawieniach)."""
        self.all = list(items)
        if 'count' in self.sorts and not any(i.get('num') for i in self.all):
            self.sorts.remove('count')
            if self.sort == 'count':
                self.sort = self.sorts[0]
        if not self.all:
            self['sel'].setText(u'Ta lista jest pusta.')
        self.refresh(keep)

    def load_more(self, item):
        if self.loading:
            return
        self['sel'].setText(u'Wczytywanie kolejnej strony…')

        def got(new):
            self.loading = False
            if not self.alive:
                return
            keep = len([i for i in self.view if not i.get('more')])
            self.all = [i for i in self.all if i is not item] + list(new)
            self.refresh()
            if self.sort == 'orig' and not self.flt:
                self['list'].moveToIndex(min(keep, max(0, len(self.view) - 1)))
                self.sel_changed()
        self.run(item['more'], got)

    # --------------------------------------------------------- widok listy
    def refresh(self, keep=False):
        index = self['list'].getSelectionIndex() if keep else 0
        items = util.filter_items(self.all, self.flt)
        self.view = util.sort_items(items, self.sort)
        width = S(1150)
        self['list'].l.setList([make_entry(i, width) for i in self.view])
        self['list'].moveToIndex(max(0, min(index or 0, len(self.view) - 1)))
        self['key_yellow'].setText(
            (u'Sortuj: ' + SORT_LABELS[self.sort]) if len(self.sorts) > 1 else u'')
        self.sel_changed()

    def queue_after(self, item):
        """Kolejne filmy z aktualnie wyswietlanej listy (dla autoodtwarzania)."""
        vids = [i for i in self.view if i.get('kind') == 'video']
        for n, i in enumerate(vids):
            if i.get('id') == item.get('id'):
                return vids[n + 1:]
        return []

    def select_id(self, vid):
        for n, i in enumerate(self.view):
            if i.get('kind') == 'video' and i.get('id') == vid:
                self['list'].moveToIndex(n)
                return

    def current(self):
        cur = self['list'].getCurrent()
        return cur[0] if cur else None

    def is_video(self, item):
        return self.favmode and item is not None and item.get('kind') == 'video'

    def sel_changed(self):
        item = self.current()
        if item is None and self.all:
            self['sel'].setText(u'Brak pozycji pasujących do filtra.')
        lines = []
        if item is not None:
            star = u'★ ' if (self.is_video(item) and config.is_fav(item['id'])) else u''
            self['sel'].setText(star + item['name'])
            if item.get('info'):
                lines += item['info'].split(u'\n') + [u'']
            if self.is_video(item):
                self['key_green'].setText(
                    u'Usuń z ulubionych' if config.is_fav(item['id']) else u'Dodaj do ulubionych')
            else:
                self['key_green'].setText(self.green_label)
        main = [i for i in self.view if not i.get('more')]
        idx = self['list'].getSelectedIndex() + 1 if self.view else 0
        lines.append(u'Pozycja: %d / %d' % (min(idx, len(main)), len(main)))
        if self.flt:
            lines.append(u'Filtr: ' + self.flt)
        if len(self.sorts) > 1:
            lines.append(u'Sortowanie: ' + SORT_LABELS[self.sort])
        self['stat'].setText(u'\n'.join(lines))
        self.thumb_for_current()

    # ------------------------------------------------------------ miniatury
    def item_thumb(self, item):
        if not item or not config.get('thumbs'):
            return None
        if item.get('thumb'):
            return item['thumb']
        if item.get('kind') == 'video' and item.get('id'):
            return innertube.thumb_url(item['id'])
        return None

    def thumb_for_current(self):
        url = self.item_thumb(self.current())
        self.want = url
        try:
            self['thumb'].hide()
        except Exception:
            pass
        self.thumb_timer.stop()
        if url:
            self.thumb_timer.start(250, True)

    def load_thumb(self):
        url = self.want
        if not url or not self.alive:
            return
        path = thumbs.cached(url)
        if path:
            self.show_thumb(url, path)
            return

        def done(path):
            if path and self.alive and self.want == url:
                self.show_thumb(url, path)
        d = threads.deferToThread(thumbs.fetch, url)
        d.addCallback(done)
        d.addErrback(lambda e: None)

    def show_thumb(self, url, path):
        try:
            self.picload.setPara((S(510), S(287), 1, 1, False, 1, '#00000000'))
            self.picload.startDecode(path)
        except Exception as e:
            ytlog.log('[YTDark] miniatura:', e)

    def pic_ready(self, info=None):
        try:
            ptr = self.picload.getData()
            if ptr is not None and self['thumb'].instance and self.want:
                self['thumb'].instance.setPixmap(ptr)
                self['thumb'].show()
        except Exception as e:
            ytlog.log('[YTDark] miniatura:', e)

    # ------------------------------------------------------------ klawisze
    def up(self):
        self['list'].up()
        self.sel_changed()

    def down(self):
        self['list'].down()
        self.sel_changed()

    def page_up(self):
        self['list'].pageUp()
        self.sel_changed()

    def page_down(self):
        self['list'].pageDown()
        self.sel_changed()

    def key_ok(self):
        item = self.current()
        if item is None:
            return
        if item.get('more'):
            self.load_more(item)
        elif self.on_ok:
            self.on_ok(self, item)

    def key_green(self):
        item = self.current()
        if not self.is_video(item):
            self.key_ok()
            return
        added = config.toggle_fav(item)
        if not added and getattr(self, 'is_favlist', False):
            self.all = [i for i in self.all if i is not item]
            self.refresh()
        else:
            self.sel_changed()
        self.flash(u'Dodano do ulubionych ★' if added else u'Usunięto z ulubionych')

    def cycle_sort(self):
        if len(self.sorts) < 2:
            return
        self.sort = self.sorts[(self.sorts.index(self.sort) + 1) % len(self.sorts)]
        self.refresh()

    def ask_filter(self):
        self.session.openWithCallback(
            self.filter_done, VirtualKeyBoard,
            title=u'Filtruj listę (puste = wszystko)', text=self.flt)

    def filter_done(self, text=None):
        if text is None:
            return
        self.flt = text.strip()
        self.refresh()

    def flash(self, msg, error=False):
        popup(self.session, msg, MessageBox.TYPE_ERROR if error else MessageBox.TYPE_INFO, 3)

    def exit(self):
        self.alive = False
        self.close()


# ================================================================== logowanie
class LoginScreen(Screen):
    def __init__(self, session, login_mode='own'):
        Screen.__init__(self, session)
        self.login_mode = login_mode
        self.skin = skins.login(WIDTH)
        for name in ('title', 'line1', 'url', 'line2', 'code', 'status'):
            self[name] = Label('')
        self['key_red'] = Label(u'Anuluj')
        self['title'].setText(u'Logowanie do konta Google' if login_mode == 'own'
                              else u'Logowanie kodem (jak w YouTube na TV)')
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions'],
                                    {'cancel': self.exit, 'red': self.exit}, -1)
        self.timer = eTimer()
        self.holder = []
        connect_timer(self.timer, self.tick, self.holder)
        self.device, self.alive, self.busy = None, True, False
        self.interval, self.deadline = 5, 0
        self.onLayoutFinish.append(self.begin)

    def begin(self):
        self['status'].setText(u'Łączenie z Google…')
        d = threads.deferToThread(auth.start_device_flow, self.login_mode)
        d.addCallback(self.started)
        d.addErrback(self.failed)

    def failed(self, err):
        if self.alive:
            self['status'].setText(err_text(err))

    def started(self, data):
        if not self.alive:
            return
        self.device = data
        self['line1'].setText(u'Na telefonie lub komputerze otwórz:')
        self['url'].setText(data.get('verification_url', 'google.com/device'))
        self['line2'].setText(u'i wpisz kod:')
        self['code'].setText(data.get('user_code', ''))
        self['status'].setText(u'Czekam na zatwierdzenie…\n(kod ważny około %d min)%s' % (
            int(data.get('expires_in', 1800)) // 60,
            u'\nZalecane konto dodatkowe - to metoda nieoficjalna.' if self.login_mode == 'tv' else u''))
        self.interval = max(5, int(data.get('interval', 5)))
        self.deadline = time.time() + int(data.get('expires_in', 1800))
        self.timer.start(self.interval * 1000, False)

    def tick(self):
        if self.busy or not self.device or not self.alive:
            return
        if time.time() > self.deadline:
            self.timer.stop()
            self['status'].setText(u'Kod wygasł. Zamknij to okno i spróbuj ponownie.')
            return
        self.busy = True
        d = threads.deferToThread(auth.poll, self.device['device_code'], self.login_mode)
        d.addCallback(self.polled)
        d.addErrback(self.poll_failed)

    def poll_failed(self, err):
        self.busy = False

    def polled(self, result):
        self.busy = False
        if not self.alive:
            return
        if result == 'ok':
            self.timer.stop()
            self.alive = False
            self.close(True)
        elif result == 'slow':
            self.timer.stop()
            self.interval += 5
            self.timer.start(self.interval * 1000, False)
        elif result in ('denied', 'expired', 'error'):
            self.timer.stop()
            self['status'].setText({
                'denied': u'Odmówiono dostępu na koncie Google.',
                'expired': u'Kod wygasł. Zamknij to okno i spróbuj ponownie.',
                'error': (u'Błąd logowania. Sprawdź client_id i client_secret.' if self.login_mode == 'own'
                          else u'Błąd logowania. Zamknij okno i spróbuj ponownie.')}[result])

    def exit(self):
        self.alive = False
        self.timer.stop()
        self.close(False)


def open_login(session, after=None, login_mode='own'):
    if login_mode == 'own':
        if not auth.has_credentials():
            config.import_credentials()
        if not auth.has_credentials():
            popup(session, auth.NOT_CONFIGURED, MessageBox.TYPE_ERROR, 8)
            return

    def done(ok=False):
        if ok:
            popup(session, u'Zalogowano pomyślnie ✔', MessageBox.TYPE_INFO, 3)
        if after:
            after()
    session.openWithCallback(done, LoginScreen, login_mode)


# ================================================================== odtwarzacz
def exteplayer3_available():
    return any(os.path.exists(x) for x in ('/usr/bin/exteplayer3',
                                           '/usr/lib/enigma2/python/Plugins/SystemPlugins/ServiceApp'))


def player_type():
    """Typ uslugi odtwarzacza: 5002 = exteplayer3 (domyslnie, gdy dostepny), 4097 = gstreamer."""
    chosen = config.get('player_type')
    if chosen in (4097, 5002):
        return chosen
    return 5002 if exteplayer3_available() else 4097


def player_label():
    names = {5002: u'exteplayer3', 4097: u'gstreamer'}
    if config.get('player_type') in names:
        return names[config.get('player_type')]
    return u'automatycznie (%s)' % names[player_type()]


def make_ref(item, stream):
    url = stream['url']
    if stream.get('ua'):  # googlevideo odrzuca zapytania z innym User-Agent
        url += '#User-Agent=' + stream['ua']
    ref = eServiceReference(player_type(), 0, url)
    ref.setName(item['name'])
    return ref


PIN_KEYS = ('red', 'green', 'yellow', 'blue')
# surowe kody klawiszy (linux input) -> przeskok w sekundach; obslugiwane bezposrednio,
# bo nazwy akcji w keymapach roznych obrazow sa niejednoznaczne (strzalki = 'seekFwd' = 30 s)
RAW_SEEK = {105: -10, 106: 10, 103: 30, 108: -30, 168: -30, 208: 30}

BAR_WIDGETS = ('panel', 'accent', 'p_title', 'p_sub', 'p_state', 'progress', 'p_pos', 'p_msg', 'p_len',
               'p_keys') + tuple('k_' + k for k in PIN_KEYS) + tuple('kt_' + k for k in PIN_KEYS)


class YTPlayer(Screen):
    """Wlasny ekran odtwarzania nad odtwarzaczem dekodera: pasek z tytulem i kanalem, Play/Pauza/Stop,
    przeskoki 10/30 s, zmiana jakosci w trakcie, wznawianie, nastepny film, SponsorBlock."""

    def __init__(self, session, item, stream, streams, segments, queue):
        Screen.__init__(self, session)
        self.skin = skins.player(WIDTH)
        self.item, self.stream, self.streams = item, stream, list(streams)
        self.segments = segments or []
        self.queue = list(queue or [])
        self.played = []          # poprzednie filmy (przycisk Poprzedni)
        self.last_id = item['id']
        self.alive = True
        self.visible = True
        self.paused = False
        self.started = False
        self.ending = False
        self.loading_next = False
        self.warned = False
        self.pending_seek = None
        self.skipped = set()
        self.lastpos, self.stall, self.age = -1.0, 0, 0
        for name in BAR_WIDGETS:
            if name == 'progress':
                self[name] = Slider(0, 1000)
            elif name.startswith('k_'):
                self[name] = Label(u'\u25CF')  # kolorowa pinezka (kolor w skorce)
            else:
                self[name] = Label('')
        self['actions'] = ActionMap(
            ['OkCancelActions', 'DirectionActions', 'ColorActions', 'NumberActions',
             'MediaPlayerActions', 'InfobarSeekActions'],
            {'ok': self.toggle_bar, 'cancel': self.exit, 'stop': self.exit, 'red': self.exit,
             'play': self.do_play, 'pause': self.do_pause, 'playpauseService': self.toggle_pause,
             'pauseService': self.do_pause, 'unPauseService': self.do_play, 'green': self.toggle_pause,
             'yellow': self.toggle_autoplay, 'blue': self.pick_quality,
             'seekFwd': lambda: self.seek(30), 'seekBack': lambda: self.seek(-30),
             'next': self.next_video, 'previous': self.prev_video,
             '1': lambda: self.jump(10), '2': lambda: self.jump(20), '3': lambda: self.jump(30),
             '4': lambda: self.jump(40), '5': lambda: self.jump(50), '6': lambda: self.jump(60),
             '7': lambda: self.jump(70), '8': lambda: self.jump(80), '9': lambda: self.jump(90)}, -1)
        # strzalki w osobnej mapie o wyzszym priorytecie: w wielu obrazach te same klawisze sa tez
        # przypisane do 'seekFwd/seekBack' (=30 s) i wygrywaly z 'left/right' (=10 s)
        self['arrows'] = ActionMap(
            ['DirectionActions'],
            {'left': lambda: self.seek(-10), 'right': lambda: self.seek(10),
             'up': lambda: self.seek(30), 'down': lambda: self.seek(-30)}, -2)
        self.last_seek = 0.0
        self.raw_ok = False
        if eActionMap is not None:
            try:
                eActionMap.getInstance().bindAction('', -0x7FFFFFFF, self.raw_key)
                self.raw_ok = True
            except Exception as e:
                ytlog.log('[YTDark] bindAction:', e)
        self.holder = []
        self.tick_timer, self.hide_timer, self.msg_timer = eTimer(), eTimer(), eTimer()
        connect_timer(self.tick_timer, self.tick, self.holder)
        connect_timer(self.hide_timer, self.hide_bar, self.holder)
        connect_timer(self.msg_timer, self.clear_msg, self.holder)
        self.lastservice = session.nav.getCurrentlyPlayingServiceReference()
        self.event_tracker = None
        if ServiceEventTracker is not None:
            try:
                self.event_tracker = ServiceEventTracker(
                    screen=self, eventmap={iPlayableService.evEOF: self.on_eof})
            except Exception as e:
                ytlog.log('[YTDark] ServiceEventTracker:', e)
        self.onLayoutFinish.append(self.begin)
        self.onClose.append(self.cleanup)

    # ------------------------------------------------------------ start / koniec
    def begin(self):
        self.play_stream(self.stream, resume_at=self.saved_pos(self.item))
        self.tick_timer.start(500, False)

    def raw_key(self, key, flag):
        """Strzalki / FF / REW: stale przeskoki 10 s i 30 s niezaleznie od keymapy obrazu."""
        if key not in RAW_SEEK or not self.alive:
            return 0
        if getattr(self.session, 'current_dialog', self) is not self:
            return 0  # nad playerem jest inne okno (np. wybor jakosci) - nie przechwytuj
        if flag == 0:
            self.seek(RAW_SEEK[key])
        return 1

    def cleanup(self):
        self.alive = False
        if self.raw_ok:
            try:
                eActionMap.getInstance().unbindAction('', self.raw_key)
            except Exception as e:
                ytlog.log('[YTDark] unbindAction:', e)
        for t in (self.tick_timer, self.hide_timer, self.msg_timer):
            t.stop()
        try:
            self.session.nav.stopService()
            if self.lastservice:
                self.session.nav.playService(self.lastservice)
        except Exception as e:
            ytlog.log('[YTDark] przywracanie kanalu:', e)

    def exit(self):
        self.remember()
        self.close(self.last_id)

    # ------------------------------------------------------------ odtwarzanie
    def play_stream(self, stream, resume_at=None):
        self.stream = stream
        self.started, self.ending, self.warned = False, False, False
        self.lastpos, self.stall, self.age = -1.0, 0, 0
        self.paused = False
        self.pending_seek = resume_at
        self.session.nav.playService(make_ref(self.item, stream))
        self.refresh_texts()
        self.show_bar()
        if resume_at:
            self.msg(u'Wznowiono od %s' % util.fmt_duration(resume_at))

    def refresh_texts(self):
        it = self.item
        self['p_title'].setText(it['name'])
        bits = [it.get('channel') or u'', self.stream.get('name') or u'']
        if self.queue:
            bits.append(u'Dalej: %d' % len(self.queue))
        self['p_sub'].setText(u' \u2022 '.join(b for b in bits if b))
        self.refresh_pins()

    def refresh_pins(self):
        self['kt_red'].setText(u'Stop')
        self['kt_green'].setText(u'Odtwarzaj' if self.paused else u'Pauza')
        self['kt_yellow'].setText(u'Autoodtwarzanie: %s' % (u'TAK' if config.get('autoplay') else u'NIE'))
        self['kt_blue'].setText(u'Jakość')
        self['p_keys'].setText(u'Lewo/Prawo 10 s  Góra/Dół 30 s')

    def pauseable(self):
        svc = self.session.nav.getCurrentService()
        return svc.pause() if svc else None

    def seeker(self):
        svc = self.session.nav.getCurrentService()
        return svc.seek() if svc else None

    def do_pause(self):
        p = self.pauseable()
        if p:
            p.pause()
            self.paused = True
            self['p_state'].setText(u'II Pauza')
            self.refresh_pins()
            self.show_bar(keep=True)

    def do_play(self):
        p = self.pauseable()
        if p:
            p.unpause()
        self.paused = False
        self.refresh_pins()
        self.show_bar()

    def toggle_pause(self):
        self.do_play() if self.paused else self.do_pause()

    def seek(self, sec):
        now = time.time()
        if now - self.last_seek < 0.12:  # jeden klawisz nie moze przewinac dwa razy
            return
        self.last_seek = now
        sk = self.seeker()
        if not sk:
            return
        try:
            sk.seekRelative(-1 if sec < 0 else 1, abs(sec) * 90000)
            self.msg((u'+%d s' % sec) if sec > 0 else (u'-%d s' % -sec))
        except Exception as e:
            ytlog.log('[YTDark] seek:', e)

    def jump(self, percent):
        pos, length = self.pos_len()
        sk = self.seeker()
        if sk and length:
            sk.seekTo(int(length * percent / 100.0 * 90000))
            self.msg(u'Skok do %d%%' % percent)

    def pos_len(self):
        sk = self.seeker()
        pos = length = None
        if sk:
            try:
                r = sk.getPlayPosition()
                if not r[0]:
                    pos = r[1] / 90000.0
                l = sk.getLength()
                if not l[0] and l[1] > 0:
                    length = l[1] / 90000.0
            except Exception:
                pass
        if not length and self.item.get('num') and not self.item.get('live'):
            length = float(self.item['num'])
        return pos, length

    # ------------------------------------------------------------ wznawianie
    def saved_pos(self, item):
        if not config.get('resume_on') or item.get('live'):
            return None
        pos = (config.get('resume') or {}).get(item['id'])
        if pos and pos > 20 and (not item.get('num') or pos < item['num'] - 30):
            return pos
        return None

    def remember(self, finished=False):
        store = config.get('resume')
        if not isinstance(store, dict):
            store = {}
            config.load()['resume'] = store
        vid = self.item['id']
        pos, length = self.pos_len()
        if finished or self.item.get('live') or not self.started:
            if finished:
                store.pop(vid, None)
        elif pos and pos > 20 and not (length and pos > length - 30):
            store[vid] = int(pos)
        elif vid in store and length and pos and pos > length - 30:
            store.pop(vid, None)
        while len(store) > 150:
            store.pop(next(iter(store)))
        config.save()

    # ------------------------------------------------------------ petla co 0,5 s
    def tick(self):
        if not self.alive:
            return
        pos, length = self.pos_len()
        self.age += 1
        live = bool(self.item.get('live'))
        if pos is not None and pos > 0.3:
            self.started = True
        if not self.started:
            self['p_state'].setText(u'Ładowanie…')
            if self.age == 60 and not self.warned:  # 30 s bez obrazu
                self.warned = True
                self.msg(u'Strumień nie startuje - Niebieski: inna jakość, Next: kolejny film')
            return
        if self.pending_seek:
            sk = self.seeker()
            if sk and (length or live is False):
                try:
                    sk.seekTo(int(self.pending_seek * 90000))
                except Exception as e:
                    ytlog.log('[YTDark] wznowienie:', e)
                self.pending_seek = None
        if not self.paused:
            if abs(pos - self.lastpos) < 0.01:
                self.stall += 1
            else:
                self.stall = 0
            self['p_state'].setText(u'Buforowanie…' if self.stall >= 3 else u'\u25B6 Odtwarzanie')
        self.lastpos = pos
        self['p_pos'].setText(u'NA ŻYWO' if live else util.fmt_duration(pos))
        if length and not live:
            self['p_len'].setText(util.fmt_duration(length))
            self['progress'].setValue(max(0, min(1000, int(pos / length * 1000))))
        else:
            self['p_len'].setText(u'')
            self['progress'].setValue(0)
        self.sponsor_skip(pos)
        if length and not live and pos >= length - 1.0 and not self.paused:
            self.on_eof()

    def sponsor_skip(self, pos):
        sk = self.seeker()
        if not sk:
            return
        for n, (start, end, cat) in enumerate(self.segments):
            if n not in self.skipped and start <= pos < end - 0.5:
                self.skipped.add(n)
                sk.seekTo(int(end * 90000))
                self.msg(u'Pominięto fragment: %s' % cat)
                break

    def on_eof(self):
        if self.ending or not self.alive:
            return
        if not self.started:
            self.msg(u'Nie udało się odtworzyć strumienia - spróbuj innej jakości (Niebieski)')
            return
        self.ending = True
        self.remember(finished=True)
        if config.get('autoplay') and self.queue:
            self.next_video()
        else:
            self.close(self.last_id)

    # ------------------------------------------------------------ playlista
    def load_item(self, item, push=True):
        if self.loading_next:
            return
        self.loading_next = True
        self['p_state'].setText(u'Ładowanie…')
        self.msg(u'Wczytuję: %s' % item['name'])

        def work():
            streams = resolver.resolve(item['id'])
            segs = []
            if config.get('sponsorblock') and not item.get('live'):
                segs = sponsorblock.segments(item['id'])
            return streams, segs

        def got(result):
            self.loading_next = False
            if not self.alive:
                return
            streams, segs = result
            self.remember()
            if push:
                self.played.append(self.item)
            self.item, self.streams, self.segments = item, streams, segs
            self.last_id = item['id']
            stream = resolver.pick(streams, self.stream.get('height') or config.get('max_height') or 720) \
                or streams[0]
            config.add_history(item)
            self.play_stream(stream, resume_at=self.saved_pos(item))

        def fail(err):
            self.loading_next = False
            ytlog.log('[YTDark] nastepny film:', err)
            if self.alive:
                self.msg(err_text(err))

        d = threads.deferToThread(work)
        d.addCallback(got)
        d.addErrback(fail)

    def next_video(self):
        if self.loading_next:
            return
        if not self.queue:
            self.msg(u'To ostatni film na liście')
            if self.ending:
                self.close(self.last_id)
            return
        self.load_item(self.queue.pop(0))

    def prev_video(self):
        pos, _ = self.pos_len()
        if (pos and pos > 5) or not self.played:
            sk = self.seeker()
            if sk:
                sk.seekTo(0)
                self.msg(u'Od początku')
            return
        self.queue.insert(0, self.item)
        self.load_item(self.played.pop(), push=False)

    def toggle_autoplay(self):
        config.put('autoplay', not config.get('autoplay'))
        self.refresh_texts()
        self.msg(u'Autoodtwarzanie: %s' % (u'TAK' if config.get('autoplay') else u'NIE'))

    # ------------------------------------------------------------ jakosc w trakcie filmu
    def pick_quality(self):
        if len(self.streams) < 2:
            self.msg(u'Brak innych jakości dla tego filmu')
            return
        lst = [(s['name'] + (u'  (obecna)' if s is self.stream else u''), s) for s in self.streams]
        self.session.openWithCallback(self.quality_chosen, ChoiceBox, title=u'Jakość wideo', list=lst)

    def quality_chosen(self, choice):
        if not choice or choice[1] is self.stream:
            return
        pos, _ = self.pos_len()
        self.play_stream(choice[1], resume_at=pos if pos and pos > 3 else None)

    # ------------------------------------------------------------ pasek
    def show_bar(self, keep=False):
        for n in BAR_WIDGETS:
            self[n].show()
        self.visible = True
        self.hide_timer.stop()
        if not keep and not self.paused:
            self.hide_timer.start(6000, True)

    def hide_bar(self):
        if self.paused:
            return
        for n in BAR_WIDGETS:
            self[n].hide()
        self.visible = False

    def toggle_bar(self):
        if self.visible:
            self.hide_timer.stop()
            for n in BAR_WIDGETS:
                self[n].hide()
            self.visible = False
        else:
            self.show_bar()

    def msg(self, text):
        self['p_msg'].setText(text)
        self.show_bar(keep=self.paused)
        self.msg_timer.start(3000, True)

    def clear_msg(self):
        self['p_msg'].setText(u'')


def start_player(session, item, stream, segments, streams=None, queue=None, origin=None):
    config.add_history(item)
    ytlog.log('[YTDark] odtwarzanie: %s | typ=%s | %s | ua=%s | %s' % (
        item.get('id'), player_type(), stream.get('name'), stream.get('ua'),
        stream['url'][:140]))

    def back(last_id=None):
        if origin is not None and getattr(origin, 'alive', False) and last_id:
            origin.select_id(last_id)
    session.openWithCallback(back, YTPlayer, item, stream, streams or [stream], segments, queue or [])


def play_video(screen, item):
    screen['sel'].setText(u'Pobieranie strumienia…')

    def work():
        streams = resolver.resolve(item['id'])
        segs = []
        if config.get('sponsorblock') and not item.get('live'):
            segs = sponsorblock.segments(item['id'])
        return streams, segs

    def got(result):
        streams, segs = result
        if not screen.alive:
            return
        screen.sel_changed()
        queue = screen.queue_after(item)
        chosen = resolver.pick(streams, config.get('max_height'))
        if chosen is not None:
            start_player(screen.session, item, chosen, segs, streams, queue, screen)
            return

        def ok(chooser, row):
            start_player(chooser.session, item, row['stream'], segs, streams, queue, screen)
        screen.session.open(
            HubList, u'Jakość', item['name'],
            items=[{'name': s['name'], 'stream': s, 'kind': 'stream'} for s in streams], on_ok=ok)

    def fail(err):
        ytlog.log('[YTDark] blad strumienia:', err)
        if screen.alive:
            screen.sel_changed()
            screen.flash(err_text(err), error=True)

    d = threads.deferToThread(work)
    d.addCallback(got)
    d.addErrback(fail)


# ================================================================== przeplyw
def item_ok(screen, item):
    kind, session = item.get('kind'), screen.session
    if kind == 'video':
        play_video(screen, item)
    elif kind == 'channel':
        open_list(session, util.clean(item['name'].replace(u'[Kanał] ', u'')), u'Filmy kanału',
                  lambda: source.channel_videos(item['id']))
    elif kind == 'playlist':
        open_list(session, item['name'].replace(u'[Playlista] ', u''), u'Playlista',
                  lambda: source.playlist_items(item['id']))
    elif kind == 'category':
        open_list(session, item['name'], item.get('sub') or u'',
                  lambda: source.search(item['q'], item.get('sp')))


def open_list(session, title, subtitle, loader, sorts=('orig', 'az', 'za', 'count'), sort='orig',
              items=None, favlist=False):
    scr = session.open(HubList, title, subtitle, items=items, loader=loader, on_ok=item_ok,
                       sorts=sorts, sort=sort, favmode=True)
    scr.is_favlist = favlist
    return scr


def home_items():
    logged = auth.is_logged_in()
    items = [
        {'name': u'Strona główna', 'sub': u'Polecane filmy - bez logowania', 'kind': 'home'},
        {'name': u'Szukaj', 'sub': u'Filmy, kanały i playlisty', 'kind': 'search'},
        {'name': u'Na czasie', 'sub': u'Najpopularniejsze teraz', 'kind': 'trending'},
        {'name': u'Kategorie', 'sub': u'Muzyka, gry, sport, wiadomości…', 'kind': 'categories'},
    ]
    if logged:
        items += [{'name': u'Subskrypcje', 'sub': u'Nowe filmy z Twoich kanałów' if auth.is_tv()
                   else u'Twoje kanały', 'kind': 'subs'},
                  {'name': u'Moje playlisty', 'sub': u'Konto Google', 'kind': 'myplaylists'},
                  {'name': u'Polubione filmy', 'sub': u'Konto Google', 'kind': 'liked'}]
        if auth.is_tv():
            items += [{'name': u'Do obejrzenia później', 'sub': u'Konto Google', 'kind': 'watchlater'},
                      {'name': u'Historia konta', 'sub': u'Ostatnio oglądane w YouTube', 'kind': 'ythistory'}]
        else:
            items.append({'name': u'Moje filmy', 'sub': u'Konto Google', 'kind': 'uploads'})
    items += [{'name': u'Historia', 'sub': u'Ostatnio oglądane', 'kind': 'history',
               'right': u'%d' % len(config.get('history'))},
              {'name': u'★ Ulubione', 'sub': u'Zapisane filmy', 'kind': 'favs',
               'right': u'%d' % len(config.get('favs'))},
              {'name': u'Ustawienia', 'sub': u'Jakość, region, konto (opcjonalne)', 'kind': 'settings'}]
    return items


# ================================================================== wyszukiwanie z podpowiedziami
# wpisywanie pilotem jak w telefonie: kolejne nacisniecia tego samego klawisza = kolejna litera
MULTITAP = {'1': u' 1.,-_@', '2': u'abcąć2', '3': u'defę3', '4': u'ghi4', '5': u'jklł5',
            '6': u'mnońó6', '7': u'pqrsś7', '8': u'tuv8', '9': u'wxyzźż9', '0': u' 0'}
MULTITAP_WINDOW = 1.1  # sekundy na kolejne nacisniecie tego samego klawisza

# klawiatura ekranowa: (napis, szerokosc w kafelkach, wartosc); siatka ma 10 kolumn
KB_ROWS = [
    [(c, 1, c) for c in u'1234567890'],
    [(c, 1, c) for c in u'qwertyuiop'],
    [(c, 1, c) for c in u'asdfghjklł'],
    [(c, 1, c) for c in u'zxcvbnmóąę'],
    [(c, 1, c) for c in u'ćńśźż'] + [(u'spacja', 2, u' '), (u'Usuń', 1, 'BS'), (u'Szukaj', 2, 'GO')],
]
KB_CELL, KB_ROW_H = 74, 84
C_KEY, C_KEY_DIM = 0x272727, 0x555555

SEARCH_HELP = (u'Strzałki: wybór klawisza, OK: wpisz\n'
               u'Żółty: przejdź do podpowiedzi i z powrotem\n'
               u'W podpowiedziach: Góra/Dół, OK = szukaj,\n'
               u'Prawo = wstaw do pola\n'
               u'Zielony: szukaj    Niebieski: usuń znak\n'
               u'Cyfry: pisanie jak w telefonie\n'
               u'Klawiatura USB też działa.')


class KbMenu(MenuList):
    def __init__(self):
        MenuList.__init__(self, [], False, eListboxPythonMultiContent)
        self.l.setItemHeight(S(KB_ROW_H))
        self.l.setFont(0, gFont('Regular', S(36)))
        self.l.setFont(1, gFont('Regular', S(26)))
        try:
            self.selectionEnabled(0)
        except Exception:
            pass


class SearchScreen(Screen):
    """Pole tekstowe + wlasna klawiatura ekranowa + podpowiedzi YouTube na zywo."""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.skin = skins.search(WIDTH)
        self.text = u''
        self.sugs = []
        self.entries = []
        self.focus = 'keys'   # 'keys' = klawiatura, 'list' = podpowiedzi
        self.kr, self.kc = 1, 0
        self.last_digit, self.last_time = None, 0.0
        self.alive = True
        self['title'] = Label(u'Szukaj')
        self['subtitle'] = Label(u'Klawiatura ekranowa i podpowiedzi na żywo')
        self['mode'] = Label(u'\u25CF Zalogowano' if auth.is_logged_in() else u'\u25CF Tryb gościa')
        self['input'] = Label(u'_')
        self['kb'] = KbMenu()
        self['list'] = HubMenu()
        self['help'] = Label(SEARCH_HELP)
        for key, text in (('key_red', u'Wstecz'), ('key_green', u'Szukaj'),
                          ('key_yellow', u'Podpowiedzi'), ('key_blue', u'Usuń znak')):
            self[key] = Label(text)
        actions = {'ok': self.key_ok, 'cancel': self.close, 'red': self.close, 'green': self.search_text,
                   'yellow': self.toggle_focus, 'blue': self.backspace,
                   'up': self.key_up, 'down': self.key_down, 'left': self.key_left, 'right': self.key_right}
        for d in '0123456789':
            actions[d] = (lambda digit=d: self.digit(digit))
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'DirectionActions', 'NumberActions'],
                                    actions, -1)
        self['ascii'] = ActionMap(['ASCIIActions'], {'gotAsciiCode': self.ascii}, -1)
        self.holder = []
        self.sug_timer = eTimer()
        connect_timer(self.sug_timer, self.request_sugs, self.holder)
        self.onClose.append(self.shutdown)
        self.onLayoutFinish.append(self.start)

    def start(self):
        self.rebuild()
        self.kb_refresh()

    def shutdown(self):
        self.alive = False
        self.sug_timer.stop()

    # ------------------------------------------------------------ klawiatura ekranowa
    def kb_refresh(self):
        rows = []
        for r, row in enumerate(KB_ROWS):
            entry = [None]
            col = 0
            for ci, (label, span, value) in enumerate(row):
                selected = (r == self.kr and ci == self.kc)
                back = (C_ACCENT if self.focus == 'keys' else C_KEY_DIM) if selected else C_KEY
                entry.append(MultiContentEntryText(
                    pos=(S(KB_CELL * col + 2), S(4)), size=(S(KB_CELL * span - 4), S(KB_ROW_H - 8)),
                    font=0 if len(label) == 1 else 1, flags=RT_HALIGN_CENTER | RT_VALIGN_CENTER,
                    text=label, color=C_TEXT, color_sel=C_TEXT, backcolor=back, backcolor_sel=back))
                col += span
            rows.append(entry)
        self['kb'].l.setList(rows)

    @staticmethod
    def _start_col(row, idx):
        return sum(c[1] for c in row[:idx])

    def kb_move(self, dr, dc):
        row = KB_ROWS[self.kr]
        if dc:
            self.kc = (self.kc + dc) % len(row)
        if dr:
            col = self._start_col(row, self.kc)
            nr = max(0, min(len(KB_ROWS) - 1, self.kr + dr))
            if nr != self.kr:
                self.kr = nr
                for ci, (_l, span, _v) in enumerate(KB_ROWS[nr]):
                    if self._start_col(KB_ROWS[nr], ci) <= col < self._start_col(KB_ROWS[nr], ci) + span:
                        self.kc = ci
                        break
        self.kb_refresh()

    def set_focus(self, focus):
        self.focus = focus
        self.kb_refresh()

    def toggle_focus(self):
        self.set_focus('list' if self.focus == 'keys' and self.entries else 'keys')

    def key_up(self):
        self.kb_move(-1, 0) if self.focus == 'keys' else self['list'].up()

    def key_down(self):
        self.kb_move(1, 0) if self.focus == 'keys' else self['list'].down()

    def key_left(self):
        self.kb_move(0, -1) if self.focus == 'keys' else self.set_focus('keys')

    def key_right(self):
        self.kb_move(0, 1) if self.focus == 'keys' else self.complete()

    def key_ok(self):
        if self.focus == 'list':
            self.ok()
            return
        value = KB_ROWS[self.kr][self.kc][2]
        if value == 'BS':
            self.backspace()
        elif value == 'GO':
            self.search_text()
        else:
            self.text += value
            self.last_digit = None
            self.changed()

    # ------------------------------------------------------------ lista
    def rebuild(self, keep=False):
        index = self['list'].getSelectionIndex() if keep else 0
        t = self.text.strip()
        items = []
        if t:
            items.append({'name': u'Szukaj: %s' % t, 'sub': u'Dokładnie tę frazę', 'q': t, 'right': u''})
            items += [{'name': s, 'sub': u'Podpowiedź', 'q': s, 'right': u''} for s in self.sugs]
        else:
            items = [{'name': q, 'sub': u'Ostatnio szukane', 'q': q, 'right': u''}
                     for q in (config.get('searches') or [])]
        self.entries = items
        if not items and self.focus == 'list':
            self.focus = 'keys'
            self.kb_refresh()
        self['list'].l.setList([make_entry(i, S(950)) for i in items])
        self['list'].moveToIndex(max(0, min(index or 0, len(items) - 1)))

    def selected(self):
        idx = self['list'].getSelectionIndex()
        return self.entries[idx] if 0 <= idx < len(self.entries) else None

    # ------------------------------------------------------------ wpisywanie
    def changed(self):
        self['input'].setText(self.text + u'_')
        t = self.text.strip()
        cached = suggest._cache.get(t)
        if cached is not None:
            self.sugs = cached
        else:  # zostaw tylko dotychczasowe podpowiedzi pasujace do nowego poczatku
            self.sugs = [s for s in self.sugs if t and s.lower().startswith(t.lower())]
        self.rebuild()
        self.sug_timer.stop()
        if t and cached is None:
            self.sug_timer.start(250, True)

    def request_sugs(self):
        q = self.text.strip()
        if not q:
            return

        def got(result):
            if self.alive and self.text.strip() == q:
                self.sugs = result
                self.rebuild(keep=True)
        d = threads.deferToThread(suggest.fetch, q)
        d.addCallback(got)
        d.addErrback(lambda e: None)

    def digit(self, d):
        chars = MULTITAP[d]
        now = time.time()
        if d == self.last_digit and now - self.last_time < MULTITAP_WINDOW and self.text \
                and self.text[-1] in chars:
            self.text = self.text[:-1] + chars[(chars.index(self.text[-1]) + 1) % len(chars)]
        else:
            self.text += chars[0]
        self.last_digit, self.last_time = d, now
        self.changed()

    def backspace(self):
        self.text = self.text[:-1]
        self.last_digit = None
        self.changed()

    def complete(self):
        item = self.selected()
        if item and self.text.strip():
            self.text = item['q'] + u' '
            self.last_digit = None
            self.changed()
        self.set_focus('keys')

    def ascii(self):
        """Klawiatura USB / pilot z klawiatura: litery i znaki (cyfry obsluguje blok numeryczny)."""
        if getPrevAsciiCode is None:
            return
        try:
            code = getPrevAsciiCode()
        except Exception:
            return
        if code in (8, 127):
            self.backspace()
        elif code >= 32 and not (48 <= code <= 57):
            try:
                self.text += unichr(code)  # noqa: F821  (python 2)
            except NameError:
                self.text += chr(code)
            self.last_digit = None
            self.changed()

    # ------------------------------------------------------------ szukanie
    def ok(self):
        item = self.selected()
        if item:
            run_search(self.session, item['q'])
        elif self.text.strip():
            run_search(self.session, self.text)

    def search_text(self):
        if self.text.strip():
            run_search(self.session, self.text)


def run_search(session, query):
    query = query.strip()
    if not query:
        return
    config.add_search(query)
    open_list(session, u'Szukaj', query, lambda: source.search(query))


def open_search(session):
    session.open(SearchScreen)


def home_ok(screen, item):
    session, kind = screen.session, item['kind']
    if kind == 'home':
        open_list(session, u'Strona główna', u'Polecane dla gościa', source.home)
    elif kind == 'search':
        open_search(session)
    elif kind == 'trending':
        open_list(session, u'Na czasie', u'Najpopularniejsze teraz', source.trending)
    elif kind == 'categories':
        open_list(session, u'Kategorie', u'Wybierz kategorię', None, items=source.categories(),
                  sorts=('orig', 'az', 'za'))
    elif kind == 'subs':
        open_list(session, u'Subskrypcje', u'Twoje kanały', source.subscriptions,
                  sorts=('orig', 'az', 'za', 'count'), sort='orig' if auth.is_tv() else 'az')
    elif kind == 'myplaylists':
        open_list(session, u'Moje playlisty', u'Konto Google', source.my_playlists,
                  sorts=('az', 'za', 'count', 'orig'), sort='az')
    elif kind == 'liked':
        open_list(session, u'Polubione', u'Konto Google', source.liked_videos)
    elif kind == 'watchlater':
        open_list(session, u'Do obejrzenia później', u'Konto Google', source.watch_later)
    elif kind == 'ythistory':
        open_list(session, u'Historia konta', u'Ostatnio oglądane', source.yt_history,
                  sorts=('orig', 'az', 'za'))
    elif kind == 'uploads':
        open_list(session, u'Moje filmy', u'Konto Google', api.my_uploads)
    elif kind == 'history':
        entries = list(config.get('history'))
        open_list(session, u'Historia', u'Ostatnio oglądane', None,
                  items=source.local_items(entries))
    elif kind == 'favs':
        entries = list(config.get('favs'))
        open_list(session, u'★ Ulubione', u'Zapisane filmy', None,
                  items=source.local_items(entries), sorts=('az', 'orig'), sort='az', favlist=True)
    elif kind == 'settings':
        open_settings(session, screen)


def account_items():
    if auth.is_logged_in():
        return [{'name': u'Konto Google: zalogowano (%s) - wyloguj' % (u'kod TV' if auth.is_tv() else u'własny projekt'),
                 'sub': u'OK wylogowuje z tego dekodera', 'kind': 'set_logout'}]
    return [{'name': u'Zaloguj kodem (szybko, nieoficjalne)',
             'sub': u'Jak YouTube na TV - bez własnego projektu; zalecane konto dodatkowe',
             'kind': 'set_login_tv'},
            {'name': u'Zaloguj - własny projekt Google (oficjalne)',
             'sub': u'Wymaga client_id/secret - patrz README', 'kind': 'set_login_own'}]


def settings_items():
    q = config.get('max_height')
    return account_items() + [
        {'name': u'Miniatury: ' + (u'TAK' if config.get('thumbs') else u'NIE'),
         'sub': u'Podgląd zaznaczonego filmu', 'kind': 'set_thumbs'},
        {'name': u'Wznawianie od miejsca: ' + (u'TAK' if config.get('resume_on') else u'NIE'),
         'sub': u'Zapamiętuje, gdzie skończyłeś oglądać', 'kind': 'set_resume'},
        {'name': u'Pokaż w menu głównym: ' + (u'TAK' if config.get('main_menu') else u'NIE'),
         'sub': u'Skrót do YTDark w menu głównym dekodera (po restarcie GUI)', 'kind': 'set_mainmenu'},
        {'name': u'Aktualizacje: sprawdź teraz (wersja %s)' % __version__,
         'sub': u'Pobiera nową wersję z GitHub tylko za Twoją zgodą', 'kind': 'set_update'},
        {'name': u'Sprawdzaj aktualizacje automatycznie: ' + (u'TAK' if config.get('update_check') else u'NIE'),
         'sub': u'Raz na dobę przy uruchomieniu pluginu', 'kind': 'set_autoupdate'},
        {'name': u'Przywróć poprzednią wersję', 'sub': u'Kopia sprzed ostatniej aktualizacji',
         'kind': 'set_rollback'},
        {'name': u'yt-dlp: ' + (u'zainstalowany' if ytdlp_setup.installed() else u'niezainstalowany'),
         'sub': u'OK: zainstaluj lub zaktualizuj (opkg install python3-yt-dlp)', 'kind': 'set_ytdlp'},
        {'name': u'Pytaj o yt-dlp przy starcie: ' + (u'TAK' if config.get('ytdlp_prompt') else u'NIE'),
         'sub': u'Gdy yt-dlp nie jest zainstalowany', 'kind': 'set_ytdlp_prompt'},
        {'name': u'Autoodtwarzanie następnego: ' + (u'TAK' if config.get('autoplay') else u'NIE'),
         'sub': u'Kolejny film z listy, playlisty lub kanału', 'kind': 'set_autoplay'},
        {'name': u'Pomijanie sponsorów: ' + (u'TAK' if config.get('sponsorblock') else u'NIE'),
         'sub': u'SponsorBlock', 'kind': 'set_sb'},
        {'name': u'Odtwarzacz: ' + player_label(),
         'sub': u'Domyślnie exteplayer3, gdy jest w obrazie; OK przełącza', 'kind': 'set_player'},
        {'name': u'Jakość wideo: ' + (u'%dp' % q if q else u'zawsze pytaj'),
         'sub': u'Najwyższa dostępna jako pojedynczy strumień', 'kind': 'set_q'},
        {'name': u'Region list: ' + config.get('region'), 'sub': u'Wpływa na polecane', 'kind': 'set_region'},
        {'name': u'Wyczyść historię', 'sub': u'Oglądane filmy', 'kind': 'set_clear'},
        {'name': u'Wyczyść ostatnie wyszukiwania', 'sub': u'Lista fraz w Szukaj', 'kind': 'set_clear_s'},
    ]


def open_settings(session, home_screen):
    def ok(screen, item):
        kind = item['kind']
        if kind == 'set_logout':
            auth.logout()
            screen.set_items(settings_items(), keep=True)
            home_screen.set_items(home_items(), keep=True)
            return
        if kind in ('set_login_tv', 'set_login_own'):
            def refreshed():
                screen.set_items(settings_items(), keep=True)
                home_screen.set_items(home_items(), keep=True)
            open_login(session, after=refreshed, login_mode='tv' if kind == 'set_login_tv' else 'own')
            return
        if kind == 'set_thumbs':
            config.put('thumbs', not config.get('thumbs'))
        elif kind == 'set_resume':
            config.put('resume_on', not config.get('resume_on'))
        elif kind == 'set_mainmenu':
            config.put('main_menu', not config.get('main_menu'))
            screen.set_items(settings_items(), keep=True)
            session.openWithCallback(
                lambda yes: restart_gui(session) if yes else None, MessageBox,
                u'Skrót w menu głównym %s po restarcie interfejsu.\nZrestartować GUI teraz?'
                % (u'pojawi się' if config.get('main_menu') else u'zniknie'),
                MessageBox.TYPE_YESNO)
            return
        elif kind == 'set_ytdlp':
            check_ytdlp(session, manual=True)
            return
        elif kind == 'set_ytdlp_prompt':
            config.put('ytdlp_prompt', not config.get('ytdlp_prompt'))
        elif kind == 'set_update':
            check_updates(session, manual=True)
            return
        elif kind == 'set_autoupdate':
            config.put('update_check', not config.get('update_check'))
        elif kind == 'set_rollback':
            def do_rollback(yes):
                if not yes:
                    return
                if update.rollback():
                    ask_restart(session, u'Przywrócono poprzednią wersję.')
                else:
                    popup(session, u'Brak kopii zapasowej.', MessageBox.TYPE_ERROR, 5)
            session.openWithCallback(do_rollback, MessageBox,
                                     u'Przywrócić wersję sprzed ostatniej aktualizacji?', MessageBox.TYPE_YESNO)
            return
        elif kind == 'set_autoplay':
            config.put('autoplay', not config.get('autoplay'))
        elif kind == 'set_sb':
            config.put('sponsorblock', not config.get('sponsorblock'))
        elif kind == 'set_player':
            order = [0, 5002, 4097]  # automatyczny -> exteplayer3 -> gstreamer
            cur = config.get('player_type')
            config.put('player_type', order[(order.index(cur) + 1) % 3] if cur in order else 5002)
        elif kind == 'set_q':
            cur = config.get('max_height')
            config.put('max_height', QUALITIES[(QUALITIES.index(cur) + 1) % len(QUALITIES)]
                       if cur in QUALITIES else 720)
        elif kind == 'set_region':
            cur = config.get('region')
            config.put('region', REGIONS[(REGIONS.index(cur) + 1) % len(REGIONS)]
                       if cur in REGIONS else 'PL')
        elif kind == 'set_clear':
            config.put('history', [])
            screen.flash(u'Historia wyczyszczona.')
        elif kind == 'set_clear_s':
            config.put('searches', [])
            screen.flash(u'Wyszukiwania wyczyszczone.')
        screen.set_items(settings_items(), keep=True)
        home_screen.set_items(home_items(), keep=True)

    session.open(HubList, u'Ustawienia', u'OK zmienia wartość', items=settings_items(), on_ok=ok)


# ================================================================== aktualizacje
_restart_timers = []


def restart_gui(session):
    """Restart interfejsu zlecony z timera, a nie bezposrednio z callbacku okna.

    Enigma pozwala otworzyc kolejne okno modalne tylko z ekranu, ktory aktualnie dziala; w callbacku
    zamykanego MessageBox (zwlaszcza gdy pod spodem czekalo inne okno) bywa to niemozliwe
    ("Modal open are allowed only from a screen which is modal"). Timer odpala sie juz po uporzadkowaniu stosu okien."""
    holder = []
    timer = eTimer()
    entry = (timer, holder)

    def fire():
        if entry in _restart_timers:
            _restart_timers.remove(entry)
        try:
            session.open(TryQuitMainloop, 3)
        except Exception as e:  # ostatnia deska ratunku: bezposredni restart GUI
            ytlog.log('[YTDark] TryQuitMainloop:', e)
            try:
                from enigma import quitMainloop
                quitMainloop(3)
            except Exception as e2:
                ytlog.log('[YTDark] quitMainloop:', e2)
    connect_timer(timer, fire, holder)
    _restart_timers.append(entry)
    timer.start(400, True)


def ask_restart(session, prefix):
    session.openWithCallback(
        lambda yes: restart_gui(session) if yes else None, MessageBox,
        prefix + u'\nZrestartować interfejs teraz? (bez tego działa jeszcze stara wersja)',
        MessageBox.TYPE_YESNO)


def check_updates(session, manual=False, after=None):
    """after: wywolywane, gdy nie ma co aktualizowac / uzytkownik odmowil / blad (kolejny krok startu)."""
    def work():
        return update.check(force=manual)

    def got(info):
        if info:
            offer_update(session, info, after)
            return
        if manual:
            popup(session, u'Masz najnowszą wersję (%s).' % __version__, MessageBox.TYPE_INFO, 5)
        elif after:
            after()

    def fail(err):
        ytlog.log('[YTDark] sprawdzanie aktualizacji:', err)
        if manual:
            popup(session, err_text(err), MessageBox.TYPE_ERROR, 8)
        elif after:
            after()

    d = threads.deferToThread(work)
    d.addCallback(got)
    d.addErrback(fail)


def offer_update(session, info, after=None):
    notes = info.get('notes') or u''
    if len(notes) > 400:
        notes = notes[:400].rsplit(u'\n', 1)[0] + u'\n…'
    text = u'Dostępna nowa wersja YTDark: %s (masz %s).\n\n%s\n\nZainstalować teraz?' % (
        info['version'], __version__, notes)
    def answer(yes):
        if yes:
            install_update(session, info)
        elif after:
            after()
    session.openWithCallback(answer, MessageBox, text, MessageBox.TYPE_YESNO)


def install_update(session, info):
    popup(session, u'Pobieram i instaluję aktualizację…', MessageBox.TYPE_INFO, 4)

    def got(version):
        ask_restart(session, u'Zainstalowano wersję %s.' % version)

    def fail(err):
        ytlog.log('[YTDark] aktualizacja:', err)
        popup(session, u'Aktualizacja nie powiodła się:\n' + err_text(err), MessageBox.TYPE_ERROR, 10)

    d = threads.deferToThread(update.install, info)
    d.addCallback(got)
    d.addErrback(fail)


# ================================================================== yt-dlp
def popup(session, text, kind=None, timeout=10):
    """Komunikat nad dowolnym oknem (takze nad odtwarzaczem), bez blokowania pracy."""
    kind = MessageBox.TYPE_INFO if kind is None else kind
    if AddPopup is not None:
        try:
            AddPopup(text, kind, timeout)
            return
        except Exception as e:
            ytlog.log('[YTDark] AddPopup:', e)
    session.open(MessageBox, text, kind)  # bez timeoutu: nie zostawiamy "wiszacych" okien pod innymi


def ytdlp_install(session):
    """opkg update + install/upgrade w tle; plugin dziala dalej, wynik przychodzi jako komunikat."""
    if ytdlp_setup.busy:
        popup(session, u'Instalacja yt-dlp już trwa…', timeout=5)
        return
    popup(session, u'Instaluję yt-dlp w tle (opkg) - możesz dalej korzystać z pluginu.\n'
                   u'Dam znać, gdy będzie gotowe.', timeout=6)

    def got(result):
        ok, msg = result
        popup(session, msg, MessageBox.TYPE_INFO if ok else MessageBox.TYPE_ERROR, 12)

    def fail(err):
        ytlog.log('[YTDark] instalacja yt-dlp:', err)
        popup(session, u'Instalacja yt-dlp nie powiodła się:\n' + err_text(err), MessageBox.TYPE_ERROR, 12)

    d = threads.deferToThread(ytdlp_setup.install_or_upgrade)
    d.addCallback(got)
    d.addErrback(fail)


def check_ytdlp(session, manual=False):
    """Brak yt-dlp -> pyta, czy zainstalowac (opkg install python3-yt-dlp). Jest -> (reczne) proponuje aktualizacje."""
    if not ytdlp_setup.supported():
        if manual:
            popup(session, u'Ten obraz nie obsługuje instalacji yt-dlp przez opkg\n'
                           u'(wymagany Python 3 i opkg).', MessageBox.TYPE_INFO, 8)
        return
    if ytdlp_setup.installed():
        if not manual:
            return

        def have(ver):
            text = u'yt-dlp jest zainstalowany%s.\nSprawdzić i zainstalować aktualizację?' % (
                u' (pakiet %s)' % ver if ver else u'')
            session.openWithCallback(lambda yes: ytdlp_install(session) if yes else None,
                                     MessageBox, text, MessageBox.TYPE_YESNO)
        d = threads.deferToThread(ytdlp_setup.version)
        d.addCallback(have)
        d.addErrback(lambda e: have(u''))
        return
    text = (u'Nie wykryto yt-dlp (pakiet %s).\n'
            u'Bez niego część filmów może się nie odtwarzać (blokada „bot”).\n\n'
            u'Zainstalować teraz? (opkg install %s)\nInstalacja trwa w tle - plugin działa dalej.'
            % (ytdlp_setup.PACKAGE, ytdlp_setup.PACKAGE))
    session.openWithCallback(lambda yes: ytdlp_install(session) if yes else None,
                             MessageBox, text, MessageBox.TYPE_YESNO)


# ================================================================== wejscie
def main(session, **kwargs):
    config.load(force=True)
    if not auth.has_credentials():
        config.import_credentials()  # opcjonalne: tylko dla logowania do konta
    session.open(HubList, u'YTDark', u'YouTube bez reklam \u2022 v%s' % __version__, items=home_items(),
                 on_ok=home_ok)
    def next_step():
        if config.get('ytdlp_prompt'):
            check_ytdlp(session)

    if config.get('update_check') and update.enabled():
        check_updates(session, after=next_step)
    else:
        next_step()


def menu_entry(menuid, **kwargs):
    """Skrot w menu glownym dekodera (wlaczany w Ustawieniach, dziala po restarcie GUI)."""
    if menuid == 'mainmenu':
        return [(u'YTDark', main, 'ytdark', 47)]
    return []


def Plugins(**kwargs):
    entries = [PluginDescriptor(
        name='YTDark',
        description=u'YouTube bez reklam: wyszukiwanie i przeglądanie bez logowania, SponsorBlock',
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon='icon.png',
        fnc=main)]
    try:
        if config.load().get('main_menu'):
            entries.append(PluginDescriptor(
                name='YTDark', description=u'YouTube bez reklam',
                where=PluginDescriptor.WHERE_MENU, fnc=menu_entry))
    except Exception as e:
        ytlog.log('[YTDark] menu glowne:', e)
    return entries
