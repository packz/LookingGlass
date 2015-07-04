
import os
from os.path import exists
import subprocess

import django_rq
from django_rq import job

import queue
import ratchet
import smp

import thirtythirty.settings as TTS
import thirtythirty.exception as TTE

import logging
logger = logging.getLogger(__name__)

@job
def LOCKDOWN():
    if exists(TTS.PASSPHRASE_CACHE):
        PP = file(TTS.PASSPHRASE_CACHE, 'r').read()
        try: ratchet.conversation.Conversation.objects.encrypt_database(PP)
        except: pass
        try: smp.models.SMP.objects.encrypt_database(PP)
        except: pass
        os.unlink(TTS.PASSPHRASE_CACHE)
    logger.debug('Emphemeral DBs encrypted')
    return True
    
        
@job
def REBOOT():
    logger.critical('Reboot in progress')
    subprocess.call(['/usr/bin/sudo', '-u', 'root',
                     '/sbin/shutdown', '-r', 'now'])
