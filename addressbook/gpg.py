
from os import chmod
from stat import S_IRUSR, S_IWUSR
from time import time

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
    addressbook.address.Address.objects.rebuild_addressbook(Private=True)
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


def change_expiration(passwd=None, expire='8m'):
    Script = """0
expire
%s
%s
1
expire
%s
%s
save
""" % (
    expire,
    passwd,
    expire,
    passwd
    )
    Raw = __gpg_edit_key(Script)
    if re.search('Invalid passphrase', Raw): return False
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


def push_to_keyserver():
    Me = addressbook.utils.my_address()
    ret = {'failed':True,
           'status':[]}
    for X in TTS.GPG['keyserver']:
        S = addressbook.GPG.send_keys(X, Me.fingerprint)
        Info = re.sub('(?s).*gpg: sending key', '', S.stderr).strip()
        logger.debug(Info)
        ret['status'].append(Info)
        if not re.search('failed', Info):
            ret['failed'] = False
    return ret


def __search_keyserver(covername=None):
    """
    do sanity checking of the key here
    return only very very good prospects
    """
    Epoch = time()
    Search = '%s@*.onion' % re.sub(' ', '.', covername)
    RE_Match = '<%s@[0-9A-Z]{16}\.ONION>$' % re.sub(' ', '\.', covername).upper()
    ret = []
    Timeout_Count = 0
    for KS in TTS.GPG['keyserver']:
        K = addressbook.GPG.search_keys(Search, KS)
        if 'timed out' in K.stderr:
            logger.warning('Server timeout: %s' % KS)
            Timeout_Count += 1
        elif len(K) == 0:
            logger.warning('%s has no keys.' % KS)
        for Key in K:
            try: # key w/o expiration results in empty string
                if float(Key['expires']) < Epoch:
                    logger.debug('Key %s expired' % Key['keyid'])
                    continue
            except ValueError:
                logger.debug('Key %s no expiration' % Key['keyid'])
                continue
            try:
                if re.search(RE_Match, Key['uids'][0]):
                    if Key not in ret:
                        ret.append(Key)
            except ValueError:
                logger.debug('Key %s uid AFU' % Key['keyid'])
                continue
    if Timeout_Count >= len(TTS.GPG['keyserver']):
        raise(addressbook.exception.KeyserverTimeout('All servers timed out'))
    return ret


def __key_from_fingerprint(FP=None):
    for KS in TTS.GPG['keyserver']:
        if addressbook.GPG.recv_keys(KS, FP).count == 1:
            addressbook.address.Address.objects.rebuild_addressbook()
            return FP
    return None

        
def pull_from_keyserver(address=None, covername=None, fingerprint=None):
    if not (address or covername or fingerprint): return None
    if address:
        if not isinstance(address, addressbook.address.Address): return None
        covername = address.covername
        if not covername: return None
    if covername:
        Search_Result = __search_keyserver(covername)
        if len(Search_Result) == 1:
            fingerprint = Search_Result[0]['keyid']
        elif len(Search_Result) > 1:
            raise(addressbook.exception.MultipleMatches(Search_Result))
        elif len(Search_Result) == 0:
            raise(addressbook.exception.NoKeyMatch(Search_Result))
    if not fingerprint:
        logger.debug('No fingerprint?')
        return None
    logger.debug('Requesting key for %s' % fingerprint)
    if __key_from_fingerprint(fingerprint):
        return addressbook.address.Address.objects.get(fingerprint=fingerprint)

