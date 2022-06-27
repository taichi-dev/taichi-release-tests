# -*- coding: utf-8 -*-

# -- stdlib --
from functools import wraps

# -- third party --
# -- own --

# -- code --
def hook(module):
    def inner(hooker):
        funcname = hooker.__name__
        hookee = getattr(module, funcname)

        @wraps(hookee)
        def real_hooker(*args, **kwargs):
            return hooker(hookee, *args, **kwargs)
        real_hooker.orig = hookee
        setattr(module, funcname, real_hooker)
        return real_hooker
    return inner
