
import subprocess
import os.path

import django_rq
from django_rq import job

import thirtythirty.hdd as TTH
import thirtythirty.exception as TTE
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@job
def Shred_Keyfile():
    subprocess.call(['/usr/bin/shred', '-fu',
                     TTS.LUKS['key_file']])
    logger.debug('Keyfile %s izzzzzzzzzzzz gone' % TTS.LUKS['key_file'])

    
@job
def Unlock(passphrase=None):
    if passphrase:
        fh = file(TTS.LUKS['key_file'], 'w')
        fh.write(passphrase)
        fh.close()
    if not os.path.exists(TTS.LUKS['key_file']):
        logger.critical('No key file!  Abort')
        return False
    logger.debug('Unlocking...')
    passphrase = file(TTS.LUKS['key_file'], 'r').read()
    Shred_Keyfile.delay()
    for V in TTH.Volumes():
        if not V.is_mounted():
            try:
                V.unlock(passphrase)
                logger.debug('Unlocked %s' % V.Name)
            except TTE.CannotStartLuks:
                logger.warning('Bad passphrase in %s' % TTS.LUKS['key_file'])
                return False
    return True


@job
def Lock():
    for V in TTH.Volumes():
        V.lock()
        logger.debug('Locked %s' % V.Name)
