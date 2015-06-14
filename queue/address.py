
import datetime
import django_rq

import addressbook
import thirtythirty

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@django_rq.job
def Reset(fingerprint=None):
    logger.debug('Address reset: %s' % fingerprint)
    if not thirtythirty.hdd.drives_are_unlocked():
        logger.warning('Drives not unlocked yet.')
        Sched = django_rq.get_scheduler('default')
        Sched.enqueue_in(datetime.timedelta(minutes=30), Reset, fingerprint=fingerprint)
        exit()

    if not exists(TTS.PASSPHRASE_CACHE):
        logger.warning('I need a passphrase to continue - rescheduling.')
        Sched = django_rq.get_scheduler()
        Sched.enqueue_in(datetime.timedelta(minutes=30), Reset, fingerprint=fingerprint)
        exit()
        
    passphrase = file(TTS.PASSPHRASE_CACHE, 'r').read()
    addressbook.address.objects.get(fingerprint=fingerprint).delete_local_state(passphrase)

