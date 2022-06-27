class Terminate(BaseException):
    pass

class Success(Terminate):
    pass

class Failed(Terminate):
    pass


