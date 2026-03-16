from __future__ import annotations

from typing import Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard


class HotkeyManager(QObject):
    start_selection = pyqtSignal()
    continuous_pressed = pyqtSignal()
    continuous_released = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._listener: Optional[keyboard.Listener] = None
        self._pressed: Set[str] = set()
        self._selection_hotkey_active = False
        self._f8_active = False

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
        except Exception as exc:  # pragma: no cover - platform specific
            self._listener = None
            self.error.emit(f"全局热键启动失败: {exc}")

    def stop(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        finally:
            self._listener = None
            self._pressed.clear()
            self._selection_hotkey_active = False
            self._f8_active = False

    def _normalize_key(self, key: keyboard.KeyCode | keyboard.Key) -> str:
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if key in (
            keyboard.Key.shift,
            keyboard.Key.shift_l,
            keyboard.Key.shift_r,
        ):
            return "shift"
        if key == keyboard.Key.f8:
            return "f8"
        if isinstance(key, keyboard.KeyCode) and key.char:
            return key.char.lower()
        return str(key)

    def _on_press(self, key: keyboard.KeyCode | keyboard.Key) -> None:
        token = self._normalize_key(key)
        self._pressed.add(token)

        if {"ctrl", "shift", "s"}.issubset(self._pressed):
            if not self._selection_hotkey_active:
                self._selection_hotkey_active = True
                self.start_selection.emit()
        else:
            self._selection_hotkey_active = False

        if token == "f8" and not self._f8_active:
            self._f8_active = True
            self.continuous_pressed.emit()

    def _on_release(self, key: keyboard.KeyCode | keyboard.Key) -> None:
        token = self._normalize_key(key)
        self._pressed.discard(token)

        if not {"ctrl", "shift", "s"}.issubset(self._pressed):
            self._selection_hotkey_active = False

        if token == "f8" and self._f8_active:
            self._f8_active = False
            self.continuous_released.emit()

