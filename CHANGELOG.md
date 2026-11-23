# Historia zmian

## [2.5.5]
- Komunikaty (np. „film dostępny tylko w wersji premium”, błędy, postęp instalacji) wyświetlają się wprost w ekranie pluginu
  przez ok. 5 s (dłuższe teksty dłużej): na liście w miejscu „Pobieranie strumienia…”, w wyszukiwaniu pod tytułem,
  na pasku odtwarzacza i na ekranie logowania. Zastępuje to nakładkę z 2.5.4, która w niektórych obrazach była pod interfejsem.

## [2.5.4]
- Powiadomienia (np. „film dostępny tylko w wersji premium”, postęp instalacji, błędy) są rysowane od razu nad ekranem
  pluginu i odtwarzaczem, a nie w systemowej kolejce, która pokazywała je dopiero po zamknięciu YTDark.
  Kilka powiadomień wyświetla się po kolei, powtórki są pomijane, a czas wyświetlania zależy od długości tekstu.

## [2.5.3]
- Playlisty i Mixy: najpierw zwykłe zapytanie (pełna lista, działa też przy koncie zalogowanym kodem TV), klient TV tylko
  jako zapas dla prywatnych list. Naprawia błąd 400 przy Mixach oraz „9 zamiast 18 filmów” przy zalogowanym koncie.
- Usunięto „szybką” ekstrakcję yt-dlp z wersji 2.5.0: zawsze kończyła się błędem i wydłużała start filmu o ok. 8 s.
- Filmy z ograniczeniem wiekowym pokazują właściwy komunikat zamiast fałszywego „blokady bota”.

## [2.5.2]
- Playlisty i Mixy doczytują kolejne strony automatycznie (do 4 stron), więc lista od razu pokazuje wszystkie filmy,
  a nie tylko pierwszą partię z pozycją „Wczytaj więcej”. Obsługa tokenów kolejnych stron także w starszym zapisie YouTube.
- W logu `/tmp/ytdark.log` widać, ile pozycji zwrócił YouTube i czy jest kolejna strona.

## [2.5.1]
- Naprawiono otwieranie playlist z wyszukiwania: Mixy („Mix – …”) i listy bez zwykłej strony otwierają się teraz
  jako kolejka odtwarzania (wcześniej błąd „kod 400”); gdy strona playlisty zawiedzie, używany jest ten sam zapas.
- Nieudane zapytania do YouTube są zapisywane w `/tmp/ytdark.log` wraz z odpowiedzią serwera.

## [2.5.0]
- Szybsze otwieranie filmów: zaznaczony na ponad ~2 s film jest przygotowywany w tle (Ustawienia →
  „Wczytywanie z wyprzedzeniem”), więc OK działa od razu; wynik trafia do pamięci podręcznej (20 min),
  a równoległe pobrania tego samego filmu są łączone w jedno.
- Plugin zapamiętuje, która metoda pobierania (yt-dlp / własne klienty) działała ostatnio, i od niej zaczyna.
- yt-dlp: szybka ekstrakcja (tylko klient web_safari, bez DASH) z automatycznym powrotem do ustawień domyślnych.
- Segmenty SponsorBlock pobierane równolegle ze strumieniem i zapamiętywane.
- Czasy poszczególnych etapów zapisywane w `/tmp/ytdark.log`.

## [2.4.1]
- Naprawiono awarię GUI po aktualizacji pluginu (`Modal open are allowed only from a screen which is modal`):
  restart interfejsu jest teraz zlecany z timera, a komunikaty informacyjne nie zostawiają okien z timeoutem pod innymi.
- Wyciszono nieszkodliwy błąd `BrokenPipeError` w logu Enigmy przy zamykaniu odtwarzania HLS.

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
