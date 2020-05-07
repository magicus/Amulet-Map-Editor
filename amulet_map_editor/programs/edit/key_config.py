import wx
from amulet_map_editor.amulet_wx.simple import SimpleDialog, SimpleScrollablePanel, SimpleChoice
from typing import Dict, Tuple, Optional, Union

ModifierKeyType = str
KeyType = Union[int, str]
ModifierType = Tuple[ModifierKeyType, ...]
SerialisedKeyType = Tuple[ModifierType, KeyType]
KeybindDict = Dict[str, SerialisedKeyType]

MouseLeft = "ML"
MouseMiddle = "MM"
MouseRight = "MR"
MouseWheelScrollUp = "MWSU"
MouseWheelScrollDown = "MWSD"
Control = "CTRL"
Shift = "SHIFT"
Alt = "ALT"

Space = "SPACE"
PageUp = "PAGE_UP"
PageDown = "PAGE_DOWN"

key_string_map = {
    wx.WXK_SHIFT: Shift,
    wx.WXK_ALT: Alt,
    wx.WXK_SPACE: Space,
    wx.WXK_PAGEUP: PageUp,
    wx.WXK_PAGEDOWN: PageDown
}


_presets: Dict[str, KeybindDict] = {
    "right": {
        "up": ((), Space),
        "down": ((), Shift),
        "forwards": ((), "W"),
        "backwards": ((), "S"),
        "left": ((), "A"),
        "right": ((), "D"),
        "box click": ((), MouseLeft),
        "toggle selection mode": ((), MouseRight),
        "toggle mouse lock": ((), MouseMiddle),
        "speed+": ((), MouseWheelScrollUp),
        "speed-": ((), MouseWheelScrollDown)
    },
    "right_laptop": {
        "up": ((), Space),
        "down": ((), Shift),
        "forwards": ((), "W"),
        "backwards": ((), "S"),
        "left": ((), "A"),
        "right": ((), "D"),
        "box click": ((), MouseLeft),
        "toggle selection mode": ((), MouseRight),
        "toggle mouse lock": ((), "F"),
        "speed+": ((), "."),
        "speed-": ((), ",")
    },
    "left": {
        "up": ((), Space),
        "down": ((), ';'),
        "forwards": ((), "I"),
        "backwards": ((), "K"),
        "left": ((), "J"),
        "right": ((), "L"),
        "box click": ((), MouseLeft),
        "toggle selection mode": ((), MouseRight),
        "toggle mouse lock": ((), MouseMiddle),
        "speed+": ((), MouseWheelScrollUp),
        "speed-": ((), MouseWheelScrollDown)
    },
    "left_laptop": {
        "up": ((), Space),
        "down": ((), ';'),
        "forwards": ((), "I"),
        "backwards": ((), "K"),
        "left": ((), "J"),
        "right": ((), "L"),
        "box click": ((), MouseLeft),
        "toggle selection mode": ((), MouseRight),
        "toggle mouse lock": ((), "H"),
        "speed+": ((), "."),
        "speed-": ((), ",")
    }
}

DefaultKeys = _presets["right"]


_mouse_events = {
    wx.EVT_LEFT_DOWN.evtType[0]: MouseLeft,
    wx.EVT_LEFT_UP.evtType[0]: MouseLeft,
    wx.EVT_MIDDLE_DOWN.evtType[0]: MouseMiddle,
    wx.EVT_MIDDLE_UP.evtType[0]: MouseMiddle,
    wx.EVT_RIGHT_DOWN.evtType[0]: MouseRight,
    wx.EVT_RIGHT_UP.evtType[0]: MouseRight
}


def serialise_key_event(evt: Union[wx.KeyEvent, wx.MouseEvent]) -> Optional[SerialisedKeyType]:
    if isinstance(evt, wx.KeyEvent):
        modifier = []
        key = evt.GetUnicodeKey() or evt.GetKeyCode()
        if key == wx.WXK_CONTROL:
            return
        if evt.ControlDown():
            if key in (wx.WXK_SHIFT, wx.WXK_ALT):
                return  # if control is pressed the real key must not be a modifier

            modifier.append(Control)
            if evt.ShiftDown():
                modifier.append(Shift)
            if evt.AltDown():
                modifier.append(Alt)

        if 33 <= key <= 126:
            key = chr(key).upper()
        elif key in key_string_map:
            key = key_string_map[key]
        return tuple(modifier), key
    elif isinstance(evt, wx.MouseEvent):
        key = evt.GetEventType()
        if key in wx.EVT_MOUSEWHEEL.evtType:
            if evt.GetWheelRotation() < 0:
                return (), MouseWheelScrollDown
            elif evt.GetWheelRotation() > 0:
                return (), MouseWheelScrollUp
        elif key in _mouse_events:
            return (), _mouse_events[key]


class KeyConfigModal(SimpleDialog):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, 'Key Select')
        self._key_config = KeyConfig(self)
        self.sizer.Add(
            self._key_config,
            0,
            wx.EXPAND
        )
        self.Layout()

    @property
    def options(self) -> Dict[str, SerialisedKeyType]:
        return self._key_config.options


class KeyConfig(wx.BoxSizer):
    def __init__(self, parent: wx.Window):
        super().__init__(wx.VERTICAL)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Add(top_sizer, 0, wx.EXPAND)
        self._choice = SimpleChoice(parent, list(_presets.keys()))
        top_sizer.Add(self._choice, 1, wx.ALL | wx.EXPAND, 5)
        # some other buttons

        self._options = SimpleScrollablePanel(parent)
        self.Add(self._options, 1, wx.EXPAND)


    @property
    def options(self) -> Dict[str, SerialisedKeyType]:
        return _presets[self._choice.GetCurrentString()]


