YTDark - YouTube bez reklam dla Enigma2
=======================================

INSTALACJA
  unzip YTDark.zip -d /usr/lib/enigma2/python/Plugins/Extensions/
  killall -9 enigma2
Plugin pojawi sie w menu pluginow jako "YTDark".

TRYB GOSCIA (domyslny) - NIC NIE TRZEBA KONFIGUROWAC
  Wyszukiwanie, strona glowna, "Na czasie", kategorie, kanaly i playlisty
  dzialaja bez logowania i bez kluczy Google - tak jak YouTube w przegladarce
  dla niezalogowanego widza. Zaznaczony film pokazuje miniature i opis.
  Reklamy i Shorts sa pomijane. Historia, ulubione i ostatnie wyszukiwania
  zapisuja sie lokalnie w odbiorniku.

OPCJONALNIE: logowanie do konta (Ustawienia -> Konto Google)
  Dwa sposoby, w obu na ekranie pojawia sie kod, ktory wpisujesz w telefonie
  (haslo nigdy nie jest wpisywane na dekoderze):

  A) "Zaloguj kodem (szybko, nieoficjalne)" - jak YouTube na telewizorze.
     Nic nie trzeba konfigurowac: wejdz na youtube.com/activate i wpisz kod.
     Daje: polecane dla konta, nowe filmy z subskrypcji, playlisty, polubione,
     "Do obejrzenia pozniej", historie konta, prywatne playlisty.
     To metoda nieoficjalna - YouTube moze ja zmienic. Zalecane konto dodatkowe.

  B) "Zaloguj - wlasny projekt Google (oficjalne)" - wymaga danych z darmowego
     projektu Google (limit 10 000 jednostek dziennie):
 1. https://console.cloud.google.com -> nowy projekt, wlacz "YouTube Data API v3".
 2. "OAuth consent screen": typ "External", dodaj SWOJE konto jako "Test user".
 3. "Credentials" -> "OAuth client ID" -> typ "TVs and Limited Input devices".
 4. Plik ytdark_credentials.json na pendrivie (/media/usb) lub w /tmp:
    {"client_id": "...", "client_secret": "...", "api_key": "(opcjonalnie)"}
    Dane zostana zapisane w /etc/enigma2/ytdark.json (uprawnienia 600).

PILOT W TRAKCIE FILMU
  Zielony / Play / Pauza  - odtwarzanie i pauza
  Czerwony / Stop / Exit   - zakoncz (zapamietuje miejsce)
  Lewo / Prawo             - przeskok -10 s / +10 s
  Gora / Dol, FF / REW     - przeskok +30 s / -30 s
  Cyfry 1-9                - skok do 10%-90% filmu
  Niebieski                - zmiana jakosci bez wychodzenia
  Zolty                    - autoodtwarzanie nastepnego TAK/NIE
  Next / Prev              - nastepny / poprzedni film z listy
  OK                       - pokaz / ukryj pasek

WYSZUKIWANIE Z PODPOWIEDZIAMI: pole tekstowe + lista podpowiedzi YouTube na zywo.
  Cyfry 2-9 pisza jak w telefonie (kilka nacisniec = kolejna litera, w tym polskie znaki),
  Lewo = usun znak, Prawo = wstaw podpowiedz, Gora/Dol = wybor, OK = szukaj,
  Zolty = pelna klawiatura ekranowa, Niebieski = wyczysc. Klawiatura USB dziala.
  Przy pustym polu widac ostatnie wyszukiwania. Wylaczenie: Ustawienia -> Podpowiedzi.

YT-DLP: przy starcie plugin sprawdza, czy jest zainstalowany python3-yt-dlp. Gdy go
  brak, pyta, czy zainstalowac (opkg update + opkg install python3-yt-dlp). Instalacja
  dziala w tle - plugin nie jest przerywany, a wynik pojawia sie jako komunikat.
  Reczne sprawdzenie/aktualizacja: Ustawienia -> yt-dlp. Pytanie przy starcie mozna
  wylaczyc w Ustawieniach.

SKROT W MENU GLOWNYM: Ustawienia -> "Pokaz w menu glownym" (po restarcie GUI
  w menu glownym dekodera pojawi sie pozycja YTDark).

DZIENNIK: plugin zapisuje wlasny log w /tmp/ytdark.log (np. przez FTP/telnet:
  cat /tmp/ytdark.log) - nie wymaga wlaczania logow debug.

WAZNE: POBIERANIE STRUMIENIA
  To najbardziej zmienna czesc, bo YouTube regularnie zmienia
  zabezpieczenia. Kolejnosc prob: yt-dlp (jesli zainstalowany na
  odbiorniku, np. opkg install python3-yt-dlp - dostepnosc zalezy od
  obrazu) -> wbudowany klient (resolver.py). Gdy film sie nie otwiera,
  najpierw zainstaluj/zaktualizuj yt-dlp.
  Komunikat "Zaloguj sie, by potwierdzic, ze nie jestes botem" to blokada
  adresu IP przez YouTube (VPN/proxy/siec mobilna/wiele zapytan). Plugin
  probuje po kolei 5 klientow; gdy wszystkie odpadna: wylacz VPN/filtr DNS,
  zrestartuj router (nowy IP) albo poczekaj kilka godzin.
  Jakosc: Ustawienia -> "Jakosc wideo" (360p-1080p albo "zawsze pytaj").
  Formaty wyzsze niz 720p zwykle wymagaja osobnego audio i nie sa
  dostepne jako pojedynczy strumien.
