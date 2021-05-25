from __future__ import annotations

import ast
import sys
from collections.abc import MutableMapping, MutableSequence
from copy import copy, deepcopy
from functools import partial
from typing import Any, List, Union, Type, Optional

import wx

import amulet_nbt as nbt
from amulet_map_editor.api.wx.ui import simple

from amulet_map_editor.api import image

nbt_resources = image.nbt


class ParsedNBT:
    __slots__ = ["_parent", "_name", "_type"]

    @classmethod
    def is_container(cls) -> bool:
        return False

    @property
    def tag_type(self) -> Type[nbt.AnyNBT]:
        return self._type

    @tag_type.setter
    def tag_type(self, tag_type: Type[nbt.AnyNBT]):
        self._type = tag_type

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def parent(self) -> ParsedNBTContainer:
        return self._parent

    @parent.setter
    def parent(self, parent: ParsedNBTContainer):
        self._parent = parent

    def remove(self):
        raise NotImplementedError

    def display(self):
        raise NotImplementedError

    def update(self, name: str, value: Any):
        raise NotImplementedError

    def build_nbt(self):
        raise NotImplementedError


class ParsedNBTValue(ParsedNBT):
    __slots__ = ParsedNBT.__slots__ + [
        "_value",
    ]

    def __init__(
        self,
        parent: Optional[ParsedNBTContainer],
        name: str,
        value: Union[int, float, str],
        _type: Type[nbt.AnyNBT],
    ):
        self._parent: ParsedNBTContainer = parent
        self._name = name
        self._value = value
        self._type = _type

    def __repr__(self):
        return f"{self._type}({self._name}, {self._value})"

    @property
    def value(self) -> Union[int, float, str]:
        return self._value

    @value.setter
    def value(self, value: Union[int, float, str]):
        self._value = value

    def display(self) -> str:
        return f"{self._name}: {self._value}" if self._name else f"{self._value}"

    def remove(self):
        self._parent.remove_child(self)

    def update(self, name: str, value: Union[int, float, str]):
        self._name = name
        self._value = value

    def build_nbt(self):
        return self._type(self._value)


class ParsedNBTContainer(ParsedNBT):
    __slots__ = ParsedNBT.__slots__ + ["_children"]

    def __init__(
        self, parent: Optional[ParsedNBTContainer], name: str, _type: Type[nbt.AnyNBT]
    ):
        self._parent: ParsedNBTContainer = parent
        self._name = name
        self._type = _type
        self._children: List[Union[ParsedNBTValue, ParsedNBTContainer]] = []

    @classmethod
    def is_container(cls) -> bool:
        return True

    @property
    def children(self) -> List[Union[ParsedNBTValue, ParsedNBTContainer]]:
        return self._children

    def remove(self):
        if self._parent:
            self._parent.remove_child(self)

    def add_child(self, child: Union[ParsedNBTValue, ParsedNBTContainer]):
        self._children.append(child)

    def remove_child(self, child: Union[ParsedNBTValue, ParsedNBTContainer]):
        self._children.remove(child)

    def display(self) -> str:
        return (
            f"{self._name}: {len(self._children)} children"
            if self._name
            else f"{len(self._children)} children"
        )

    def update(self, name: str, _: None):
        self._name = name

    def build_nbt(self):
        container = self._type()

        if isinstance(container, nbt.TAG_Compound):
            for child in self._children:
                container[child.name] = child.build_nbt()
        else:
            for child in self._children:
                container.append(child.build_nbt())

        return container


def parse_nbt(
    _nbt: Union[nbt.NBTFile, nbt.TAG_Compound, MutableMapping],
    parent: ParsedNBTContainer = None,
):
    for key, value in _nbt.items():
        if isinstance(value, MutableMapping):
            new_parent = ParsedNBTContainer(parent, key, type(value))
            parse_nbt(value, new_parent)
            parent.add_child(new_parent)
        elif isinstance(value, MutableSequence):
            new_parent = ParsedNBTContainer(parent, key, type(value))
            for child in value:
                if isinstance(child, (MutableMapping, MutableSequence)):
                    new_new_parent = ParsedNBTContainer(new_parent, "", type(child))
                    parse_nbt(child, new_new_parent)
                    new_parent.add_child(new_new_parent)
                else:
                    new_parent.add_child(
                        ParsedNBTValue(new_parent, "", child.value, type(child))
                    )
            parent.add_child(new_parent)
        else:
            if parent:
                parent.add_child(ParsedNBTValue(parent, key, value.value, type(value)))
            else:
                print(f"Found orphaned NBT: {key}, {value}", file=sys.stderr)


class NBTRadioButton(simple.SimplePanel):
    def __init__(self, parent, nbt_tag_class: str, icon):
        super(NBTRadioButton, self).__init__(parent, wx.HORIZONTAL)

        self.nbt_tag_class: str = nbt_tag_class

        self.radio_button = wx.RadioButton(self, wx.ID_ANY, wx.EmptyString)
        self.add_object(self.radio_button, 0, wx.ALIGN_CENTER | wx.ALL)

        self.tag_bitmap = wx.StaticBitmap(self, wx.ID_ANY, icon)
        self.tag_bitmap.SetToolTip(nbt_tag_class)

        self.add_object(self.tag_bitmap, 0, wx.ALIGN_CENTER | wx.ALL)

    def GetValue(self) -> bool:
        return self.radio_button.GetValue()

    def SetValue(self, val: bool):
        self.radio_button.SetValue(val)


class NBTEditor(simple.SimplePanel):
    def __init__(self, parent, nbt_data: Union[nbt.NBTFile, nbt.TAG_Compound]):
        super(NBTEditor, self).__init__(parent)

        self.image_list = wx.ImageList(16, 16)
        self.image_map = {
            nbt.TAG_Byte: self.image_list.Add(nbt_resources.nbt_tag_byte.bitmap()),
            nbt.TAG_Short: self.image_list.Add(nbt_resources.nbt_tag_short.bitmap()),
            nbt.TAG_Int: self.image_list.Add(nbt_resources.nbt_tag_int.bitmap()),
            nbt.TAG_Long: self.image_list.Add(nbt_resources.nbt_tag_long.bitmap()),
            nbt.TAG_Float: self.image_list.Add(nbt_resources.nbt_tag_float.bitmap()),
            nbt.TAG_Double: self.image_list.Add(nbt_resources.nbt_tag_double.bitmap()),
            nbt.TAG_String: self.image_list.Add(nbt_resources.nbt_tag_string.bitmap()),
            nbt.TAG_Compound: self.image_list.Add(
                nbt_resources.nbt_tag_compound.bitmap()
            ),
            nbt.NBTFile: self.image_list.ImageCount - 1,
            nbt.TAG_List: self.image_list.Add(nbt_resources.nbt_tag_list.bitmap()),
            nbt.TAG_Byte_Array: self.image_list.Add(
                nbt_resources.nbt_tag_array.bitmap()
            ),
            nbt.TAG_Int_Array: self.image_list.ImageCount - 1,
            nbt.TAG_Long_Array: self.image_list.ImageCount - 1,
        }
        self.other = self.image_map[nbt.TAG_String]

        self.tree = wx.TreeCtrl(self, style=wx.TR_DEFAULT_STYLE | wx.EXPAND | wx.ALL)
        self.tree.AssignImageList(self.image_list)

        self.add_object(self.tree, 1, wx.ALL | wx.CENTER | wx.EXPAND)

        self.tree.Bind(wx.EVT_TREE_ITEM_RIGHT_CLICK, self._tree_right_click)

        self._parent = ParsedNBTContainer(None, "", nbt.TAG_Compound)
        parse_nbt(deepcopy(nbt_data), self._parent)

        self._build_tree(self._parent)

    @property
    def nbt(self):
        return self._parent.build_nbt()

    def _generate_menu(self, include_add_tag: bool = False) -> wx.Menu:
        menu = wx.Menu()

        menu_items = [
            wx.MenuItem(menu, text="Edit Tag", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Delete Tag", id=wx.ID_ANY),
        ]

        if include_add_tag:
            menu_items.insert(0, wx.MenuItem(menu, text="Add Tag", id=wx.ID_ANY))

        for menu_item in menu_items:
            menu.Append(menu_item)

        op_map = {
            item.GetId(): item.GetItemLabelText().split()[0].lower()
            for item in menu_items
        }
        menu.Bind(wx.EVT_MENU, lambda evt: self._popup_menu_handler(op_map, evt))

        return menu

    def _tree_right_click(self, evt):
        parsed_nbt = self.tree.GetItemData(evt.GetItem())

        menu = self._generate_menu(isinstance(parsed_nbt, ParsedNBTContainer))
        self.PopupMenu(menu, evt.GetPoint())
        menu.Destroy()
        evt.Skip()

    def _popup_menu_handler(self, op_map, evt):
        op_id = evt.GetId()
        op_name = op_map[op_id]

        if op_name == "add":
            self._add_tag()
        elif op_name == "edit":
            self._edit_tag()
        else:
            self._delete_tag()

    def _add_tag(self):
        parent_element = self.tree.GetFocusedItem()
        parent_tag = self.tree.GetItemData(parent_element)

        def save_callback(new_tag):
            new_tag.parent = parent_tag
            parent_tag.add_child(new_tag)

            self.tree.DeleteChildren(parent_element)
            self._build_sub_tree(parent_element, parent_tag)
            self.tree.SetItemText(parent_element, parent_tag.display())

        add_dialog = NewTagDialog(
            self,
            (
                tag_type.__name__
                for tag_type in self.image_map.keys()
                if "TAG_" in tag_type.__name__
            ),
            save_callback,
        )
        add_dialog.Show()

    def _edit_tag(self):
        selected_element = self.tree.GetFocusedItem()
        parsed_tag = self.tree.GetItemData(selected_element)

        def save_callback(edited_tag):
            parent_element = self.tree.GetItemParent(selected_element)
            parent_tag = parsed_tag.parent

            parsed_tag.update(edited_tag.name, edited_tag.value)

            self.tree.DeleteChildren(parent_element)
            self._build_sub_tree(parent_element, parent_tag)
            self.tree.SetItemText(parent_element, parent_tag.display())

        edit_dialog = EditTagDialog(self, parsed_tag, save_callback)
        edit_dialog.Show()

    def _delete_tag(self):
        selected_element = self.tree.GetFocusedItem()

        parent_element = self.tree.GetItemParent(selected_element)
        parsed_tag = self.tree.GetItemData(selected_element)
        parent_tag = parsed_tag.parent

        parsed_tag.remove()

        self.tree.DeleteChildren(parent_element)

        self._build_sub_tree(parent_element, parent_tag)
        self.tree.SetItemText(parent_element, parent_tag.display())

    def _build_sub_tree(
        self, tree_parent: wx.TreeItemId, nbt_parent: ParsedNBTContainer
    ):
        for nbt_child in sorted(nbt_parent.children, key=lambda t: t.name):
            if isinstance(nbt_child, ParsedNBTContainer):
                new_child = self.tree.AppendItem(tree_parent, nbt_child.display())
                self._build_sub_tree(new_child, nbt_child)
            else:
                new_child = self.tree.AppendItem(tree_parent, nbt_child.display())

            self.tree.SetItemImage(
                new_child, self.image_map.get(nbt_child.tag_type, self.other)
            )
            self.tree.SetItemData(new_child, nbt_child)

    def _build_tree(self, parsed_nbt: ParsedNBTContainer):
        for root_nbt in parsed_nbt.children:
            root = self.tree.AddRoot(root_nbt.name)
            self.tree.SetItemText(root, root_nbt.display())
            self.tree.SetItemImage(
                root,
                self.image_map.get(root_nbt.tag_type, self.image_map[nbt.TAG_Compound]),
                wx.TreeItemIcon_Normal,
            )
            self.tree.SetItemData(root, root_nbt)
            self._build_sub_tree(root, root_nbt)


class NewTagDialog(wx.Frame):
    GRID_ROWS = 3
    GRID_COLUMNS = 4

    def __init__(self, parent, tag_types=None, callback=None):
        super(NewTagDialog, self).__init__(parent, title="Add NBT Tag", size=(500, 280))

        self.callback = callback

        main_panel = simple.SimplePanel(self)

        name_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
        value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
        tag_type_panel = simple.SimplePanel(main_panel)
        button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)

        name_label = wx.StaticText(name_panel, label="Name: ")
        self.name_field = wx.TextCtrl(name_panel)

        name_panel.add_object(name_label, space=0, options=wx.ALL | wx.CENTER)
        name_panel.add_object(self.name_field, space=1, options=wx.ALL | wx.EXPAND)

        value_label = wx.StaticText(value_panel, label="Value: ")
        self.value_field = wx.TextCtrl(value_panel)

        value_panel.add_object(value_label, space=0, options=wx.ALL | wx.CENTER)
        value_panel.add_object(self.value_field, space=1, options=wx.ALL | wx.EXPAND)

        tag_type_sizer = wx.GridSizer(self.GRID_ROWS, self.GRID_COLUMNS, 0, 0)

        self.radio_buttons = []

        for tag_type in tag_types:
            rd_btn = NBTRadioButton(
                tag_type_panel,
                tag_type,
                parent.image_list.GetBitmap(parent.image_map[getattr(nbt, tag_type)]),
            )
            self.radio_buttons.append(rd_btn)
            rd_btn.Bind(
                wx.EVT_RADIOBUTTON, partial(self._handle_radio_button, tag_type)
            )
            tag_type_sizer.Add(rd_btn, 0, wx.ALL, 0)

        tag_type_panel.SetSizerAndFit(tag_type_sizer)

        self.save_button = wx.Button(button_panel, label="Save")
        self.cancel_button = wx.Button(button_panel, label="Cancel")

        button_panel.add_object(self.save_button, space=0)
        button_panel.add_object(self.cancel_button, space=0)

        main_panel.add_object(name_panel, space=0, options=wx.ALL | wx.EXPAND)
        main_panel.add_object(value_panel, space=0, options=wx.ALL | wx.EXPAND)
        main_panel.add_object(tag_type_panel, space=0)
        main_panel.add_object(button_panel, space=0)

        self.save_button.Bind(wx.EVT_BUTTON, self._save)
        self.cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())

        self.SetSize((235, 260))
        self.Layout()

    def _handle_radio_button(self, tag_type: str, _):
        for rd_btn in self.radio_buttons:
            rd_btn.SetValue(rd_btn.nbt_tag_class == tag_type)

        if tag_type in ("TAG_Compound", "TAG_List"):
            self.value_field.Disable()
        elif not self.value_field.Enabled:
            self.value_field.Enable()

    def get_selected_tag_type(self) -> Optional[str]:
        for rd_btn in self.radio_buttons:
            if rd_btn.GetValue():
                return rd_btn.nbt_tag_class
        return None

    def _save(self, _):
        selected_type = self.get_selected_tag_type()
        if not selected_type:
            wx.MessageBox("No tag type selected", "Tag Type Error", wx.OK)
            return
        tag_type = getattr(nbt, selected_type)

        tag_name = self.name_field.GetValue()
        if not tag_name:
            wx.MessageBox("A tag name must be specified", "Tag Name Error", wx.OK)
            return

        if tag_type not in (nbt.TAG_List, nbt.TAG_Compound):
            try:
                value = tag_type(ast.literal_eval(self.value_field.GetValue())).value
            except ValueError:
                wx.MessageBox(
                    f'Couldn\'t cast value "{self.value_field.GetValue()}" to {tag_type.__name__}',
                    "Cast Error",
                    wx.OK,
                )
                return
            except OverflowError:
                wx.MessageBox(
                    f'Value "{self.value_field.GetValue()}" too large for {tag_type.__name__}',
                    "Cast Error",
                    wx.OK,
                )
                return
            except SyntaxError:
                value = tag_type().value
            new_tag = ParsedNBTValue(None, self.name_field.GetValue(), value, tag_type)
        else:
            new_tag = ParsedNBTContainer(None, self.name_field.GetValue(), tag_type)

        self.callback(new_tag)
        self.Close()


class EditTagDialog(wx.Frame):
    def __init__(
        self, parent, tag: Union[ParsedNBTValue, ParsedNBTContainer], callback=None
    ):
        super(EditTagDialog, self).__init__(
            parent, title="Edit NBT Tag", size=(500, 280)
        )

        self.tag = copy(tag)
        self.callback = callback

        main_panel = simple.SimplePanel(self)

        name_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
        value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
        button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)

        name_label = wx.StaticText(name_panel, label="Name: ")
        self.name_field = wx.TextCtrl(name_panel, value=tag.name)

        name_panel.add_object(name_label, space=0, options=wx.ALL | wx.CENTER)
        name_panel.add_object(self.name_field, space=1, options=wx.ALL | wx.EXPAND)

        value_label = wx.StaticText(value_panel, label="Value: ")
        self.value_field = wx.TextCtrl(
            value_panel, value=str(getattr(tag, "value", ""))
        )

        value_panel.add_object(value_label, space=0, options=wx.ALL | wx.CENTER)
        value_panel.add_object(self.value_field, space=1, options=wx.ALL | wx.EXPAND)

        self.save_button = wx.Button(button_panel, label="Save")
        self.cancel_button = wx.Button(button_panel, label="Cancel")

        button_panel.add_object(self.save_button, space=0)
        button_panel.add_object(self.cancel_button, space=0)

        main_panel.add_object(name_panel, space=0, options=wx.ALL | wx.EXPAND)
        main_panel.add_object(value_panel, space=0, options=wx.ALL | wx.EXPAND)
        main_panel.add_object(button_panel, space=0)

        self.save_button.Bind(wx.EVT_BUTTON, self._save)
        self.cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())

        self.SetSize((235, 260))
        self.Layout()

        if tag.tag_type in (nbt.TAG_List, nbt.TAG_Compound):
            self.value_field.Disable()

        if tag.parent.tag_type is nbt.TAG_List:
            self.name_field.Disable()

    def _save(self, _):
        tag_type = self.tag.tag_type

        if tag_type not in (nbt.TAG_List, nbt.TAG_Compound):
            try:
                if tag_type is nbt.TAG_String:
                    value = tag_type(self.value_field.GetValue()).value
                else:
                    value = tag_type(
                        ast.literal_eval(self.value_field.GetValue())
                    ).value
            except ValueError:
                wx.MessageBox(
                    f'Couldn\'t cast value "{self.value_field.GetValue()}" to {tag_type.__name__}',
                    "Cast Error",
                    wx.OK,
                )
                return
            except OverflowError:
                wx.MessageBox(
                    f'Value "{self.value_field.GetValue()}" too large for {tag_type.__name__}',
                    "Cast Error",
                    wx.OK,
                )
                return
            except SyntaxError:
                value = self.tag.value
            self.tag.name = self.name_field.GetValue()
            self.tag.value = value
        else:
            self.tag.name = self.name_field.GetValue()

        self.callback(self.tag)
        self.Close()


if __name__ == "__main__":
    level_dat = nbt.load(
        r"C:\Users\gotharbg\Documents\Python Projects\Amulet-Core\tests\worlds_src\Java 1.13\level.dat"
    )

    app = wx.App()
    frame = wx.Frame(None)
    editor = NBTEditor(frame, level_dat)
    frame.Show()
    app.MainLoop()
    print(editor.nbt)
