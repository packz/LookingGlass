
class RatchetException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    
class Bad_Passphrase(RatchetException):
    pass

class Undecipherable(RatchetException):
    pass

class Vanished_MessageKey(RatchetException):
    pass

class Missing_Handshake(RatchetException):
    pass

class Broken_Format(RatchetException):
    pass

class Actually_Anonymous(RatchetException):
    pass
