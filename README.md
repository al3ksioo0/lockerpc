# 🔒 Locker PC

![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(x64)-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Installer](https://img.shields.io/badge/Installer-Inno%20Setup-1E293B?style=for-the-badge)
![Release](https://img.shields.io/badge/Release-v1.0.0-16A34A?style=for-the-badge&logo=github&logoColor=white)

**Locker PC** to natywne narzędzie blokujące ekran dla systemu Windows, zaprojektowane z myślą o stabilnej pracy w tle, obsłudze wielu monitorów, bezpiecznej weryfikacji dostępu oraz elastycznym wyzwalaniu blokady.

Projekt udostępniany jest w **dwóch wariantach**, wybieranych bezpośrednio podczas instalacji w kreatorze **Locker PC**:
* 🎙️ **Alexa Lock (`Alexa Lock.exe`)** — tryb integrujący się z **TRIGGERcmd** (umożliwiający zdalne i głosowe blokowanie stacji m.in. przez **Amazon Alexa** oraz **Google Home**), obsługujący również wywołanie wiersza poleceń `--lock` i komunikację lokalną IPC.
* ⌨️ **HotKey_lock (`HotKey_lock.exe`)** — tryb samodzielny dla użytkowników bez asystentów głosowych, wyzwalany globalnym skrótem klawiszowym **`Ctrl + Shift + P`**.

---

## ✨ Kluczowe możliwości

* 🧩 **Wybór wariantu w kreatorze instalacyjnym (`LockerPC_Setup.exe`):** przejrzysty wybór między `Alexa Lock` a `HotKey_lock` podczas instalacji, połączony z konfiguracją regionu, języka, autostartu oraz opcji TRIGGERcmd.
* 🖥️ **Wielomonitorowy ekran blokady:** automatyczne wykrywanie wszystkich aktywnych wyświetlaczy i renderowanie rozmytego tła na bazie aktualnej tapety użytkownika (z konfigurowalnym parametrem `blur_radius`).
* 🛡️ **Bezpieczeństwo i ochrona przed próbami siłowymi:** weryfikacja hasła / PIN-u oparta na algorytmie **SHA-256** z solą kryptograficzną (`PIN_SALT`), licznik nieudanych prób oraz czasowa blokada ponownego logowania po przekroczeniu limitu.
* ⚙️ **Zarządzanie konfiguracją z poziomu GUI:** wbudowane okno ustawień w obu aplikacjach pozwala na zmianę hasła / PIN-u (z walidacją i potwierdzeniem), języka, regionu oraz poziomu rozmycia tła bez ręcznej ingerencji w pliki konfiguracyjne.
* 📌 **Stabilna integracja z zasobnikiem systemowym (Tray):** szybki dostęp do **Ustawień** oraz **Informacji o autorze**, z poprawną obsługą komunikatów Win32 (`WM_NULL`, `SetForegroundWindow`), 64-bitowych typów `ctypes` oraz bezpiecznym kolejkowaniem zdarzeń interfejsu.
* 📁 **Trwała konfiguracja i rejestrowanie zdarzeń:** zapis ustawień w `db/config.json` oraz dziennika zdarzeń w `logs/lock.log`, z automatycznym przejściem na katalog `%LOCALAPPDATA%` w przypadku braku uprawnień zapisu do katalogu instalacji.

---

## 📥 Instalacja

1. Pobierz najnowszy plik **`LockerPC_Setup.exe`** z sekcji **Releases**.
2. Uruchom instalator i wskaż katalog docelowy.
3. Na ekranie konfiguracji **Locker PC** wybierz docelowy wariant:
   * **Alexa Lock** — opcjonalnie zainstaluj TRIGGERcmd Agent i zarejestruj polecenie `lock` w pliku `commands.json`.
   * **HotKey_lock** — aktywuj blokowanie ekranu skrótem **`Ctrl + Shift + P`**.
4. Skonfiguruj region, język oraz opcjonalne uruchamianie wraz ze startem systemu Windows.

---

## 🛠️ Kompilacja ze źródeł

### 1. Budowanie plików wykonywalnych (PyInstaller)
```cmd
pyinstaller --noconsole --onefile --name "Alexa Lock" custom_lock.py
pyinstaller --noconsole --onefile --name "HotKey_lock" hotkey_lock.py
