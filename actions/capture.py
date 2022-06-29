# -*- coding: utf-8 -*-

# -- stdlib --
from pathlib import Path
import shutil
import tempfile

# -- third party --
import taichi as ti

# -- own --
from .common import register
from args import options, parser
from exceptions import Failed


# -- code --
parser.add_argument('--generate-captures', action='store_true')


@ti.kernel
def mse(a: ti.template(), b: ti.template()) -> ti.i64:
    assert a.shape == b.shape
    acc: ti.i64 = 0
    for i, j in a:
        v = a[i, j] - b[i, j]
        acc += (v * v).sum()
    return acc / a.shape[0] / a.shape[1]


@ti.kernel
def pixel_count(a: ti.template(), b: ti.template()) -> ti.i64:
    assert a.shape == b.shape
    acc: ti.i64 = 0
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
    shutil.rmtree(td, ignore_errors=True)
    truth = ti.tools.imread(str(truth))
    if captured.shape != truth.shape:
        raise Failed('capture-and-compare shape mismatch!')

    f_captured = ti.Vector.field(3, dtype=ti.i16, shape=captured.shape[:2])
    f_truth = ti.Vector.field(3, dtype=ti.i16, shape=truth.shape[:2])
    f_captured.from_numpy(captured[:, :, :3])
    f_truth.from_numpy(truth[:, :, :3])

    if compare == 'mse':
        diff = mse(f_captured, f_truth)
    elif compare == 'pixel-count':
        diff = pixel_count(f_captured, f_truth)
    else:
        raise ValueError(f'Unknown compare method: {compare}')

    if diff > threshold:
        raise Failed(f'capture-and-compare failed! diff({diff}) > threshold({threshold})')
