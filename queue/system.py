
import os
from os.path import exists
import subprocess

import django_rq
from django_rq import job

import queue
import ratchet
import smp

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@job
def LOCKDOWN():
    logger.critical('LOCKDOWN activated')
    if exists(TTS.PASSPHRASE_CACHE):
        PP = file(TTS.PASSPHRASE_CACHE, 'r').read()
        os.unlink(TTS.PASSPHRASE_CACHE)
        try: ratchet.conversation.Conversation.objects.encrypt_database(PP)
        except: pass
        try: smp.models.SMP.objects.encrypt_database(PP)
        except: pass
        logging.critical('Encrypted ratchet and SMP databases')
    queue.hdd.Lock.delay()
    

@job
def REBOOT():
    logger.critical('Reboot in progress')
    subprocess.call(['/usr/bin/sudo', '-u', 'root',
                     '/sbin/shutdown', '-r', 'now'])
