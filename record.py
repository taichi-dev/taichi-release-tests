# -*- coding: utf-8 -*-

# -- stdlib --
import argparse
import importlib
import importlib.util
import logging
import os
import pathlib
import random
import sys

# -- third party --
import numpy as np
import taichi as ti

# -- own --
from utils.misc import hook


# -- code --
log = logging.getLogger('main')


@hook(ti)
def init(orig, arch=None, **kwargs):
    kwargs['random_seed'] = 23333
    np.random.seed(23333)
    random.seed(23333)
    return orig(arch=arch, **kwargs)


LAST_POS = (0, 0)
LAST_FRAME = 0
PRESSED_KEYS = set()


@hook(ti.GUI)
def get_key_event(orig, self):
    global LAST_POS, LAST_FRAME
    ev = orig(self)
    frame = self.frame

    if ev.type == ti.GUI.MOTION:
        if LAST_POS == ev.pos:
            return ev
        action = 'move'
        LAST_POS = p = ev.pos
        OUTPUT.write(
            f'  - {{frame: {frame-LAST_FRAME}, '
            f'action: {action}, '
            f'position: [{p[0]:.3}, {p[1]:.3}]}}\n'
        )
        LAST_FRAME = frame
        return ev

    if ev.key in (ti.GUI.LMB, ti.GUI.MMB, ti.GUI.RMB):
        prefix = 'mouse-'
    else:
        prefix = 'key-'

    if ev.type == ti.GUI.PRESS:
        suffix = 'down'
        PRESSED_KEYS.add(ev.key)
    elif ev.type == ti.GUI.RELEASE:
        suffix = 'up'
        PRESSED_KEYS.discard(ev.key)
    else:
        suffix = 'BUG'

    action = prefix + suffix
    key = "' '" if ev.key == ' ' else ev.key
    OUTPUT.write(f'  - {{frame: {frame-LAST_FRAME}, action: {action}, key: {key}}}\n')

    LAST_FRAME = self.frame
    return ev


def process_event_frame(frames, tag, ev):
    key = ev.key

    if key in (ti.ui.LMB, ti.ui.MMB, ti.ui.RMB):
        prefix = 'mouse-'
    else:
        prefix = 'key-'

    if tag == ti.ui.RELEASE:
        suffix = 'up'
        PRESSED_KEYS.discard(key)
    else:
        suffix = 'down'
        PRESSED_KEYS.add(key)

    action = prefix + suffix

    key = "' '" if key == ' ' else key
    OUTPUT.write(f'  - {{frame: {frames}, action: {action}, key: {key}}}\n')


@hook(ti.ui.Window)
def get_event(orig, self, tag=None):
    global LAST_FRAME

    has_event = orig(self, tag)
    if not has_event:
        return has_event

    process_event_frame(self.frame - LAST_FRAME, tag, self.event)
    LAST_FRAME = self.frame

    return has_event


@hook(ti.ui.Window)
def get_events(orig, self, tag=None):
    global LAST_FRAME
    rst = orig(self, tag)

    for ev in rst:
        process_event_frame(self.frame - LAST_FRAME, tag, ev)
        LAST_FRAME = self.frame

    return rst


@hook(ti.ui.Window)
def get_cursor_pos(orig, self, _=None):
    global LAST_POS, LAST_FRAME
    pos = orig(self)
    if pos != LAST_POS:
        LAST_POS = pos
        OUTPUT.write(f'  - {{frame: {self.frame-LAST_FRAME}, action: move, position: [{pos[0]:.3}, {pos[1]:.3}]}}\n')
        LAST_FRAME = self.frame
    return LAST_POS


def sync_key_state(frame, key, pressed):
    global LAST_FRAME

    if key in (ti.ui.LMB, ti.ui.MMB, ti.ui.RMB):
        prefix = 'mouse-'
    else:
        prefix = 'key-'

    if key in PRESSED_KEYS and not pressed:
        PRESSED_KEYS.discard(key)
        key = "' '" if key == ' ' else key
        OUTPUT.write(f'  - {{frame: {frame-LAST_FRAME}, action: {prefix}up, key: {key}}}\n')
        LAST_FRAME = frame

    if key not in PRESSED_KEYS and pressed:
        PRESSED_KEYS.add(key)
        key = "' '" if key == ' ' else key
        OUTPUT.write(f'  - {{frame: {frame-LAST_FRAME}, action: {prefix}down, key: {key}}}\n')
        LAST_FRAME = frame


@hook(ti.ui.Window)
def show(orig, self, _=None):
    for k in list(PRESSED_KEYS):
        sync_key_state(self.frame, k, is_pressed.orig(self, k))

    orig(self)
    self.frame += 1


ti.ui.Window.frame = 0


@hook(ti.ui.Window)
def is_pressed(orig, self, *keys):
    rst = False
    for key in keys:
        v = orig(self, key)
        rst = rst or v
        sync_key_state(self.frame, key, v)

    return rst


def run(program, args, output):
    global OUTPUT

    ti.reset()

    path = pathlib.Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT = open(output, 'w')

    lines = [
        r'---',
        f'- path: {program}',
        f'  args: {args}',
        r'  steps:',
    ]

    for l in lines:
        OUTPUT.write(l + '\n')


    spec = importlib.util.spec_from_file_location('__main__', program)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.argv = [program] + args
    wd = pathlib.Path(program).resolve().parent
    orig = os.getcwd()
    try:
        os.chdir(wd)
        spec.loader.exec_module(module)
    except BaseException:
        pass
    finally:
        os.chdir(orig)

    OUTPUT.write('  - {frame: 30, action: succeed}\n')


def main():
    parser = argparse.ArgumentParser('taichi-release-tests-runner')
    parser.add_argument('program')
    parser.add_argument('output')
    parser.add_argument('args', nargs='...')
    options = parser.parse_args()
    run(options.program, options.args, options.output)


if __name__ == '__main__':
    main()
