"""Session/user identity independent of executable path; no Qt import at bootstrap."""
import hashlib
import os
import tempfile
from pathlib import Path


class InstanceGuard:
    def __init__(self, namespace='manager-v1'):
        self.primary = False
        self.handle = None
        self.socket = None
        self.stream = None
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes as w
            self.ctypes, self.w = ctypes, w
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.user = ctypes.WinDLL('user32', use_last_error=True)
            self.kernel.CreateMutexW.argtypes = [w.LPVOID, w.BOOL, w.LPCWSTR]
            self.kernel.CreateMutexW.restype = w.HANDLE
            self.kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
            self.kernel.WaitForSingleObject.restype = w.DWORD
            self.kernel.ReleaseMutex.argtypes = [w.HANDLE]
            self.kernel.CloseHandle.argtypes = [w.HANDLE]
            buffer, size = ctypes.create_unicode_buffer(256), w.DWORD(256)
            advapi = ctypes.WinDLL('advapi32', use_last_error=True)
            advapi.GetUserNameW.argtypes = [w.LPWSTR, ctypes.POINTER(w.DWORD)]
            if not advapi.GetUserNameW(buffer, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            identity = buffer.value.casefold()
        else:
            identity = f'{os.getuid()}:{os.environ.get("XDG_SESSION_ID", os.environ.get("DISPLAY", "default"))}'
        self.key = hashlib.sha256((identity + ':' + namespace).encode()).hexdigest()[:24]
        self.property_name = 'EDPD.Manager.' + self.key

    def acquire(self):
        if os.name == 'nt':
            self.handle = self.kernel.CreateMutexW(None, True, 'Local\\EDPD.Manager.' + self.key)
            if not self.handle:
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            existed = self.ctypes.get_last_error() == 183
            if not existed:
                self.primary = True
            else:
                # A crash abandons ownership. Do not leave a stale lock behind.
                self.primary = self.kernel.WaitForSingleObject(self.handle, 0) in (0, 0x80)
            return self.primary
        import fcntl
        import socket
        folder = Path(tempfile.gettempdir()) / f'edpd-instance-{os.getuid()}'
        folder.mkdir(mode=0o700, exist_ok=True)
        if folder.stat().st_uid != os.getuid():
            raise PermissionError('Az EDPD példánykönyvtára más felhasználóé.')
        self.socket_path = folder / (self.key + '.sock')
        self.stream = (folder / (self.key + '.lock')).open('a+b')
        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        self.primary = True
        self.socket_path.unlink(missing_ok=True)
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(8)
        self.socket.setblocking(False)
        return True

    def tag_window(self, window, kind='main'):
        if os.name == 'nt':
            self.user.IsWindow.argtypes = [self.w.HWND]
            if not self.user.IsWindow(int(window.winId())):
                from PySide2.QtWidgets import QApplication
                if QApplication.platformName() == 'offscreen':
                    return
            self.user.SetPropW.argtypes = [self.w.HWND, self.w.LPCWSTR, self.w.HANDLE]
            self.user.SetPropW.restype = self.w.BOOL
            if not self.user.SetPropW(int(window.winId()), self.property_name + '.' + kind, 1):
                raise self.ctypes.WinError(self.ctypes.get_last_error())

    def notify_existing(self, show_notice=True):
        if os.name != 'nt':
            import socket
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(.5)
                    client.connect(str(self.socket_path))
                    client.sendall(b'activate')
                    state = client.recv(32)
                return {'peer_state': state.decode('ascii'), 'activated': True}
            except OSError:
                return {'peer_state': 'initializing', 'activated': False}
        c, w = self.ctypes, self.w
        self.user.GetPropW.argtypes = [w.HWND, w.LPCWSTR]
        self.user.GetPropW.restype = w.HANDLE
        callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.user.EnumWindows.argtypes = [callback_type, w.LPARAM]
        found = {}
        def inspect(hwnd, _):
            for kind in ('main', 'splash'):
                if self.user.GetPropW(hwnd, self.property_name + '.' + kind):
                    found[kind] = hwnd
            return True
        self.user.EnumWindows(callback_type(inspect), 0)
        hwnd = found.get('main')
        activated = False
        if hwnd:
            self.user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
            pid = w.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, c.byref(pid))
            self.user.AllowSetForegroundWindow.argtypes = [w.DWORD]
            self.user.AllowSetForegroundWindow(pid.value)
            self.user.IsIconic.argtypes = [w.HWND]
            self.user.ShowWindow.argtypes = [w.HWND, c.c_int]
            self.user.SetForegroundWindow.argtypes = [w.HWND]
            self.user.SetForegroundWindow.restype = w.BOOL
            if self.user.IsIconic(hwnd):
                self.user.ShowWindow(hwnd, 9)
            activated = bool(self.user.SetForegroundWindow(hwnd))
        elif show_notice:
            self.starting_notice()
        return {'peer_state': 'main_visible' if hwnd else 'initializing', 'activated': activated}

    def starting_notice(self):
        """Small native, auto-closing notification; does not load a second Qt app."""
        import time
        c, w = self.ctypes, self.w
        self.user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
            c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
        self.user.CreateWindowExW.restype = w.HWND
        self.user.GetSystemMetrics.argtypes = [c.c_int]
        width, height = 430, 95
        x = (self.user.GetSystemMetrics(0) - width) // 2
        y = (self.user.GetSystemMetrics(1) - height) // 2
        hwnd = self.user.CreateWindowExW(0x88, 'STATIC',
            'EDPD – Postai dokumentumkezelő\nAz EDPD már indul…',
            0x90000001, x, y, width, height, None, None, None, None)
        if not hwnd:
            return
        self.user.UpdateWindow.argtypes = [w.HWND]
        self.user.DestroyWindow.argtypes = [w.HWND]
        self.user.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
        self.user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
        self.user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
        self.user.DispatchMessageW.restype = w.LPARAM
        self.user.UpdateWindow(hwnd)
        message = w.MSG()
        until = time.monotonic() + 1.2
        try:
            while time.monotonic() < until:
                while self.user.PeekMessageW(c.byref(message), None, 0, 0, 1):
                    self.user.TranslateMessage(c.byref(message))
                    self.user.DispatchMessageW(c.byref(message))
                time.sleep(.01)
        finally:
            self.user.DestroyWindow(hwnd)

    def poll_activation(self, window):
        if self.socket is None:
            return
        while True:
            try:
                client, _ = self.socket.accept()
            except BlockingIOError:
                return
            with client:
                client.settimeout(.2)
                try:
                    request = client.recv(16)
                except OSError:
                    continue
                if request == b'activate':
                    if window.isMinimized():
                        window.showNormal()
                    window.raise_()
                    window.activateWindow()
                    try:
                        client.sendall(b'main_visible')
                    except OSError:
                        pass

    def close(self):
        if os.name == 'nt' and self.handle:
            if self.primary:
                self.kernel.ReleaseMutex(self.handle)
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        if self.socket:
            self.socket.close()
            self.socket_path.unlink(missing_ok=True)
            self.socket = None
        if self.stream:
            self.stream.close()
            self.stream = None
        self.primary = False
