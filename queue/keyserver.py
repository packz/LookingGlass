
from django.db import models
from django.db.models import Q

import django_rq
from django_rq import job

import datetime
from os.path import exists

import addressbook
import emailclient
import ratchet
import thirtythirty.hdd
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

@job
def Push():
    logger.debug('Keyserver push')
    if not thirtythirty.hdd.drives_are_unlocked():
        logger.warning('Drives not unlocked yet.')
        Sched = django_rq.get_scheduler('default')
        Sched.enqueue_in(datetime.timedelta(minutes=30), Push)
        exit()
    Resp = addressbook.gpg.push_to_keyserver()
    Me = addressbook.utils.my_address()
    if Resp['failed']:
        emailclient.utils.submit_to_smtpd(Payload="""The upstream server seems to have experienced a temporary problem during registration.
The error is:
`%s`
We'll try registration again in a bit and see if it magically starts working.
""" % '\n'.join(Resp['status']),
                Destination=Me.email,
                Subject='Temporary problem - key registration',
                From='Sysop <root>')
    else:
        Me.comment = 'KS Accepted - %s' % ' '.join(Resp['status'])
        Me.save()

        
@job
def Pull(covername=None):
    logger.debug('Keyserver pull')

    if not exists(TTS.PASSPHRASE_CACHE):
        logger.warning('I need a passphrase to continue - rescheduling.')
        Sched = django_rq.get_scheduler()
        Sched.enqueue_in(datetime.timedelta(minutes=30), Pull, covername=covername)
        exit()

    passphrase = file(TTS.PASSPHRASE_CACHE).read()

    try: Ratchet_Objects.decrypt_database(passphrase)
    except thirtythirty.exception.Target_Exists: pass
    
    Me = addressbook.utils.my_address()
    
    try:
        Resp = addressbook.gpg.pull_from_keyserver(covername=covername)
        
    except addressbook.exception.MultipleMatches as Matches:
        logger.debug(Matches)
#        address.user_state = addressbook.address.Address.FAIL
#        address.save()
        emailclient.utils.submit_to_smtpd(Payload="""The upstream server returned many keys for "%s".
This is exciting new territory in errors!  Please fill out a bug report!  Thank you!
""" % covername,
      Destination=Me.email,
      Subject='FATAL problem - many users go by "%s"' % covername,
      From='Sysop <root>')
            
    except addressbook.exception.NoKeyMatch:
        logger.debug('No matches')
#        address.user_state = addressbook.address.Address.FAIL
#        address.save()
        emailclient.utils.submit_to_smtpd(Payload="""No upstream server knows "%s".
This may be a typo in the covername - please bother a developer to write the synonym code in a bug report!  Thank you!
""" % covername,
      Destination=Me.email,
      Subject='FATAL problem - no one by the name of "%s"' % covername,
      From='Sysop <root>')
            
    except addressbook.exception.KeyserverTimeout:
        logger.debug('Keyservers all timed out - TEMPFAIL')
        emailclient.utils.submit_to_smtpd(Payload="""The upstream server seems to have experienced a temporary problem during key lookup for "%s".
We'll try again in a bit and see if it magically starts working.
""" % covername,
      Destination=Me.email,
      Subject='Temporary problem - key lookup for "%s"' % covername,
      From='Sysop <root>')
        Sched = django_rq.get_scheduler('default')
        Sched.enqueue_in(datetime.timedelta(minutes=30), Pull, covername=covername)
