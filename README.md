# YTDark

Wtyczka **YouTube bez reklam** dla dekoderów z **Enigma2** (OpenATV, OpenPLi i pochodne).

- Wyszukiwanie, strona główna, „Na czasie”, kategorie, kanały i playlisty **bez logowania i bez kluczy API** (tryb gościa)
- Ciemny wygląd w stylu YouTube z miniaturami
- Własny ekran odtwarzania: Play/Pauza/Stop, przeskoki 10 s i 30 s, zmiana jakości w trakcie filmu,
  wznawianie od miejsca, autoodtwarzanie następnego filmu, SponsorBlock
- Opcjonalne logowanie kodem (subskrypcje, playlisty, polubione)
- Aktualizacje z GitHub prosto z pluginu (za Twoją zgodą)

## Wymagania

Obraz Enigma2 z **Pythonem 3** (np. OpenATV 7.x lub nowszy). Instalator i pakiet IPK odmawiają instalacji
na obrazach z Pythonem 2.

## Instalacja

**1. Pakiet IPK** (najprościej): pobierz `enigma2-plugin-extensions-ytdark_*_all.ipk` z zakładki
[Releases](https://github.com/Marcoxxdev/YTDark/releases/latest), wgraj na dekoder do `/tmp` i wykonaj:

```sh
opkg install /tmp/enigma2-plugin-extensions-ytdark_*_all.ipk
```

**2. Jedna komenda** (telnet/SSH na dekoderze):

```sh
wget -qO- https://raw.githubusercontent.com/Marcoxxdev/YTDark/main/install.sh | sh
```

**3. Ręcznie:** rozpakuj `YTDark.zip` do `/usr/lib/enigma2/python/Plugins/Extensions/`.

Po instalacji zrestartuj interfejs (`killall -9 enigma2`). Wtyczka pojawi się w menu wtyczek.

## Aktualizacje

Wtyczka raz na dobę sprawdza, czy w Releases jest nowsza wersja, i **pyta o zgodę** przed instalacją.
Przed podmianą plików sprawdza sumę SHA-256, składnię kodu i zgodność wersji, robi kopię zapasową
(`Ustawienia → Przywróć poprzednią wersję`). Ręcznie: `Ustawienia → Aktualizacje: sprawdź teraz`.
Automatyczne sprawdzanie można wyłączyć w Ustawieniach.

## Dla autora: jak wydać nową wersję

1. Zmień `__version__` w `YTDark/__init__.py` i dopisz sekcję `## [X.Y.Z]` w `CHANGELOG.md`.
2. `git commit -am "Wersja X.Y.Z"` i `git push`.
3. `git tag vX.Y.Z && git push --tags`

Workflow `Release` sprawdzi, czy tag pasuje do wersji, zbuduje `YTDark.zip`, sumę SHA-256 i pakiet IPK
oraz opublikuje wydanie z opisem z `CHANGELOG.md`. Użytkownicy dostaną propozycję aktualizacji.

Pierwsze uruchomienie repozytorium: `sh tools/set_repo.sh twoj_login/YTDark` (ustawia nazwę repozytorium
w pluginie, README i `install.sh`).

## Bezpieczeństwo i prywatność

- Wtyczka **nie zawiera żadnych danych logowania**. Tokeny konta trafiają tylko na dekoder do
  `/etc/enigma2/ytdark.json` (uprawnienia 600). Nigdy nie dodawaj tego pliku do repozytorium (jest w `.gitignore`).
- Aktualizacje instalują się **tylko po zatwierdzeniu** przez użytkownika. Sumy SHA-256 chronią przed
  uszkodzonym pobraniem, ale nie przed przejęciem Twojego konta GitHub - włącz tam weryfikację dwuetapową.
- Logowanie kodem „jak na TV” jest **nieoficjalne**; YouTube może je zmienić. Zalecane konto dodatkowe.

## Uwagi

Wtyczka korzysta z nieoficjalnego interfejsu YouTube, który bywa zmieniany - gdy przestanie działać,
napisz w Issues (dołącz `cat /tmp/ytdark.log`). Projekt nie jest powiązany z Google ani YouTube.

Licencja: do ustalenia przez autora (bez pliku `LICENSE` obowiązują domyślne prawa autorskie).
