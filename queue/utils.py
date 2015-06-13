
from os.path import exists

from addressbook.gpg import verify_symmetric
from thirtythirty.settings import PASSPHRASE_CACHE

def Passphrase():
    if exists(PASSPHRASE_CACHE):
        pp = file(PASSPHRASE_CACHE).read()
        if verify_symmetric(pp):
            return pp
    return None
