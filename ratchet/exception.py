
class RatchetException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)

class No_Address(RatchetException):
    pass
    
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

class Broken_State(RatchetException):
    pass

class Actually_Anonymous(RatchetException):
    pass
