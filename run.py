# -*- coding: utf-8 -*-

# -- stdlib --
from pathlib import Path
import random
import importlib
import importlib.util
import numpy as np  # pyright: ignore
import inspect
import logging
import os
import sys

# -- third party --
import taichi as ti  # pyright: ignore
import yaml

# -- own --
from args import parse_args, options
from actions import ACTIONS
from exceptions import Success
from utils import logconfig
from utils.misc import hook


# -- code --
log = logging.getLogger('main')


STATE = {
    'current_test': None,
    'steps_iter': None,
    'step': None,
    'last_step_frame': 0,
}

ACTIVE_GUI = set()
ACTIVE_GGUI = set()


def next_step():
    assert STATE['steps_iter']
    try:
        STATE['step'] = next(STATE['steps_iter'])
    except StopIteration:
        STATE['step'] = None
        raise Success


def run_step(gui, test, step, dry=False):
    if 'action' not in step:
        raise ValueError('Step %s has no action!', step)
    if step['action'] not in ACTIONS:
        raise ValueError('Unknown action %s!', step['action'])

    action = ACTIONS[step['action']]
    args = {**step, 'dry': dry, 'gui': gui, 'current_test': test}
    args = {k: v for k, v in args.items() if k in action.params}

    if dry and 'dry' not in args:
        return

    action(**args)


def try_run_step(self):
    test = STATE['current_test']
    step = STATE['step']
    if step is None:
        return False

    fr = step['frame']
    if isinstance(fr, str) and fr.startswith('@'):
        fr = int(fr[1:])
    else:
        fr = STATE['last_step_frame'] + int(fr)

    if self.frame < fr:
        return False

    STATE['last_step_frame'] = self.frame
    run_step(self, test, step)
    next_step()
    return True


@hook(ti.GUI, 'show')
def gui_show(orig, self, _=None):
    ACTIVE_GUI.add(self)
    while try_run_step(self):
        pass
    orig(self)


@hook(ti.ui.Window, 'show')
def ggui_show(orig, self, _=None):
    ACTIVE_GGUI.add(self)
    while try_run_step(self):
        pass
    orig(self)
    self.frame += 1


ti.ui.Window.frame = 0


@hook(ti)
def init(orig, arch=None, **kwargs):
    kwargs['random_seed'] = 23333
    print('hook init')
    return orig(arch=arch, **kwargs)


def run(test):
    log.info('Running %s...', test['path'])
    ti.reset()
    np.random.seed(23333)
    random.seed(23333)

    STATE['current_test'] = test
    STATE['steps_iter'] = iter(test['steps'])
    STATE['last_step_frame'] = 0
    next_step()

    for act in ACTIONS:
        if act.startswith('__reset:'):
            ACTIONS[act]()

    spec = importlib.util.spec_from_file_location('testee', test['path'])
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        sys.argv = [test['path']] + test['args']
        spec.loader.exec_module(module)
        if main := getattr(module, 'main', None):
            main()
    except Success:
        pass

    for gui in ACTIVE_GUI:
        gui.close()

    for gui in ACTIVE_GGUI:
        gui.destroy()


def collect_timeline(rst, p):
    log.info('Collecting cases in %s', p)

    with open(p) as f:
        tests = yaml.safe_load(f)

    for test in tests:
        p = Path(test['path'])
        if not p.exists():
            log.error('%s does not exist!', p)
            continue
        else:
            for step in test['steps']:
                run_step(None, test, step, dry=True)

            rst.append(test)



def run_timelines(timelines):
    rst = []
    p = Path(timelines)
    if p.is_dir():
        log.info('Run timelines in %s', timelines)
        for dirp, _, filenames in os.walk(p):
            for fn in filenames:
                if not fn.endswith('.yaml'):
                    continue

                collect_timeline(rst, Path(dirp) / fn)
    elif p.is_file():
        collect_timeline(rst, p)
    else:
        log.error("Don't know how to run %s", p)
        return

    for test in rst:
        run(test)


def main():
    parse_args()
    logconfig.init(getattr(logging, options.log))

    run_timelines(options.timelines)


if __name__ == '__main__':
    main()
