import ctypes
from ctypes import wintypes
import hashlib
import json
import logging
import os
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import winreg
from PIL import Image, ImageFilter, ImageTk

APP_NAME = "Al3ksio Lock"
IPC_HOST = "127.0.0.1"
IPC_PORT = 47881

DEFAULT_PIN = "748080"
PIN_SALT = "al3ksio_lock_salt_2026"
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15
BLUR_RADIUS = 24


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resolve_storage_dirs() -> tuple[str, str]:
    app_dir = get_base_dir()
    db_dir = os.path.join(app_dir, "db")
    logs_dir = os.path.join(app_dir, "logs")

    try:
        os.makedirs(db_dir, exist_ok=True)
        os.makedirs(logs_dir, exist_ok=True)
        test_file = os.path.join(logs_dir, ".write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return db_dir, logs_dir
    except OSError:
        local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        fallback_db = os.path.join(local_app, "Al3ksioLock", "db")
        fallback_logs = os.path.join(local_app, "Al3ksioLock", "logs")
        os.makedirs(fallback_db, exist_ok=True)
        os.makedirs(fallback_logs, exist_ok=True)
        return fallback_db, fallback_logs


DB_DIR, LOGS_DIR = resolve_storage_dirs()
CONFIG_PATH = os.path.join(DB_DIR, "config.json")
LOG_PATH = os.path.join(LOGS_DIR, "lock.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("Al3ksioLock")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

LRESULT = ctypes.c_ssize_t
HHOOK = ctypes.c_void_p
HWND = wintypes.HWND
HMENU = wintypes.HMENU
HINSTANCE = wintypes.HINSTANCE
LPVOID = ctypes.c_void_p

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    ctypes.c_void_p,
    HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = HHOOK

user32.CallNextHookEx.argtypes = [
    HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.DefWindowProcW.argtypes = [
    HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = LRESULT

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    HWND,
    HMENU,
    HINSTANCE,
    LPVOID,
]
user32.CreateWindowExW.restype = HWND

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = HINSTANCE

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_NULL = 0x0000
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

VK_TAB = 0x09
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_ESCAPE = 0x1B

LLKHF_ALTDOWN = 0x20

MONITORINFOF_PRIMARY = 0x00000001
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MF_STRING = 0x00000000
TPM_LEFTALIGN = 0x0000
TPM_BOTTOMALIGN = 0x0020
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

IDI_SHIELD = 32518

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def hash_password(password: str) -> str:
    return hashlib.sha256((PIN_SALT + password).encode("utf-8")).hexdigest()


def default_config() -> dict:
    return {
        "language": "pl",
        "region": "Europe/Warsaw (PL)",
        "pin_hash": hash_password(DEFAULT_PIN),
        "blur_radius": BLUR_RADIUS,
    }


def load_config() -> dict:
    os.makedirs(DB_DIR, exist_ok=True)
    cfg = default_config()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Nie udało się wczytać %s: %s", CONFIG_PATH, exc)
    else:
        save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    logger.info("Zapisano konfigurację w %s", CONFIG_PATH)


def get_current_wallpaper_path() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            wallpaper_path, _ = winreg.QueryValueEx(key, "Wallpaper")
            if wallpaper_path and os.path.exists(wallpaper_path):
                return wallpaper_path
    except OSError:
        pass
    return None


def get_monitors_primary_first() -> list[tuple[int, int, int, int, bool]]:
    monitors: list[tuple[int, int, int, int, bool]] = []

    def _enum_proc(hmonitor, _hdc, _lprc, _dwdata):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            w = r.right - r.left
            h = r.bottom - r.top
            is_primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            if w > 0 and h > 0:
                monitors.append((r.left, r.top, w, h, is_primary))
        return 1

    cb = MONITORENUMPROC(_enum_proc)
    user32.EnumDisplayMonitors(None, None, cb, 0)

    if not monitors:
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        monitors.append((vx, vy, max(vw, 800), max(vh, 600), True))

    monitors.sort(key=lambda m: (0 if m[4] else 1, m[0], m[1]))
    return monitors


def send_ipc_command(cmd: str) -> bool:
    try:
        with socket.create_connection((IPC_HOST, IPC_PORT), timeout=0.6) as sock:
            sock.sendall(cmd.encode("utf-8"))
            return True
    except OSError:
        return False


class SettingsWindow:
    def __init__(self, parent: tk.Tk, cfg: dict):
        self.cfg = cfg

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} — Ustawienia")
        self.win.geometry("480x410")
        self.win.configure(bg="#0c1018")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.after(200, lambda: self.win.attributes("-topmost", False))

        self.lang_var = tk.StringVar(value=self.cfg.get("language", "pl"))
        self.region_var = tk.StringVar(value=self.cfg.get("region", "Europe/Warsaw (PL)"))
        self.blur_var = tk.IntVar(value=int(self.cfg.get("blur_radius", BLUR_RADIUS)))
        self.new_pass_var = tk.StringVar(value="")
        self.confirm_pass_var = tk.StringVar(value="")

        frame = tk.Frame(self.win, bg="#0c1018", padx=22, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Ustawienia blokady",
            font=("Segoe UI", 15, "bold"),
            fg="#ff2e55",
            bg="#0c1018",
        ).pack(anchor="w", pady=(0, 14))

        tk.Label(frame, text="Język:", fg="#cbd5e1", bg="#0c1018").pack(anchor="w")
        ttk.Combobox(
            frame,
            textvariable=self.lang_var,
            values=["pl", "en"],
            state="readonly",
            width=24,
        ).pack(anchor="w", pady=(4, 10))

        tk.Label(frame, text="Region:", fg="#cbd5e1", bg="#0c1018").pack(anchor="w")
        ttk.Combobox(
            frame,
            textvariable=self.region_var,
            values=[
                "Europe/Warsaw (PL)",
                "Europe/Berlin (DE)",
                "Europe/London (UK)",
                "America/New_York (US)",
            ],
            state="readonly",
            width=24,
        ).pack(anchor="w", pady=(4, 10))

        tk.Label(frame, text="Siła rozmycia tła (blur):", fg="#cbd5e1", bg="#0c1018").pack(
            anchor="w"
        )
        tk.Scale(
            frame,
            from_=0,
            to=60,
            orient="horizontal",
            variable=self.blur_var,
            bg="#0c1018",
            fg="#ffffff",
            highlightthickness=0,
            troughcolor="#182030",
            activebackground="#ff2e55",
            length=220,
        ).pack(anchor="w", pady=(2, 10))

        tk.Label(
            frame,
            text="Zmiana hasła / PIN-u (zostaw puste, aby nie zmieniać):",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0c1018",
        ).pack(anchor="w")

        tk.Label(frame, text="Nowe hasło / PIN:", fg="#cbd5e1", bg="#0c1018").pack(anchor="w")
        tk.Entry(
            frame,
            textvariable=self.new_pass_var,
            show="•",
            bg="#182030",
            fg="#ffffff",
            insertbackground="#ff2e55",
            relief="flat",
            width=26,
        ).pack(anchor="w", pady=(3, 8), ipady=4)

        tk.Label(frame, text="Powtórz nowe hasło / PIN:", fg="#cbd5e1", bg="#0c1018").pack(
            anchor="w"
        )
        tk.Entry(
            frame,
            textvariable=self.confirm_pass_var,
            show="•",
            bg="#182030",
            fg="#ffffff",
            insertbackground="#ff2e55",
            relief="flat",
            width=26,
        ).pack(anchor="w", pady=(3, 14), ipady=4)

        tk.Button(
            frame,
            text="Zapisz ustawienia",
            bg="#ff2e55",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=18,
            pady=8,
            command=self._save,
        ).pack(anchor="e")

    def _save(self):
        new_p = self.new_pass_var.get()
        conf_p = self.confirm_pass_var.get()

        if new_p != "" or conf_p != "":
            if new_p.strip() == "":
                messagebox.showwarning(
                    "Błąd hasła", "Nowe hasło / PIN nie może być puste.", parent=self.win
                )
                return
            if new_p != conf_p:
                messagebox.showwarning(
                    "Błąd hasła", "Podane hasła nie są identyczne.", parent=self.win
                )
                return
            self.cfg["pin_hash"] = hash_password(new_p.strip())
            logger.info("Zmieniono hasło / PIN w ustawieniach.")

        self.cfg["language"] = self.lang_var.get()
        self.cfg["region"] = self.region_var.get()
        self.cfg["blur_radius"] = int(self.blur_var.get())
        save_config(self.cfg)
        messagebox.showinfo("Zapisano", "Ustawienia zostały zapisane.", parent=self.win)
        self.win.destroy()


class BackgroundLockDaemon:
    def __init__(self, root: tk.Tk, cfg: dict, start_locked: bool = False):
        self.root = root
        self.cfg = cfg
        self.start_locked = start_locked

        self.root.withdraw()
        self.root.title(APP_NAME)

        self.is_locked = False
        self.unlock_message_active = False
        self.attempts = 0
        self.locked_until = 0.0
        self.hook_handle = None
        self._hook_cb = None
        self._pending_action: str | None = None
        self._settings_win: SettingsWindow | None = None

        self.overlay_windows: list[tk.Toplevel] = []
        self.bg_photos: list[ImageTk.PhotoImage] = []
        self.primary_win: tk.Toplevel | None = None
        self.entry: tk.Entry | None = None
        self.btn: tk.Button | None = None
        self.status_label: tk.Label | None = None
        self.pin_var = tk.StringVar(value="")

        self.tray_hwnd: int | None = None
        self._tray_wndproc = None
        self.tray_added = False

        logger.info("Start demona %s (db=%s, logs=%s)", APP_NAME, DB_DIR, LOGS_DIR)
        self._init_tray_icon()
        self._start_ipc_server()
        self._poll_pending_actions()
        self._countdown_loop()
        self._keep_focus_loop()

        if self.start_locked:
            self.root.after(150, self.safe_show_lock_screen)

    def _poll_pending_actions(self):
        action = self._pending_action
        if action is not None:
            self._pending_action = None
            if action == "lock":
                self.safe_show_lock_screen()
            elif action == "settings":
                self.open_settings()
            elif action == "about":
                self.open_author_info()
        self.root.after(100, self._poll_pending_actions)

    def _init_tray_icon(self):
        wnd_class_name = "Al3ksioLockTrayClass"
        wndproc_type = ctypes.WINFUNCTYPE(
            LRESULT, HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", wndproc_type),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", HINSTANCE),
                ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        def _wnd_proc(hwnd, msg, wparam, lparam):
            try:
                if msg == WM_TRAYICON:
                    if lparam == WM_RBUTTONUP:
                        self._show_tray_menu(hwnd)
                        return 0
                    if lparam == WM_LBUTTONDBLCLK:
                        self._pending_action = "settings"
                        return 0
            except Exception as exc:
                logger.exception("Błąd w _wnd_proc: %s", exc)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._tray_wndproc = wndproc_type(_wnd_proc)
        h_inst = HINSTANCE(kernel32.GetModuleHandleW(None) or 0)

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._tray_wndproc
        wc.hInstance = h_inst
        wc.lpszClassName = wnd_class_name
        user32.RegisterClassW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, wnd_class_name, APP_NAME, 0, 0, 0, 0, 0, None, None, h_inst, None
        )
        self.tray_hwnd = hwnd

        h_icon = user32.LoadIconW(None, IDI_SHIELD)
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = h_icon
        nid.szTip = APP_NAME

        if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            self.tray_added = True

    def _show_tray_menu(self, hwnd: int):
        h_menu = user32.CreatePopupMenu()
        user32.AppendMenuW(h_menu, MF_STRING, 1001, "Otwórz Ustawienia")
        user32.AppendMenuW(h_menu, MF_STRING, 1002, "Informacje o autorze")

        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)

        cmd_id = user32.TrackPopupMenu(
            h_menu,
            TPM_LEFTALIGN | TPM_BOTTOMALIGN | TPM_RETURNCMD | TPM_NONOTIFY,
            pt.x,
            pt.y,
            0,
            hwnd,
            None,
        )
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(h_menu)

        if cmd_id == 1001:
            self._pending_action = "settings"
        elif cmd_id == 1002:
            self._pending_action = "about"

    def open_settings(self):
        if self._settings_win is not None and self._settings_win.win.winfo_exists():
            self._settings_win.win.lift()
            self._settings_win.win.focus_force()
            return
        self._settings_win = SettingsWindow(self.root, self.cfg)

    def open_author_info(self):
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.attributes("-topmost", True)
        messagebox.showinfo(
            "Informacje o autorze",
            f"{APP_NAME}\nAutor: Aleks (Al3ksio)\nEkran blokady z PIN-em, obsługą wielu monitorów i TRIGGERcmd.",
            parent=top,
        )
        top.destroy()

    def _start_ipc_server(self):
        def _server_loop():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv.bind((IPC_HOST, IPC_PORT))
                srv.listen(5)
                while True:
                    conn, _ = srv.accept()
                    with conn:
                        data = conn.recv(64).decode("utf-8", errors="ignore").strip()
                        if data == "LOCK":
                            logger.info("Odebrano komendę IPC LOCK.")
                            self._pending_action = "lock"
            except OSError as exc:
                logger.warning("Błąd gniazda IPC: %s", exc)
            finally:
                try:
                    srv.close()
                except OSError:
                    pass

        threading.Thread(target=_server_loop, daemon=True).start()

    def _load_blurred_wallpaper(self) -> Image.Image | None:
        wp = get_current_wallpaper_path()
        if not wp:
            return None
        try:
            radius = int(self.cfg.get("blur_radius", BLUR_RADIUS))
            img = Image.open(wp).convert("RGB")
            if radius > 0:
                return img.filter(ImageFilter.GaussianBlur(radius=radius))
            return img
        except Exception as exc:
            logger.warning("Błąd ładowania tapety: %s", exc)
            return None

    def _make_monitor_photo(
        self, base_blur: Image.Image | None, width: int, height: int
    ) -> ImageTk.PhotoImage:
        if base_blur is not None and base_blur.width > 0 and base_blur.height > 0:
            img_ratio = base_blur.width / base_blur.height
            mon_ratio = width / height
            if img_ratio > mon_ratio:
                new_h = height
                new_w = max(1, int(new_h * img_ratio))
            else:
                new_w = width
                new_h = max(1, int(new_w / img_ratio))
            resized = base_blur.resize((new_w, new_h), Image.Resampling.BILINEAR)
            left = max(0, (new_w - width) // 2)
            top = max(0, (new_h - height) // 2)
            cropped = resized.crop((left, top, left + width, top + height))
        else:
            cropped = Image.new("RGB", (width, height), (10, 13, 20))

        dark = Image.new("RGB", (width, height), (0, 0, 0))
        blended = Image.blend(cropped, dark, alpha=0.35)
        return ImageTk.PhotoImage(blended, master=self.root)

    def safe_show_lock_screen(self):
        try:
            self.show_lock_screen()
        except Exception as exc:
            logger.exception("Krytyczny błąd podczas pokazywania ekranu blokady: %s", exc)
            self.is_locked = False
            self.uninstall_hook()

    def show_lock_screen(self):
        if self.is_locked:
            return

        self.is_locked = True
        self.unlock_message_active = False
        self.pin_var.set("")
        self.overlay_windows.clear()
        self.bg_photos.clear()

        monitors = get_monitors_primary_first()
        base_blur = self._load_blurred_wallpaper()

        for idx, (mx, my, mw, mh, is_primary) in enumerate(monitors):
            win = tk.Toplevel(self.root)
            win.geometry(f"{mw}x{mh}+{mx}+{my}")
            win.configure(bg="#090b10")
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.protocol("WM_DELETE_WINDOW", lambda: None)

            photo = self._make_monitor_photo(base_blur, mw, mh)
            self.bg_photos.append(photo)

            bg_lbl = tk.Label(win, image=photo, borderwidth=0)
            bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)

            if is_primary or idx == 0:
                self.primary_win = win
                self._build_pin_card(win)

            self.overlay_windows.append(win)

        self.install_hook()
        logger.info("Aktywowano ekran blokady na %d monitorach.", len(monitors))
        if self.entry is not None:
            self.entry.focus_force()

    def _build_pin_card(self, parent: tk.Toplevel):
        card_bg = "#10141e"
        card = tk.Frame(
            parent,
            bg=card_bg,
            padx=36,
            pady=32,
            highlightbackground="#2b3348",
            highlightthickness=1,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            card,
            text="EKRAN ZABLOKOWANY",
            font=("Segoe UI", 24, "bold"),
            fg="#ff2e55",
            bg=card_bg,
        ).pack(pady=(0, 6))

        tk.Label(
            card,
            text="Wpisz hasło / PIN, aby odblokować",
            font=("Segoe UI", 11),
            fg="#b8c2d1",
            bg=card_bg,
        ).pack(pady=(0, 18))

        self.entry = tk.Entry(
            card,
            textvariable=self.pin_var,
            show="•",
            font=("Segoe UI", 20),
            width=14,
            justify="center",
            bg="#1a2030",
            fg="#ffffff",
            insertbackground="#ff2e55",
            relief="flat",
        )
        self.entry.pack(ipady=8, pady=(0, 14))
        self.entry.bind("<Return>", lambda _e: self.verify_pin())

        self.btn = tk.Button(
            card,
            text="ODBLOKUJ",
            font=("Segoe UI", 11, "bold"),
            bg="#ff2e55",
            fg="#ffffff",
            activebackground="#d91e42",
            activeforeground="#ffffff",
            relief="flat",
            padx=24,
            pady=10,
            command=self.verify_pin,
        )
        self.btn.pack()

        self.status_label = tk.Label(
            card,
            text="",
            font=("Segoe UI", 11, "bold"),
            fg="#ff6b81",
            bg=card_bg,
        )
        self.status_label.pack(pady=(12, 0))

    def _keyboard_proc(self, n_code, w_param, l_param):
        try:
            if self.is_locked and n_code >= 0 and w_param in (
                WM_KEYDOWN,
                WM_KEYUP,
                WM_SYSKEYDOWN,
                WM_SYSKEYUP,
            ):
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode
                alt_pressed = bool(kb.flags & LLKHF_ALTDOWN) or bool(
                    user32.GetAsyncKeyState(VK_MENU) & 0x8000
                )
                if (alt_pressed and vk in (VK_TAB, VK_ESCAPE)) or vk in (VK_LWIN, VK_RWIN):
                    return 1
        except Exception:
            pass

        return user32.CallNextHookEx(self.hook_handle, n_code, w_param, l_param)

    def install_hook(self):
        if self.hook_handle:
            return
        self._hook_cb = LowLevelKeyboardProc(self._keyboard_proc)
        h_mod = HINSTANCE(kernel32.GetModuleHandleW(None) or 0)
        self.hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._hook_cb, h_mod, 0
        )

    def uninstall_hook(self):
        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None
            self._hook_cb = None

    def _keep_focus_loop(self):
        if self.is_locked and not self.unlock_message_active:
            for win in self.overlay_windows:
                if win.winfo_exists():
                    win.lift()
                    win.attributes("-topmost", True)
            if (
                self.entry
                and self.entry.winfo_exists()
                and time.monotonic() >= self.locked_until
            ):
                self.entry.focus_set()
        self.root.after(250, self._keep_focus_loop)

    def _countdown_loop(self):
        if self.is_locked and not self.unlock_message_active and self.locked_until > 0.0:
            now = time.monotonic()
            if now < self.locked_until:
                rem = int(self.locked_until - now) + 1
                if self.status_label:
                    self.status_label.config(
                        text=f"Za dużo prób. Odczekaj {rem} s...", fg="#ff6b81"
                    )
            else:
                self.locked_until = 0.0
                if self.entry:
                    self.entry.config(state="normal")
                    self.entry.focus_set()
                if self.btn:
                    self.btn.config(state="normal")
                if self.status_label:
                    self.status_label.config(
                        text="Możesz ponownie wpisać hasło / PIN.", fg="#6ee7b7"
                    )
        self.root.after(200, self._countdown_loop)

    def verify_pin(self):
        if not self.is_locked or self.unlock_message_active:
            return

        now = time.monotonic()
        if now < self.locked_until:
            rem = int(self.locked_until - now) + 1
            if self.status_label:
                self.status_label.config(
                    text=f"Za dużo prób. Odczekaj {rem} s...", fg="#ff6b81"
                )
            self.pin_var.set("")
            return

        self.locked_until = 0.0
        entered = self.pin_var.get().strip()
        expected = self.cfg.get("pin_hash") or hash_password(DEFAULT_PIN)

        if hash_password(entered) == expected:
            logger.info("Poprawne hasło / PIN — odblokowanie po komunikacie 'Zalogowano!'.")
            self.unlock_message_active = True
            if self.entry:
                self.entry.config(state="disabled")
            if self.btn:
                self.btn.config(state="disabled")
            if self.status_label:
                self.status_label.config(text="Zalogowano!", fg="#4ade80")
            self.root.after(2000, self._finish_unlock)
        else:
            self.attempts += 1
            self.pin_var.set("")
            if self.attempts >= MAX_ATTEMPTS:
                self.locked_until = now + LOCKOUT_SECONDS
                self.attempts = 0
                logger.warning(
                    "Przekroczono limit %d prób. Blokada na %d s.",
                    MAX_ATTEMPTS,
                    LOCKOUT_SECONDS,
                )
                if self.entry:
                    self.entry.config(state="disabled")
                if self.btn:
                    self.btn.config(state="disabled")
                if self.status_label:
                    self.status_label.config(
                        text=f"Błędne hasło / PIN. Blokada prób na {LOCKOUT_SECONDS} s.",
                        fg="#ff6b81",
                    )
            else:
                left = MAX_ATTEMPTS - self.attempts
                logger.warning("Nieprawidłowe hasło / PIN. Pozostało prób: %d.", left)
                if self.status_label:
                    self.status_label.config(
                        text=f"Nieprawidłowe hasło / PIN. Pozostało prób: {left}.",
                        fg="#ff6b81",
                    )

    def _finish_unlock(self):
        self.uninstall_hook()
        for win in self.overlay_windows:
            if win.winfo_exists():
                win.destroy()
        self.overlay_windows.clear()
        self.bg_photos.clear()
        self.primary_win = None
        self.entry = None
        self.btn = None
        self.status_label = None
        self.is_locked = False
        self.unlock_message_active = False

    def cleanup_tray(self):
        self.uninstall_hook()
        if self.tray_added and self.tray_hwnd:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.tray_hwnd
            nid.uID = 1
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            self.tray_added = False


def main():
    want_lock = "--lock" in sys.argv

    if want_lock and send_ipc_command("LOCK"):
        return

    cfg = load_config()
    root = tk.Tk()
    app = BackgroundLockDaemon(root, cfg, start_locked=want_lock)
    try:
        root.mainloop()
    finally:
        app.cleanup_tray()
        logger.info("Zamknięto %s.", APP_NAME)


if __name__ == "__main__":
    main()