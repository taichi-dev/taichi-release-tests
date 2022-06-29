# -*- coding: utf-8 -*-

# -- stdlib --
import inspect

# -- third party --
# -- own --

# -- code --
ACTIONS = {}

def register(name):
    def decorator(func):
        func.params = set(inspect.signature(func).parameters.keys())
        ACTIONS[name] = func
        return func
    return decorator
