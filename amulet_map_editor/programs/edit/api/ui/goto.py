from typing import Optional, Tuple
import wx
import re

from amulet_map_editor.api.wx.ui.simple import SimpleDialog
from amulet.api.data_types import PointCoordinates

CoordRegex = re.compile(
    r"^"  # match the start
    r"\s*"  # leading whitespace
    r"(?P<x>-?[0-9]+\.?[0-9]*)"  # the x coordinate
    r"((?:,\s*)|(?:\s+))"  # separator 1
    r"(?P<y>-?[0-9]+\.?[0-9]*)"  # the y coordinate
    r"((?:,\s*)|(?:\s+))"  # separator 2
    r"(?P<z>-?[0-9]+\.?[0-9]*)"  # the z coordinate
    r",?\s*"  # trailing comma and whitespace
    r"$"  # matches the end
)


def show_goto(
    parent: wx.Window, x: float, y: float, z: float
) -> Optional[Tuple[float, float, float]]:
    dialog = GoTo(parent, "Teleport", (x, y, z))
    if dialog.ShowModal() == wx.ID_OK:
        return dialog.location


class GoTo(SimpleDialog):
    def __init__(self, parent: wx.Window, title: str, start: PointCoordinates):
        super().__init__(parent, title, wx.HORIZONTAL)
        x, y, z = start
        x_text = wx.StaticText(self, label="x:")
        self.x = wx.SpinCtrlDouble(self, min=-30000000, max=30000000, initial=x)
        y_text = wx.StaticText(self, label="y:")
        self.x.SetDigits(2)
        self.y = wx.SpinCtrlDouble(self, min=-30000000, max=30000000, initial=y)
        z_text = wx.StaticText(self, label="z:")
        self.y.SetDigits(2)
        self.z = wx.SpinCtrlDouble(self, min=-30000000, max=30000000, initial=z)
        self.z.SetDigits(2)
        self.sizer.Add(x_text, 0, wx.CENTER | wx.ALL, 5)
        self.sizer.Add(self.x, 1, wx.CENTER | wx.ALL, 5)
        self.sizer.Add(y_text, 0, wx.CENTER | wx.ALL, 5)
        self.sizer.Add(self.y, 1, wx.CENTER | wx.ALL, 5)
        self.sizer.Add(z_text, 0, wx.CENTER | wx.ALL, 5)
        self.sizer.Add(self.z, 1, wx.CENTER | wx.ALL, 5)
        self.x.Bind(wx.EVT_CHAR, self._on_text)
        self.y.Bind(wx.EVT_CHAR, self._on_text)
        self.z.Bind(wx.EVT_CHAR, self._on_text)
        self.Fit()

    @property
    def location(self) -> PointCoordinates:
        return self.x.GetValue(), self.y.GetValue(), self.z.GetValue()

    def _on_text(self, evt):
        if evt.ControlDown() and evt.GetKeyCode() == 3:
            # Ctrl+C
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(
                    wx.TextDataObject(
                        "{} {} {}".format(
                            round(self.x.GetValue(), 5),
                            round(self.y.GetValue(), 5),
                            round(self.z.GetValue(), 5),
                        )
                    )
                )
                wx.TheClipboard.Close()
        elif evt.ControlDown() and evt.GetKeyCode() == 22:
            # Ctrl+V
            text = ""
            text_data = wx.TextDataObject()
            if wx.TheClipboard.Open():
                success = wx.TheClipboard.GetData(text_data)
                wx.TheClipboard.Close()
                if success:
                    text = text_data.GetText()
            match = CoordRegex.fullmatch(text)
            if match:
                self.x.SetValue(float(match.group("x")))
                self.y.SetValue(float(match.group("y")))
                self.z.SetValue(float(match.group("z")))
            else:
                evt.Skip()
        else:
            evt.Skip()
