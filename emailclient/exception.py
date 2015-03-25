
class EmailException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)

class Bad_Passphrase(EmailException):
    pass

class No_Attachment(EmailException):
    pass

