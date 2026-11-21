# Historia zmian

## [2.4.0]
- Wymagany Python 3: instalator (`install.sh`) odmawia instalacji na obrazach z Pythonem 2, pakiet IPK ma
  zależność `python3-core`, a sama wtyczka na Pythonie 2 pokazuje tylko komunikat (nie ładuje kodu aplikacji).
- Kod aplikacji przeniesiony z `plugin.py` do `app.py`; `plugin.py` jest teraz cienkim punktem wejścia.

## [2.3.1]
- Naprawiono błąd: wyjście z ekranu wyszukiwania (Wstecz) wywalało Enigmę (`'list' object is not callable`).

## [2.3.0]
- Nowe wyszukiwanie: własna klawiatura ekranowa z podpowiedziami YouTube na żywo (jedyny tryb wyszukiwania);
  zachowane pisanie cyframi jak w telefonie, klawiatura USB i ostatnie wyszukiwania.
- Usunięto przełącznik podpowiedzi i stary ekran wyszukiwania.

## [2.2.0]
- Domyślny odtwarzacz: exteplayer3 (jeśli jest w obrazie, inaczej gstreamer); zmiana w Ustawieniach.
- Sprawdzanie yt-dlp przy starcie: gdy brak `python3-yt-dlp`, plugin pyta o instalację przez opkg;
  instalacja i aktualizacja działają w tle (Ustawienia → yt-dlp).

## [2.1.0]
- Aktualizacje z GitHub: sprawdzanie raz na dobę, instalacja tylko za zgodą, sumy SHA-256,
  kopia zapasowa i możliwość przywrócenia poprzedniej wersji (Ustawienia).
- Skrót do pluginu w menu głównym dekodera (opcja w Ustawieniach).
- Przeskoki Lewo/Prawo 10 s, Góra/Dół oraz FF/REW 30 s niezależnie od keymapy obrazu.
- Własny pasek odtwarzania z kolorowymi pinezkami przycisków pilota.

## [2.0.0]
- Tryb gościa: wyszukiwanie, strona główna, „Na czasie” i kategorie bez logowania i bez kluczy API.
- Nowy ciemny wygląd w stylu YouTube z miniaturami.
- Własny ekran odtwarzania: Play/Pauza/Stop, przeskoki, zmiana jakości w trakcie, wznawianie,
  autoodtwarzanie następnego filmu, SponsorBlock.
- Odtwarzanie HLS z dźwiękiem (składanie obrazu i dźwięku), wielu klientów YouTube, własny log.
- Logowanie kodem (jak YouTube na TV, nieoficjalne) obok oficjalnego własnego projektu Google.
