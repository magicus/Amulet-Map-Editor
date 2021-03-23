from typing import TYPE_CHECKING, Type, Any, Callable, Tuple
import wx
from OpenGL.GL import (
    glClear,
    GL_DEPTH_BUFFER_BIT,
)
import weakref
import numpy
import math

from amulet.api.data_types import BlockCoordinates

from amulet_map_editor import lang
from amulet_map_editor.api.wx.util.validators import IntValidator
from amulet_map_editor.api.opengl.camera import Projection, Camera
from amulet_map_editor.api.opengl.matrix import rotation_matrix_xy
from amulet_map_editor.programs.edit.api.events import EVT_SELECTION_CHANGE
from amulet_map_editor.programs.edit.api.behaviour.inspect_block_behaviour import (
    InspectBlockBehaviour,
)
from amulet_map_editor.programs.edit.api.behaviour.block_selection_behaviour import (
    BlockSelectionBehaviour,
    EVT_RENDER_BOX_CHANGE,
    RenderBoxChangeEvent,
    EVT_RENDER_BOX_DISABLE_INPUTS,
    EVT_RENDER_BOX_ENABLE_INPUTS,
)
from amulet_map_editor.programs.edit.api.ui.tool import DefaultBaseToolUI
from amulet_map_editor.programs.edit.api.key_config import (
    KeybindGroup,
    ACT_MOVE_UP,
    ACT_MOVE_DOWN,
    ACT_MOVE_FORWARDS,
    ACT_MOVE_BACKWARDS,
    ACT_MOVE_LEFT,
    ACT_MOVE_RIGHT,
    ACT_BOX_CLICK,
)
from amulet_map_editor.api.wx.util.button_input import (
    ButtonInput,
    InputPressEvent,
    EVT_INPUT_PRESS,
    InputReleaseEvent,
    EVT_INPUT_RELEASE,
    InputHeldEvent,
    EVT_INPUT_HELD,
)

if TYPE_CHECKING:
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

_MoveActions = {
    ACT_MOVE_UP,
    ACT_MOVE_DOWN,
    ACT_MOVE_FORWARDS,
    ACT_MOVE_BACKWARDS,
    ACT_MOVE_LEFT,
    ACT_MOVE_RIGHT,
}


class MovementButton(wx.Button):
    """A button that catches actions when pressed."""

    def __init__(
        self,
        parent: wx.Window,
        camera: Camera,
        keybinds: KeybindGroup,
        label: str,
        tooltip: str,
    ):
        super().__init__(parent, label=label)
        self.SetToolTip(tooltip)
        self._camera = weakref.ref(camera)
        self._buttons = ButtonInput(self)
        self._buttons.register_actions(keybinds)
        self._buttons.bind_events()  # this is fine here because we are binding to a custom button not the canvas.
        self.Bind(EVT_INPUT_PRESS, self._on_down)
        self.Bind(EVT_INPUT_RELEASE, self._on_up)
        self.Bind(EVT_INPUT_HELD, self._on_held)
        self._listen = False
        self._timeout = 10

    @property
    def camera(self) -> Camera:
        return self._camera()

    def enable(self):
        self._buttons.enable()

    def disable(self):
        self._buttons.disable()

    def _on_down(self, evt: InputPressEvent):
        if evt.action_id == ACT_BOX_CLICK:
            self._listen = True
        elif evt.action_id in _MoveActions:
            self._timeout = 10

    def _on_up(self, evt: InputReleaseEvent):
        if evt.action_id == ACT_BOX_CLICK:
            self._listen = False

    def _on_held(self, evt: InputHeldEvent):
        if self._listen:
            if self._timeout == 0 or self._timeout == 10:
                x = y = z = 0
                if ACT_MOVE_LEFT in evt.action_ids:
                    x += 1
                if ACT_MOVE_RIGHT in evt.action_ids:
                    x -= 1
                if ACT_MOVE_UP in evt.action_ids:
                    y += 1
                if ACT_MOVE_DOWN in evt.action_ids:
                    y -= 1
                if ACT_MOVE_FORWARDS in evt.action_ids:
                    z += 1
                if ACT_MOVE_BACKWARDS in evt.action_ids:
                    z -= 1
                if any((x, y, z)):
                    self._move(self._rotate((x, y, z)))
            if self._timeout:
                self._timeout -= 1

    def _rotate(self, offset: Tuple[int, int, int]) -> Tuple[int, int, int]:
        x, y, z = offset
        ry = self.camera.rotation[0]
        x, y, z, _ = (
            numpy.round(
                numpy.matmul(rotation_matrix_xy(0, -math.radians(ry)), (x, y, z, 0))
            )
            .astype(int)
            .tolist()
        )
        return x, y, z

    def _move(self, offset: Tuple[int, int, int]):
        pass


class BaseSelectionMoveButton(MovementButton):
    def __init__(
        self,
        parent: wx.Window,
        camera: Camera,
        keybinds: KeybindGroup,
        label: str,
        tooltip: str,
        selection: BlockSelectionBehaviour,
    ):
        super().__init__(parent, camera, keybinds, label, tooltip)
        self._selection = selection


class Point1MoveButton(BaseSelectionMoveButton):
    def _move(self, offset: Tuple[int, int, int]):
        ox, oy, oz = offset
        (x, y, z), point2 = self._selection.active_block_positions
        self._selection.active_block_positions = (x + ox, y + oy, z + oz), point2


class Point2MoveButton(BaseSelectionMoveButton):
    def _move(self, offset: Tuple[int, int, int]):
        ox, oy, oz = offset
        point1, (x, y, z) = self._selection.active_block_positions
        self._selection.active_block_positions = point1, (x + ox, y + oy, z + oz)


class SelectionMoveButton(BaseSelectionMoveButton):
    def _move(self, offset: Tuple[int, int, int]):
        ox, oy, oz = offset
        (x1, y1, z1), (x2, y2, z2) = self._selection.active_block_positions
        self._selection.active_block_positions = (x1 + ox, y1 + oy, z1 + oz), (
            x2 + ox,
            y2 + oy,
            z2 + oz,
        )


class SelectTool(wx.BoxSizer, DefaultBaseToolUI):
    def __init__(self, canvas: "EditCanvas"):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        DefaultBaseToolUI.__init__(self, canvas)

        self._selection = BlockSelectionBehaviour(self.canvas)
        self._inspect_block = InspectBlockBehaviour(self.canvas, self._selection)

        self._button_panel = wx.Panel(canvas)
        button_sizer = wx.BoxSizer(wx.VERTICAL)
        self._button_panel.SetSizer(button_sizer)

        def add_button(
            label: str, tooltip: str, action: Callable[[wx.PyEventBinder], None]
        ):
            button = wx.Button(self._button_panel, label=label)
            button.SetToolTip(tooltip)
            button_sizer.Add(button, 0, wx.ALL | wx.EXPAND, 5)
            button.Bind(wx.EVT_BUTTON, action)

        add_button(
            lang.get("program_3d_edit.select_tool.delete_button"),
            lang.get("program_3d_edit.select_tool.delete_button_tooltip"),
            lambda evt: self.canvas.delete(),
        )
        add_button(
            lang.get("program_3d_edit.select_tool.copy_button"),
            lang.get("program_3d_edit.select_tool.copy_button_tooltip"),
            lambda evt: self.canvas.copy(),
        )
        add_button(
            lang.get("program_3d_edit.select_tool.cut_button"),
            lang.get("program_3d_edit.select_tool.cut_button_tooltip"),
            lambda evt: self.canvas.cut(),
        )
        add_button(
            lang.get("program_3d_edit.select_tool.paste_button"),
            lang.get("program_3d_edit.select_tool.paste_button_tooltip"),
            lambda evt: self.canvas.paste_from_cache(),
        )

        self.Add(self._button_panel, 0, wx.ALIGN_CENTER_VERTICAL)

        self._x1: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_x1"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._y1: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_y1"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._z1: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_z1"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._x1.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._y1.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._z1.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._x1.SetValidator(IntValidator())
        self._y1.SetValidator(IntValidator())
        self._z1.SetValidator(IntValidator())

        self._x2: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_x2"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._y2: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_y2"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._z2: wx.SpinCtrl = self._add_row(
            lang.get("program_3d_edit.select_tool.scroll_point_z2"),
            wx.SpinCtrl,
            min=-30000000,
            max=30000000,
        )
        self._x2.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._y2.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._z2.Bind(wx.EVT_SPINCTRL, self._box_input_change)
        self._x2.SetValidator(IntValidator())
        self._y2.SetValidator(IntValidator())
        self._z2.SetValidator(IntValidator())

        self._x1.Disable()
        self._y1.Disable()
        self._z1.Disable()
        self._x2.Disable()
        self._y2.Disable()
        self._z2.Disable()

        self._x1.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_x1_tooltip")
        )
        self._y1.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_y1_tooltip")
        )
        self._z1.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_z1_tooltip")
        )
        self._x2.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_x2_tooltip")
        )
        self._y2.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_y2_tooltip")
        )
        self._z2.SetToolTip(
            lang.get("program_3d_edit.select_tool.scroll_point_z2_tooltip")
        )

        self._x1.SetBackgroundColour((160, 215, 145))
        self._y1.SetBackgroundColour((160, 215, 145))
        self._z1.SetBackgroundColour((160, 215, 145))

        self._x2.SetBackgroundColour((150, 150, 215))
        self._y2.SetBackgroundColour((150, 150, 215))
        self._z2.SetBackgroundColour((150, 150, 215))

        self._point1_move = Point1MoveButton(
            self._button_panel,
            self.canvas.camera,
            self.canvas.key_binds,
            lang.get("program_3d_edit.select_tool.button_point1"),
            lang.get("program_3d_edit.select_tool.button_point1_tooltip"),
            self._selection,
        )
        self._point1_move.SetBackgroundColour((160, 215, 145))
        self._point1_move.Disable()
        button_sizer.Add(self._point1_move, 0, wx.ALL | wx.EXPAND, 5)

        self._point2_move = Point2MoveButton(
            self._button_panel,
            self.canvas.camera,
            self.canvas.key_binds,
            lang.get("program_3d_edit.select_tool.button_point2"),
            lang.get("program_3d_edit.select_tool.button_point2_tooltip"),
            self._selection,
        )
        self._point2_move.SetBackgroundColour((150, 150, 215))
        self._point2_move.Disable()
        button_sizer.Add(self._point2_move, 0, wx.ALL | wx.EXPAND, 5)

        self._selection_move = SelectionMoveButton(
            self._button_panel,
            self.canvas.camera,
            self.canvas.key_binds,
            lang.get("program_3d_edit.select_tool.button_selection_box"),
            lang.get("program_3d_edit.select_tool.button_selection_box_tooltip"),
            self._selection,
        )
        self._selection_move.SetBackgroundColour((255, 255, 255))
        self._selection_move.Disable()
        button_sizer.Add(self._selection_move, 0, wx.ALL | wx.EXPAND, 5)

    @property
    def name(self) -> str:
        return "Select"

    def bind_events(self):
        super().bind_events()
        self.canvas.Bind(EVT_RENDER_BOX_CHANGE, self._box_renderer_change)
        self.canvas.Bind(EVT_RENDER_BOX_DISABLE_INPUTS, self._disable_inputs)
        self.canvas.Bind(EVT_RENDER_BOX_ENABLE_INPUTS, self._enable_inputs)
        self.canvas.Bind(EVT_SELECTION_CHANGE, self._on_selection_change)
        self._selection.bind_events()
        self._inspect_block.bind_events()

    def enable(self):
        super().enable()
        self._selection.enable()
        self._pull_selection()
        self._point1_move.enable()
        self._point2_move.enable()
        self._selection_move.enable()

    def disable(self):
        super().disable()
        self._point1_move.disable()
        self._point2_move.disable()
        self._selection_move.disable()

    def _add_row(self, label: str, wx_object: Type[wx.Object], **kwargs) -> Any:
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._button_panel.GetSizer().Add(sizer, 0, 0)
        name_text = wx.StaticText(self._button_panel, label=label)
        sizer.Add(name_text, flag=wx.CENTER | wx.ALL | wx.EXPAND, border=5)
        obj = wx_object(self._button_panel, **kwargs)
        sizer.Add(obj, flag=wx.CENTER | wx.ALL, border=5)
        return obj

    def _box_input_change(self, _):
        self._selection.active_block_positions = (
            (self._x1.GetValue(), self._y1.GetValue(), self._z1.GetValue()),
            (self._x2.GetValue(), self._y2.GetValue(), self._z2.GetValue()),
        )

    def _box_renderer_change(self, evt: RenderBoxChangeEvent):
        self._update_selection_inputs(*evt.points)
        evt.Skip()

    def _on_selection_change(self, evt):
        self._pull_selection()
        evt.Skip()

    def _pull_selection(self):
        self._update_selection_inputs(*self._selection.active_block_positions)

    def _update_selection_inputs(
        self, point1: BlockCoordinates, point2: BlockCoordinates
    ):
        (x1, y1, z1), (x2, y2, z2) = point1, point2
        self._x1.SetValue(x1)
        self._y1.SetValue(y1)
        self._z1.SetValue(z1)
        self._x2.SetValue(x2)
        self._y2.SetValue(y2)
        self._z2.SetValue(z2)

    def _enable_inputs(self, evt):
        self._set_scroll_state(True)
        self._point1_move.Enable()
        self._point2_move.Enable()
        self._selection_move.Enable()
        evt.Skip()

    def _disable_inputs(self, evt):
        self._set_scroll_state(False)
        self._point1_move.Disable()
        self._point2_move.Disable()
        self._selection_move.Disable()
        evt.Skip()

    def _set_scroll_state(self, state: bool):
        for scroll in (self._x1, self._y1, self._z1, self._x2, self._y2, self._z2):
            scroll.Enable(state)

    def _on_draw(self, evt):
        self.canvas.renderer.start_draw()
        if self.canvas.camera.projection_mode == Projection.PERSPECTIVE:
            self.canvas.renderer.draw_sky_box()
            glClear(GL_DEPTH_BUFFER_BIT)
        self.canvas.renderer.draw_level()
        self._selection.draw()
        self.canvas.renderer.end_draw()
