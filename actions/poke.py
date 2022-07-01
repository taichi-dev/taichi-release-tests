# -*- coding: utf-8 -*-

# -- stdlib --
import sys

# -- third party --
# -- own --
from .common import register
from pathlib import Path


# -- code --
@register('poke')
def poke(function, code, current_test):
    path = Path(current_test['path']).resolve()
    f = sys._getframe(1)
    while f:
        co = f.f_code

        if Path(co.co_filename).resolve() != path:
            f = f.f_back
            continue

        if co.co_name == function:
            exec(code, f.f_globals, f.f_locals)
            return

        f = f.f_back

    raise ValueError(f'poke: Cannot find function `{function}`')
