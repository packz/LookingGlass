
class AddressbookException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    
class Bad_Passphrase(AddressbookException):
    pass

class Multiple_Private_Keys(AddressbookException):
    pass

class Need_Axolotl_First(AddressbookException):
    pass

class Socialist_Misstep(AddressbookException):
    pass

class Unset_Secret(AddressbookException):
    pass

class Secret_Already_Set(AddressbookException):
    pass
