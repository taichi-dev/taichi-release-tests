# -*- coding: utf-8 -*-

# -- stdlib --
from pathlib import Path
import shutil
import tempfile

# -- third party --
import matplotlib.pyplot as plt
import taichi as ti

# -- own --
from .common import register
from args import options, parser
from exceptions import Failed


# -- code --
parser.add_argument('--generate-captures', action='store_true')


@ti.kernel
def mse(a: ti.template(), b: ti.template()) -> ti.f32:
    assert a.shape == b.shape
    acc: ti.f32 = 0
    for i, j in a:
        v = a[i, j] - b[i, j]
        acc += (v * v).sum()
    return acc / a.shape[0] / a.shape[1]


@ti.kernel
def sum_difference(a: ti.template(), b: ti.template()) -> ti.i32:
    assert a.shape == b.shape
    acc: ti.i32 = 0
    for i, j in a:
        for k in ti.static(range(3)):
            v: ti.i32 = a[i, j][k] - b[i, j][k]
            acc += ti.abs(v)
    return acc


@ti.kernel
def pixel_count(a: ti.template(), b: ti.template()) -> ti.i32:
    assert a.shape == b.shape
    acc: ti.i32 = 0
    for i, j in a:
        if any(a[i, j] != b[i, j]):
            acc += 1
    return acc


# -- code --
def capture(gui, path):
    if gui is None:
        return

    if isinstance(gui, ti.ui.Window):
        gui.write_image(str(path))
    elif isinstance(gui, ti.GUI):
        gui.core.screenshot(str(path))
    elif gui is plt:
        plt.savefig(str(path))


@register('capture-and-compare')
def capture_and_compare(dry, gui, compare, ground_truth, threshold):
    if dry:
        return

    truth = Path(ground_truth)
    if options.generate_captures:
        truth.parent.mkdir(parents=True, exist_ok=True)
        capture(gui, truth)
        return

    td = Path(tempfile.mkdtemp())
    capture(gui, td / 'capture.png')
    captured = ti.tools.imread(str(td / 'capture.png'))
    truth = ti.tools.imread(str(truth))
    if captured.shape != truth.shape:
        raise Failed('capture-and-compare shape mismatch!')

    f_captured = ti.Vector.field(3, dtype=ti.i16, shape=captured.shape[:2])
    f_truth = ti.Vector.field(3, dtype=ti.i16, shape=truth.shape[:2])
    f_captured.from_numpy(captured[:, :, :3])
    f_truth.from_numpy(truth[:, :, :3])

    pixels = f_captured.shape[0] * f_captured.shape[1]
    if compare == 'mse':
        diff = mse(f_captured, f_truth)
        if isinstance(threshold, str) and threshold.endswith('%'):
            threshold = float(threshold[:-1]) / 100 * 255
    elif compare == 'sum-difference':
        diff = sum_difference(f_captured, f_truth)
        if isinstance(threshold, str) and threshold.endswith('%'):
            threshold = float(threshold[:-1]) / 100 * pixels * 3 * 255
    elif compare == 'pixel-count':
        diff = pixel_count(f_captured, f_truth)
        if isinstance(threshold, str) and threshold.endswith('%'):
            threshold = float(threshold[:-1]) / 100 * pixels
    else:
        raise ValueError(f'Unknown compare method: {compare}')

    if diff > threshold:
        shutil.move(str(td / 'capture.png'), str(ground_truth) + '.bad.png')
        shutil.rmtree(td, ignore_errors=True)
        raise Failed(f'capture-and-compare failed! diff({diff}) > threshold({threshold})')

    shutil.rmtree(td, ignore_errors=True)
