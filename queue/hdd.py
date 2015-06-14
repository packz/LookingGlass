
import subprocess
import os.path

import django_rq

import thirtythirty.hdd as TTH
import thirtythirty.exception as TTE
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@django_rq.job
def Shred_Keyfile():
    subprocess.call(['shred', '-fuv', TTS.LUKS['key_file']])
    logger.debug('Keyfile %s izzzzzzzzzzzz gone' % TTS.LUKS['key_file'])

@django_rq.job
def Unlock():
    if not os.path.exists(TTS.LUKS['key_file']):
        logger.critical('No key file!  Abort')
    else:
        passphrase = file(TTS.LUKS['key_file'], 'r').read()
        Shred_Keyfile.delay()
        for V in TTH.Volumes():
            if not V.is_mounted():
                try:
                    V.unlock(passphrase)
                except TTE.CannotStartLuks:
                    logger.warning('Bad passphrase in %s' % TTS.LUKS['key_file'])
                    exit()
