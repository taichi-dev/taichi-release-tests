ACTIONS = {}

def register(name):
    def decorator(func):
        ACTIONS[name] = func
        return func
    return decorator
