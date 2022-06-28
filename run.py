# -*- coding: utf-8 -*-

# -- stdlib --
from pathlib import Path
import argparse
import importlib
import importlib.util
import logging
import os
import sys

# -- third party --
import taichi as ti
import yaml

# -- own --
from actions import ACTIONS
from exceptions import Success
from utils import logconfig
from utils.misc import hook


# -- code --
log = logging.getLogger('main')
options = None

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


def run_step(step, dry=False):
    if 'action' not in step:
        raise ValueError('Step %s has no action!', step)
    if step['action'] not in ACTIONS:
        raise ValueError('Unknown action %s!', step['action'])

    args = dict(step)
    args.pop('action', 0)
    args.pop('frame', 0)
    args['dry'] = dry
    ACTIONS[step['action']](**args)


def try_run_step(self):
    step = STATE['step']
    if step is None:
        return

    fr = step['frame']
    if isinstance(fr, str) and fr.startswith('@'):
        fr = int(fr[1:])
    else:
        fr = STATE['last_step_frame'] + int(fr)

    if self.frame >= fr:
        STATE['last_step_frame'] = self.frame
        run_step(step)
        next_step()


@hook(ti.GUI, 'show')
def gui_show(orig, self, _=None):
    ACTIVE_GUI.add(self)
    orig(self)
    try_run_step(self)


@hook(ti.ui.Window, 'show')
def ggui_show(orig, self, _=None):
    ACTIVE_GGUI.add(self)
    orig(self)
    self.frame += 1
    try_run_step(self)


ti.ui.Window.frame = 0


def run(test):
    log.info('Running %s...', test['path'])
    ti.reset()
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
                run_step(step, dry=True)

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
    global options
    parser = argparse.ArgumentParser('taichi-release-tests-runner')
    parser.add_argument('timelines')
    parser.add_argument('--log', default='INFO')
    options = parser.parse_args()

    logconfig.init(getattr(logging, options.log))

    run_timelines(options.timelines)


if __name__ == '__main__':
    main()
