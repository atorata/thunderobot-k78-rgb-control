"""
k78tray - Bağımlılıksız Windows sistem tepsisi simgesi (Shell_NotifyIconW, ctypes).

Kendi thread'inde gizli bir pencere ve mesaj döngüsü çalıştırır. Olaylar (show / quit)
thread-safe bir kuyruğa yazılır; tkinter tarafı bu kuyruğu root.after ile okur.
"""
import ctypes
import ctypes.wintypes as W
import queue
import threading

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, WPARAM, LPARAM)

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_USER = 0x0002, 0x0010, 0x0111, 0x0400
WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_LBUTTONUP = 0x0203, 0x0205, 0x0202
WM_TRAY = WM_USER + 20
WM_K78_QUIT = WM_USER + 21
WM_K78_BALLOON = WM_USER + 22
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
IDI_APPLICATION = 32512
MF_STRING, MF_SEPARATOR = 0x0, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100
ID_SHOW, ID_QUIT = 1001, 1002


class GUID(ctypes.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT), ("uFlags", W.UINT),
                ("uCallbackMessage", W.UINT), ("hIcon", W.HICON), ("szTip", W.WCHAR * 128),
                ("dwState", W.DWORD), ("dwStateMask", W.DWORD), ("szInfo", W.WCHAR * 256),
                ("uVersion", W.UINT), ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", W.HICON)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", W.HINSTANCE), ("hIcon", W.HICON),
                ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH), ("lpszMenuName", W.LPCWSTR),
                ("lpszClassName", W.LPCWSTR)]


user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [W.HWND, W.UINT, WPARAM, LPARAM]
user32.CreateWindowExW.restype = W.HWND
user32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.LoadIconW.restype = W.HICON
user32.LoadIconW.argtypes = [W.HINSTANCE, W.LPVOID]
user32.CreatePopupMenu.restype = W.HMENU
user32.AppendMenuW.argtypes = [W.HMENU, W.UINT, ctypes.c_size_t, W.LPCWSTR]
user32.TrackPopupMenu.argtypes = [W.HMENU, W.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.LPVOID]
user32.DestroyMenu.argtypes = [W.HMENU]
user32.PostMessageW.argtypes = [W.HWND, W.UINT, WPARAM, LPARAM]
user32.DestroyWindow.argtypes = [W.HWND]
user32.SetForegroundWindow.argtypes = [W.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
shell32.Shell_NotifyIconW.argtypes = [W.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.ExtractIconW.restype = W.HICON
shell32.ExtractIconW.argtypes = [W.HINSTANCE, W.LPCWSTR, W.UINT]
kernel32.GetModuleHandleW.restype = W.HMODULE


class TrayIcon:
    def __init__(self, tooltip="K78", icon_file=None):
        self.tooltip = tooltip
        self.icon_file = icon_file          # .ico ya da simgeli .exe yolu
        self.events = queue.Queue()
        self.hwnd = None
        self._ready = threading.Event()
        self._wndproc = WNDPROC(self._proc)          # referans tutulmalı
        self._thread = threading.Thread(target=self._run, name="k78-tray", daemon=True)

    def start(self):
        self._thread.start()
        self._ready.wait(3)

    def _nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        return nid

    def _proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            if lparam in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                self.events.put("show")
            elif lparam == WM_RBUTTONUP:
                self._menu()
            return 0
        if msg == WM_K78_BALLOON:
            return 0
        if msg == WM_K78_QUIT:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid()))
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_SHOW, "Göster")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Çıkış")
        pt = W.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(menu)
        if cmd == ID_SHOW:
            self.events.put("show")
        elif cmd == ID_QUIT:
            self.events.put("quit")

    def _run(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "K78TrayWindow"
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "K78", 0, 0, 0, 0, 0, None, None, hinst, None)
        nid = self._nid()
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        hicon = None
        if self.icon_file:
            h = shell32.ExtractIconW(hinst, self.icon_file, 0)
            if h and h != 1:                      # 1 = dosya simge içermiyor
                hicon = h
        nid.hIcon = hicon or user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
        nid.szTip = self.tooltip[:127]
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._ready.set()
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def balloon(self, title, text):
        if not self.hwnd:
            return
        nid = self._nid()
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_K78_QUIT, 0, 0)
            self._thread.join(timeout=2)
