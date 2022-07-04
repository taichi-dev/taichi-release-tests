# -*- coding: utf-8 -*-

# -- stdlib --
from pathlib import Path
import random
import multiprocessing
import importlib
import importlib.util
import numpy as np  # pyright: ignore
import logging
import os
import sys

# -- third party --
import matplotlib.pyplot as plt
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
    'current_module': None,
    'ensure_compiled_run': False,
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


@hook(plt, 'show')
def plt_show(orig, *args, **kwargs):
    # special case
    test = STATE['current_test']
    step = STATE['step']
    if step is None:
        return

    if not step['action'] == 'capture-and-compare':
        return

    run_step(plt, test, step)
    next_step()
    return True


@hook(ti)
def init(orig, arch=None, **kwargs):
    kwargs['random_seed'] = 23333
    np.random.seed(23333)
    random.seed(23333)
    return orig(arch=arch, **kwargs)


@hook(ti.lang.kernel_impl.Kernel)
def ensure_compiled(orig, self, *args):
    if STATE['ensure_compiled_run']:
        return orig(self, *args)

    STATE['ensure_compiled_run'] = True
    test = STATE['current_test']
    mod = STATE['current_module']
    if 'before_first_kernel' in test:
        exec(test['before_first_kernel'], mod.__dict__, mod.__dict__)

    return orig(self, *args)


def run(test):
    log.info('Running %s...', test['path'])
    ti.reset()

    STATE['ensure_compiled_run'] = False
    STATE['current_test'] = test
    STATE['steps_iter'] = iter(test['steps'])
    STATE['last_step_frame'] = 0
    next_step()

    for act in ACTIONS:
        if act.startswith('__reset:'):
            ACTIONS[act]()

    spec = importlib.util.spec_from_file_location('__main__', test['path'])
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    STATE['current_module'] = module
    sys.argv = [test['path']] + test['args']

    try:
        spec.loader.exec_module(module)
    except Success:
        pass
    except Exception:
        log.error("%s failed!", test['path'])
        raise

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


def run_as_worker(id, wq, cq):
    while True:
        test = wq.get()
        if test is None:
            return

        try:
            run(test)
            cq.put((id, 'ok'))
        except Exception:
            cq.put((id, 'error'))
            raise



def run_timelines(timeline_path):
    timelines = []
    p = Path(timeline_path)
    if p.is_dir():
        log.info('Run timelines in %s', timeline_path)
        for dirp, _, filenames in os.walk(p):
            for fn in filenames:
                if not fn.endswith('.yaml'):
                    continue

                collect_timeline(timelines, Path(dirp) / fn)
    elif p.is_file():
        collect_timeline(timelines, p)
    else:
        log.error("Don't know how to run %s", p)
        return

    if options.runners == 1:
        for test in timelines:
            run(test)
    else:
        wq = multiprocessing.Queue()
        cq = multiprocessing.Queue()
        workers = []
        for i in range(options.runners):
            proc = multiprocessing.Process(target=run_as_worker, args=(i, wq, cq))
            proc.start()
            workers.append(proc)

        for test in timelines:
            wq.put(test)

        for _ in range(options.runners):
            wq.put(None)

        wq.close()

        for _ in range(len(timelines)):
            id, status = cq.get()
            if status == 'error':
                raise Exception('Worker %d failed!', id)

def main():
    parse_args()
    logconfig.init(getattr(logging, options.log))

    os.environ['TI_GUI_FAST'] = '0'

    run_timelines(options.timelines)


if __name__ == '__main__':
    main()
