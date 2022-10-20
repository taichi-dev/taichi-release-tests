# -*- coding: utf-8 -*-

# -- stdlib --
import argparse

# -- third party --
import numpy as np
import taichi as ti

# -- own --
from actions.capture import gaussian_blur, rmse, pixel_count, sum_difference


# -- code --
def main():
    ti.init(arch=ti.gpu)

    parser = argparse.ArgumentParser('compare')
    parser.add_argument('a')
    parser.add_argument('b')
    options = parser.parse_args()

    file_a = ti.tools.imread(options.a)
    file_b = ti.tools.imread(options.b)

    assert file_a.shape == file_b.shape

    f_a = ti.Vector.field(3, dtype=ti.i16, shape=file_a.shape[:2])
    f_b = ti.Vector.field(3, dtype=ti.i16, shape=file_b.shape[:2])
    f_aux = ti.Vector.field(3, dtype=ti.i16, shape=file_a.shape[:2])
    f_a.from_numpy(np.ascontiguousarray(file_a[:, :, :3]))
    f_b.from_numpy(np.ascontiguousarray(file_b[:, :, :3]))

    pixels = f_a.shape[0] * f_a.shape[1]
    diff = rmse(f_a, f_b)
    print(f'rmse: {diff}')
    diff = sum_difference(f_a, f_b)
    print(f'sum difference: {diff}, {diff / (pixels * 3 * 255) * 100:.2f}%')
    diff = pixel_count(f_a, f_b)
    print(f'pixel count: {diff}, {diff / pixels * 100:.2f}%')
    gaussian_blur(f_a, f_aux)
    gaussian_blur(f_b, f_aux)
    diff = sum_difference(f_a, f_b)
    print(f'blur sum difference: {diff}, {diff / (pixels * 3 * 255) * 100:.2f}%')

if __name__ == '__main__':
    main()
