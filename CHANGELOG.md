# Historia zmian

## [2.2.0]
- Wyszukiwanie z podpowiedziami na żywo (pisanie pilotem jak w telefonie, klawiatura USB, ostatnie wyszukiwania).
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
