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

# def _get_gaussian_coef(radius):
#     from math import erfc
#     a = 3.0 / radius * 0.707106781
#     f = lambda x: 0.5*erfc(-x*a)
#     l = [f(0.5 + i) - f(-0.5 + i) for i in range(radius+1)]
#     l = [i for i in l if i>0.01]
#     l = list(reversed(l[1:])) + l
#     s = sum(l)
#     l = [i/s for i in l]
#     return l


GAUSSIAN_COEFF = [
    0.01449797497581252,
    0.04928451699227458,
    0.11807162656393803,
    0.19941115896256947,
    0.23746944501081074,
    0.19941115896256947,
    0.11807162656393803,
    0.04928451699227458,
    0.01449797497581252,
]


@ti.kernel
def rmse(a: ti.template(), b: ti.template()) -> ti.f32:
    assert a.shape == b.shape
    acc: ti.f32 = 0
    for i, j in a:
        v = a[i, j] - b[i, j]
        acc += (v * v).sum()
    return ti.sqrt(acc / a.shape[0] / a.shape[1])


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


@ti.kernel
def gaussian_blur(a: ti.template(), aux: ti.template()):
    assert a.shape == aux.shape
    for i, j in a:
        acc = ti.Vector([0.0, 0.0, 0.0])
        for k in ti.static(range(-4, 5)):
            acc += GAUSSIAN_COEFF[k + 4] * a[i, j+k]
        aux[i, j] = ti.cast(acc, ti.i16)

    for i, j in a:
        acc = ti.Vector([0.0, 0.0, 0.0])
        for k in ti.static(range(-4, 5)):
            acc += GAUSSIAN_COEFF[k + 4] * aux[i+k, j]
        a[i, j] = ti.cast(acc, ti.i16)


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
    if compare == 'rmse':
        diff = rmse(f_captured, f_truth)
        if isinstance(threshold, str) and threshold.endswith('%'):
            threshold = float(threshold[:-1]) / 100 * 255
    elif compare == 'sum-difference':
        diff = sum_difference(f_captured, f_truth)
        if isinstance(threshold, str) and threshold.endswith('%'):
            threshold = float(threshold[:-1]) / 100 * pixels * 3 * 255
    elif compare == 'blur-sum-difference':
        f_aux = ti.Vector.field(3, dtype=ti.i16, shape=truth.shape[:2])
        gaussian_blur(f_captured, f_aux)
        gaussian_blur(f_truth, f_aux)
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
