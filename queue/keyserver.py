
from django.db import models
from django.db.models import Q

import django_rq
from django_rq import job
import datetime

import addressbook
import emailclient
import ratchet

import logging
logger = logging.getLogger(__name__)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

@job
def Push():
    logger.debug('Pushing')
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
def Pull(address=None):
    try: Ratchet_Objects.decrypt_database(passphrase)
    except thirtythirty.exception.Target_Exists: pass
    
    Me = addressbook.utils.my_address()

    try:
        Resp = addressbook.gpg.pull_from_keyserver(covername=address.covername)            
    except addressbook.exception.MultipleMatches as Matches:
        logger.debug(Matches)
        address.user_state = addressbook.address.Address.FAIL
        address.save()
        emailclient.utils.submit_to_smtpd(Payload="""The upstream server returned many keys for "%s".
This is exciting new territory in errors!  Please fill out a bug report!  Thank you!
""" % address.covername,
      Destination=Me.email,
      Subject='FATAL problem - many users go by "%s"' % Message.address.covername,
      From='Sysop <root>')
            
    except addressbook.exception.NoKeyMatch:
        logger.debug('No matches')
        address.user_state = addressbook.address.Address.FAIL
        address.save()
        emailclient.utils.submit_to_smtpd(Payload="""No upstream server knows "%s".
This may be a typo in the covername - please bother a developer to write the synonym code in a bug report!  Thank you!
""" % Message.address.covername,
      Destination=Me.email,
      Subject='FATAL problem - no one by the name of "%s"' % Message.address.covername,
      From='Sysop <root>')
            
    except addressbook.exception.KeyserverTimeout:
        logger.debug('Keyservers all timed out - TEMPFAIL')
        emailclient.utils.submit_to_smtpd(Payload="""The upstream server seems to have experienced a temporary problem during key lookup for "%s".
We'll try again in a bit and see if it magically starts working.
""" % Message.address.covername,
      Destination=Me.email,
      Subject='Temporary problem - key lookup for "%s"' % Message.address.covername,
      From='Sysop <root>')
        Sched = django_rq.get_scheduler('default')
        Sched.enqueue_at(datetime.timedelta(minutes=30), Push(address))
