# -*- coding: utf-8 -*-
"""Punkt wejscia Enigmy2.

YTDark wymaga Pythona 3. Na Pythonie 2 wtyczka pokazuje tylko komunikat, a caly kod
aplikacji (app.py) nie jest w ogole ladowany - dzieki temu nie ma bledow skladni ani awarii GUI."""
import sys

if sys.version_info[0] >= 3:
    from .app import Plugins, main  # noqa: F401
else:
    from Plugins.Plugin import PluginDescriptor
    from Screens.MessageBox import MessageBox

    def main(session, **kwargs):
        session.open(
            MessageBox,
            u'YTDark wymaga Pythona 3.\nTen obraz używa Pythona 2, więc wtyczka nie jest obsługiwana.\n'
            u'Zainstaluj obraz z Pythonem 3 (np. OpenATV 7.x lub nowszy).',
            MessageBox.TYPE_ERROR, timeout=15)

    def Plugins(**kwargs):
        return [PluginDescriptor(
            name=u'YTDark (wymaga Pythona 3)', description=u'Ten obraz używa Pythona 2',
            where=PluginDescriptor.WHERE_PLUGINMENU, icon='icon.png', fnc=main)]
