
class AddressbookException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)
    
class Bad_Passphrase(AddressbookException):
    pass

class Missing_Message(AddressbookException):
    pass

class Multiple_Private_Keys(AddressbookException):
    pass

class Need_Axolotl_First(AddressbookException):
    pass

class Socialist_Misstep(AddressbookException):
    pass


class FileLockException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Bad_Key(FileLockException):
    pass

class No_File(FileLockException):
    pass

class File_Exists(FileLockException):
    pass
