
from os import chmod
from stat import S_IRUSR, S_IWUSR

import re
import subprocess
import os.path

import addressbook

from thirtythirty.gpgauth import set_up_single_user

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

def generate_key(passphrase=None,
                 covername=None,
                 email=None,):
    """
    FIXME: clock is ticking on code to handle key expiration
    """
    Me = addressbook.address.Address.objects.filter(is_me=True).first()
    if Me:
        logger.debug('requested gpg key, but we already have an addressbook entry')
        return Me
    logger.debug('Creating key for %s' % email)
    Key_Length = 2048
    Input = addressbook.GPG.gen_key_input(key_type='DSA',
                                          key_length=Key_Length,
                                          subkey_type='ELG-E',
                                          subkey_length=Key_Length,
                                          name_real=covername,
                                          name_email=email,
                                          expire_date='8m',
                                          passphrase=passphrase,
                                          )
    Fingerprint = addressbook.GPG.gen_key(Input)
    logger.debug('Key created, running DB import scripts')
    addressbook.address.Address.objects.rebuild_addressbook()
    return Fingerprint


def __gpg_edit_key(script=None, debug=False):
    Me = addressbook.address.Address.objects.filter(is_me=True).first()
    Handle = subprocess.Popen(['/usr/bin/gpg',
                               '--command-fd', '0',
                               '--status-fd', '1',
                               '--no-tty',
                               '--edit-key', Me.fingerprint],
                              stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE,
                              stdin=subprocess.PIPE)
    Out, Err = Handle.communicate(script)
    if debug:
        logger.debug('SO> %s' % Out)
        logger.debug('SE> %s' % Err)
    return Err


def change_passphrase(old=None,
                      new=None):
    Script = """passwd
%s
%s
save
""" % (old, new)
    Raw = __gpg_edit_key(Script)
    if re.search('Invalid passphrase', Raw): return False
    return True


def change_uid(passwd=None):
    Me = addressbook.address.Address.objects.filter(is_me=True).first()
    Script = """adduid
%s
%s

O
%s
1
deluid
y
save
""" % (Me.covername.upper(), Me.email.upper(), passwd)
    Raw = __gpg_edit_key(Script)
    if re.search('signing failed', Raw): return False
    return True


def export():
    Me = addressbook.address.Address.objects.filter(is_me=True).first()
    if not Me: return False
    return addressbook.GPG.export_keys(Me.fingerprint)


def Import(keydata=None):
    return addressbook.GPG.import_keys(keydata)
    

def decrypt(msg=None, passphrase=None):
    return addressbook.GPG.decrypt(msg,
                                   always_trust=True,
                                   passphrase=passphrase)


def symmetric(msg=None, passphrase=None,
              armor=True,
              filename=None):
    if not passphrase or not msg: return False
    if not filename:
        return addressbook.GPG.encrypt(msg,
                                       recipients=None,
                                       armor=armor,
                                       always_trust=True,
                                       passphrase=passphrase,
                                       symmetric=TTS.GPG['symmetric_algo'])
    else:
        return addressbook.GPG.encrypt_file(msg,
                                            recipients=None,
                                            armor=False,
                                            output=filename,
                                            always_trust=True,
                                            passphrase=passphrase,
                                            symmetric=TTS.GPG['symmetric_algo'])


def create_symmetric(passphrase=None, clobber=False, location=None):
    """
    location is used for test framework
    """
    if not location:
        location = TTS.GPG['symmetric_location']
    if ((not passphrase) or
        (os.path.exists(location) and
         not clobber)):
        return False
    FH = file(location, 'w')
    FH.write(str(symmetric(TTS.GPG['magic_cookie'], passphrase)))
    return location


def verify_symmetric(passphrase=None, location=None):
    """
    as a side effect, blows the passphrase into the on-disk cache
    
    location is used for test framework
    """
    if not location:
        location = TTS.GPG['symmetric_location']
    if ((not passphrase) or
        (not os.path.exists(location))): return False
    FH = file(location, 'rb').read()
    DC = decrypt(FH, passphrase)
    if ((DC.ok) and (str(DC.data) == TTS.GPG['magic_cookie'])):
        prefs = set_up_single_user()
        if ((prefs.passphrase_cache) and
            (not os.path.exists(TTS.PASSPHRASE_CACHE))):
            fh = file(TTS.PASSPHRASE_CACHE, 'w')
            chmod(TTS.PASSPHRASE_CACHE, S_IRUSR | S_IWUSR)
            fh.write(passphrase)
            fh.close()
        return True
    else:
        return False


def sign_data(to_sign=None, passphrase=None):
    if ((not to_sign) or
        (not passphrase)): return False
    S = addressbook.GPG.sign(to_sign,
                             passphrase=passphrase)
    if S.fingerprint is None: return False
    else: return str(S)


def verify_clearsign(eeenput=None):
    """
    this is lame
    """
    S = addressbook.GPG.verify(eeenput)
    return S


def verify_data(eeenput=None):
    from re import search, sub
    
    if not eeenput: return {'ok':False,
                            'reason':'no eeenput, stephanie'}

    V = str(eeenput)
    S = addressbook.GPG.verify(V)
    if not S: return {'ok':False,
                      'msg':'verify failed'}
    
    just_the_faqs = search("""(?smx) # dotall, multiline, verbose
^Hash: [^\n]+\W
^\W$
(?P<signed_part>.+)\W+
^\-\-\-\-\-BEGIN\ PGP\ SIGNATURE""", str(V)) # i like hot smx
    if not just_the_faqs:
        return {'ok':False,
                'reason':'I probably screwed up the regex'}
    return {'ok':(S and True),
            'msg':sub('\\n', '\n', just_the_faqs.group('signed_part')),
            'fp':S.pubkey_fingerprint,
            'timestamp':S.timestamp,
            }
