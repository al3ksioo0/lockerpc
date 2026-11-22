# Locker PC

Lekkie narzędzie do blokowania ekranu w systemie Windows z rozmytym tłem na wielu monitorach, obsługą PIN-u / hasła, zasobnikiem systemowym (tray) oraz pełnym oknem ustawień.

Projekt dostępny jest w **dwóch wersjach**, wybieranych bezpośrednio podczas instalacji w kreatorze **Locker PC**:
* **Alexa Lock (`Alexa Lock.exe`)** — blokada wyzwalana przez **TRIGGERcmd** (np. głosowo przez **Amazon Alexa** lub **Google Home**) albo parametrem `--lock` / lokalnym gniazdem IPC.
* **HotKey_lock (`HotKey_lock.exe`)** — blokada wyzwalana globalnym skrótem klawiszowym **`Ctrl + Shift + P`** (dla osób niekorzystających z Alexy lub Google Home).

---

## Funkcje

* **Dwa tryby działania w jednym instalatorze (`LockerPC_Setup.exe`):** wybór między `Alexa Lock` a `HotKey_lock` na etapie konfiguracji.
* **Wielomonitorowy ekran blokady:** rozmyte tło oparte o aktualną tapetę pulpitu (z regulacją `blur_radius`) wyświetlane na wszystkich podłączonych ekranach.
* **Bezpieczna weryfikacja PIN-u / hasła:** haszowanie **SHA-256** z solą (`PIN_SALT`), limit prób oraz czasowa blokada po przekroczeniu limitu nieudanych prób.
* **Zmiana hasła / PIN-u w ustawieniach:** w obu wersjach (`Alexa Lock` oraz `HotKey_lock`) można zmienić hasło/PIN (z potwierdzeniem), język, region oraz siłę rozmycia bez ręcznej edycji plików.
* **Panel w zasobniku systemowym (Tray):** szybki dostęp do **Ustawień** i **Informacji o autorze** (poprawiona obsługa `WM_NULL` i 64-bitowych typów Win32).
* **Logi i konfiguracja:** konfiguracja w `db/config.json` oraz logi w `logs/lock.log` (z automatycznym fallbackiem do `%LOCALAPPDATA%` przy braku uprawnień zapisu do folderu aplikacji).

---

## Instalacja (zalecana)

1. Pobierz plik **`LockerPC_Setup.exe`** z zakładki **Releases**.
2. Uruchom instalator i wybierz folder docelowy.
3. Na ekranie konfiguracji **Locker PC** wybierz wersję:
   * **Alexa Lock** — opcjonalnie zainstaluj TRIGGERcmd Agent i dodaj komendę `lock` do `commands.json`.
   * **HotKey_lock** — uruchomienie blokady skrótem **`Ctrl + Shift + P`**.
4. Opcjonalnie włącz autostart przy starcie Windows.

---

## Budowanie ze źródeł (Python + PyInstaller + Inno Setup)

### 1. Budowanie plików `.exe`
```cmd
pyinstaller --noconsole --onefile --name "Alexa Lock" custom_lock.py
pyinstaller --noconsole --onefile --name "HotKey_lock" hotkey_lock.py
