
class CryptDBException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)
    
class Bad_Passphrase(CryptDBException): pass

class Undecipherable(CryptDBException): pass

class Locking_Problem(CryptDBException): pass

class Target_Exists(CryptDBException): pass

class Missing_Database(CryptDBException): pass



class LuksException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)

class No_Keyfile(LuksException): pass

class No_Old_Keyfile(LuksException): pass

class LVExists(LuksException): pass

class CannotCreateLV(LuksException): pass

class CannotFormat(LuksException): pass

class CannotStartLuks(LuksException): pass

class CannotStopLuks(LuksException): pass

class CannotMKFS(LuksException): pass

class CannotMount(LuksException): pass

class CannotUmount(LuksException): pass

class CannotOwn(LuksException): pass

class CannotMod(LuksException): pass

class NoKeychange(LuksException): pass

class LVResizeFailed(LuksException): pass

class CryptResizeFailed(LuksException): pass

class FSResizeFailed(LuksException): pass

class LVRemoveFailed(LuksException): pass


class UpgradeException(Exception):
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)
        
    def __str__(self):
        return repr(self.value)

class ScanException(UpgradeException): pass

class DownloadException(UpgradeException): pass

class ChecksumException(UpgradeException): pass

class SignatureException(UpgradeException): pass

class PreInstException(UpgradeException): pass

class UnpackException(UpgradeException): pass

class PostInstException(UpgradeException): pass
