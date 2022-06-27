# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
# -- own --
from .common import register
from exceptions import Success


# -- code --
@register('succeed')
def succeed(dry):
    if dry:
        return

    raise Success
