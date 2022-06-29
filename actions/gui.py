# -*- coding: utf-8 -*-

# -- stdlib --
from dataclasses import dataclass
from enum import Enum

# -- third party --
import taichi as ti

# -- own --
from .common import register
from utils.misc import hook


# -- code --
NEXT_EVENTS = []
PRESSED_KEYS = set()
LAST_POS = (0.0, 0.0)


class EventTag(Enum):
    PRESS = 1
    RELEASE = 2
    MOTION = 3


@dataclass
class CookedEvent:
    tag: EventTag
    key: str
    modifiers: list


def hook_gui_events():
    EV_MAP = {
        EventTag.PRESS:   ti.GUI.PRESS,
        EventTag.RELEASE: ti.GUI.RELEASE,
        EventTag.MOTION:  ti.GUI.MOTION,
    }

    @hook(ti.GUI)
    def get_key_event(orig, self):
        while has_key_event.orig(self):
            orig(self)  # discard result

        if NEXT_EVENTS:
            e = NEXT_EVENTS.pop(0)
            ev = ti.GUI.Event()
            ev.type = EV_MAP[e.tag]
            ev.key = e.key
            ev.pos = LAST_POS
            ev.modifier = e.modifiers
            return ev

        assert False, 'Should not reach here!'


    @hook(ti.GUI)
    def has_key_event(orig, self):
        orig(self)  # discard result
        return bool(NEXT_EVENTS)


    @hook(ti.GUI)
    def get_cursor_pos(orig, self):
        orig(self)  # discard result
        return LAST_POS


    @hook(ti.GUI)
    def is_pressed(orig, self, *keys):
        orig(self, *keys)  # discard result
        return any(k in PRESSED_KEYS for k in keys)


def hook_ggui_events():
    EV_MAP = {
        EventTag.PRESS:   ti.ui.PRESS,
        EventTag.RELEASE: ti.ui.RELEASE,
    }

    class current_ev:
        def __init__(self):
            self.key = None

        def __get__(self, instance, cls):
            return self

        def __set__(self, instance, value):
            pass

        def _set_key(self, key):
            self.key = key

    ti.ui.Window.event = current_ev()

    @hook(ti.ui.Window)
    def is_pressed(orig, self, *keys):
        orig(self, *keys)  # discard result
        return any(k in PRESSED_KEYS for k in keys)

    @hook(ti.ui.Window)
    def get_cursor_pos(orig, self):
        orig(self)
        return LAST_POS

    @hook(ti.ui.Window)
    def get_event(orig, self, tag=None):
        nonlocal current_ev
        orig(self, tag)
        if not NEXT_EVENTS:
            return False

        e = NEXT_EVENTS.pop(0)

        if e.tag == EventTag.MOTION:
            return False

        ev_tag = EV_MAP[e.tag]
        if tag is None or tag == ev_tag:
            ti.ui.Window.event._set_key(e.key)
            return True
        else:
            return False


hook_gui_events()
hook_ggui_events()


@register('__reset:gui_events')
def reset():
    global LAST_POS
    NEXT_EVENTS[:] = []
    PRESSED_KEYS.clear()
    LAST_POS = (0.0, 0.0)


@register('key-down')
@register('mouse-down')
def key_down(dry, key, modifiers=[]):
    ALL_MODIFIERS = ('Shift', 'Control', 'Alt')
    assert all(m in ALL_MODIFIERS for m in modifiers)

    if dry:
        return

    NEXT_EVENTS.append(
        CookedEvent(
            tag=EventTag.PRESS,
            key=key,
            modifiers=modifiers,
        )
    )
    PRESSED_KEYS.add(key)


@register('key-up')
@register('mouse-up')
def key_up(dry, key, modifiers=[]):
    ALL_MODIFIERS = ('Shift', 'Control', 'Alt')
    assert all(m in ALL_MODIFIERS for m in modifiers)

    if dry:
        return

    NEXT_EVENTS.append(
        CookedEvent(
            tag=EventTag.RELEASE,
            key=key,
            modifiers=modifiers,
        )
    )
    PRESSED_KEYS.remove(key)


@register('key-press')
@register('mouse-click')
def key_press(dry, key, modifiers=[]):
    key_down(dry, key, modifiers)
    key_up(dry, key, modifiers)


@register('move')
def move(dry, position):
    global LAST_POS

    assert len(position) == 2
    assert isinstance(position[0], float)
    assert isinstance(position[1], float)
    assert 0.0 <= position[0] <= 1.0
    assert 0.0 <= position[1] <= 1.0

    position = tuple(position)

    if dry:
        return

    LAST_POS = position

    NEXT_EVENTS.append(
        CookedEvent(
            tag=EventTag.MOTION,
            key=ti.GUI.MOVE,
            modifiers=[],
        )
    )
