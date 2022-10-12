# -*- coding: utf-8 -*-

# --- prioritized ---
import os
os.environ['TI_GUI_FAST'] = '0'
os.environ['MPLBACKEND'] = 'agg'

# -- stdlib --
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import importlib
import importlib.util
import logging
import platform
import random
import sys

# -- third party --
import numpy as np
import taichi as ti
import yaml

# -- own --
from actions import ACTIONS
from actions.common import register
from args import options, parse_args
from exceptions import Success
from utils import logconfig
from utils.misc import hook


# -- code --
log = logging.getLogger('main')

STATE = {
    'orig_work_dir': Path(os.getcwd()),
    'current_test': None,
    'current_module': None,
    'ensure_compiled_run': False,
    'steps_iter': None,
    'step': None,
    'last_step_frame': 0,
}

ACTIVE_GUI = set()
ACTIVE_GGUI = set()

apply = lambda f, *a, **k: f(*a, **k)


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

    try:
        orig = os.getcwd()
        os.chdir(STATE['orig_work_dir'])
        action(**args)
    finally:
        os.chdir(orig)


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


@apply
def hook_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    @hook(plt)
    def show(orig, *args, **kwargs):
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


@apply
def hook_opencv():
    try:
        import cv2
    except ImportError:
        return

    cv2.frame = 0

    @hook(cv2)
    def waitKey(orig, *a, **k):
        return orig(1)

    @hook(cv2)
    def imwrite(orig, *args, **kwargs):
        return

    @hook(cv2)
    def imshow(orig, winname, mat):
        orig(winname, mat)
        cv2._imshow_image = mat
        while try_run_step(cv2):
            pass

    @register('__reset:cv2')
    def reset_cv2():
        try:
            import cv2
            cv2.destroyAllWindows()
        except ImportError:
            pass



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

    spec = importlib.util.spec_from_file_location('__main__', Path(test['path']).resolve())
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    STATE['current_module'] = module
    sys.argv = [test['path']] + test['args']
    wd = Path(test['path']).resolve().parent
    os.chdir(wd)
    sys.path.insert(0, str(wd))
    try:
        spec.loader.exec_module(module)
    except Success:
        pass
    except BaseException:
        log.error("%s failed!", test['path'])
        raise
    finally:
        os.chdir(STATE['orig_work_dir'])
        sys.path.remove(str(wd))

    for gui in ACTIVE_GUI:
        gui.close()

    for gui in ACTIVE_GGUI:
        gui.destroy()

    return True


def collect_timeline(rst, p):
    log.info('Collecting cases in %s', p)

    with open(p) as f:
        tests = yaml.safe_load(f)

    machine = platform.machine()
    COALESCE = {
        'AMD64': 'x86_64',
        'x64': 'x86_64',
    }
    machine = COALESCE.get(machine, machine)

    for i, test in enumerate(tests):
        m = test.get('machine', None)
        if m and machine not in m:
            log.debug('Skipping %s:%d due to incompatible machine type %s (we are on %s)', test['path'], i, m, machine)
            continue

        p = Path(test['path'])
        if not p.exists():
            log.error('%s does not exist!', p)
            continue
        else:
            for step in test['steps']:
                run_step(None, test, step, dry=True)

            rst.append(test)


def run_timelines(timeline_path):
    timelines = []
    p = Path(timeline_path)
    if p.is_dir():
        log.info('Run timelines in %s', timeline_path)
        for dirp, _, filenames in os.walk(p):
            for fn in filenames:
                if not fn.endswith('.yaml') and not fn.endswith('.yml'):
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
        with ProcessPoolExecutor(max_workers=options.runners) as pool:
            for r in pool.map(run, timelines):
                if not r:
                    break


def main():
    parse_args()
    logconfig.init(getattr(logging, options.log))
    run_timelines(options.timelines)


if __name__ == '__main__':
    main()
