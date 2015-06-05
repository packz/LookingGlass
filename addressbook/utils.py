
from django.core.exceptions import MultipleObjectsReturned

import re
from types import StringType

import addressbook.address
import addressbook.exception

import logging
logger = logging.getLogger(__name__)

import cPickle
import datetime
import thirtythirty.settings as TTS
import os
class time_lock(object):
    """
    OODA too tight / slow down
    """
    def lock(self, which=None, clobber=True):
        if not TTS.HASHCASH['BACKOFF'].has_key(which):
            raise(addressbook.exception.Bad_Key('No key %s' % which))
        if ((os.path.exists(TTS.HASHCASH['BACKOFF'][which])) and
            (not clobber)):
            raise(addressbook.exception.File_Exists('File %s already there' % TTS.HASHCASH['BACKOFF'][which]))
        cPickle.dump(datetime.datetime.now(),
                     file(TTS.HASHCASH['BACKOFF'][which], 'w'))
        return True

    def is_locked(self, which=None, seconds=TTS.HASHCASH['RATE_LIMIT_SECONDS'], clobber=True):
        if not TTS.HASHCASH['BACKOFF'].has_key(which):
            raise(addressbook.exception.Bad_Key('No key %s' % which))
        if not os.path.exists(TTS.HASHCASH['BACKOFF'][which]):
            logger.debug('Locking for first time')
            self.lock(which)
            return False
        Now = datetime.datetime.now()
        Then = cPickle.load(file(TTS.HASHCASH['BACKOFF'][which], 'r'))
        D = datetime.timedelta(seconds=seconds)
        if (Now - Then) > D:
            if clobber:
                os.unlink(TTS.HASHCASH['BACKOFF'][which])
            return False
        else:
            return True


def msg_type(msg=None):
    """
    Returns False on 'no data'
    None on IDKWTF this is BBQ
    """
    if type(msg) is not StringType: return False
    if re.search('BEGIN PGP MESSAGE', msg):
        return 'PGP-MSG'
    elif re.search('BEGIN PGP SIGNED MESSAGE', msg):
        return 'PGP-CLEARSIGN'
    elif re.search('BEGIN AXOLOTL HANDSHAKE', msg):
        return 'AXO-HS'
    elif re.search('BEGIN AXOLOTL MESSAGE', msg):
        return 'AXO-MSG'
    else:
        return None
    

def my_address():
    try:
        return addressbook.address.Address.objects.get(is_me=True)
    except MultipleObjectsReturned:
        raise(addressbook.exception.Multiple_Private_Keys('You appear to have multiple private keys.  I am too hastily coded to handle that properly.'))


def double_metaphone(name=None):
    """
    FIXME: move the import statement to the head when we up the image
    """
    try:
        import fuzzy
    except:
        return []
    if not name:
        return []
    DM = fuzzy.DMetaphone()
    DMetaphone = DM(name)
    while ((len(DMetaphone) != 0) and
           (not DMetaphone[-1])):
        DMetaphone.pop()
    return DMetaphone
