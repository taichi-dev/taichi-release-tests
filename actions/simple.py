# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
# -- own --
from .common import register
from exceptions import Success, Failed


# -- code --
@register('succeed')
def succeed(dry):
    if dry:
        return

    raise Success


@register('fail')
def fail(dry):
    if dry:
        return

    raise Failed
