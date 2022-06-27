# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
import taichi as ti

# -- own --
from utils.misc import hook
from .common import register


# -- code --
NEXT_EVENTS = []
PRESSED_KEYS = set()
LAST_POS = (0.0, 0.0)


@hook(ti.GUI)
def get_key_event(orig, self):
    if has_key_event.orig(self):
        orig(self)  # discard result

    if NEXT_EVENTS:
        ev = NEXT_EVENTS.pop(0)
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

    ev = ti.GUI.Event()
    ev.type = ti.GUI.PRESS
    ev.key = key
    ev.pos = LAST_POS
    ev.modifier = modifiers

    NEXT_EVENTS.append(ev)
    PRESSED_KEYS.add(key)


@register('key-up')
@register('mouse-up')
def key_up(dry, key, modifiers=[]):
    ALL_MODIFIERS = ('Shift', 'Control', 'Alt')
    assert all(m in ALL_MODIFIERS for m in modifiers)

    if dry:
        return

    ev = ti.GUI.Event()
    ev.type = ti.GUI.RELEASE
    ev.key = key
    ev.pos = LAST_POS
    ev.modifier = modifiers

    NEXT_EVENTS.append(ev)
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

    ev = ti.GUI.Event()
    ev.type = ti.GUI.MOTION
    ev.key = ti.GUI.MOVE
    ev.pos = tuple(position)
    ev.modifier = []

    NEXT_EVENTS.append(ev)
