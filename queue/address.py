
from django.db.models import Q

import datetime
import django_rq
from django_rq import job

import addressbook
import thirtythirty

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@job
def Reset(fingerprint=None, covername=None):
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

    Addr = addressbook.address.objects.filter(
        Q(fingerprint=fingerprint) |\
        Q(covername=covername))

    if len(Addr) != 1:
        logger.critical('Got an address reset request with multiple matches: %s' % Addr)
        exit(-1)

    logger.debug('Request for %s state reset granted' % Addr[0])
    Addr[0].delete_local_state(passphrase)


@job
def Expire_Expired():
    if not thirtythirty.hdd.drives_are_unlocked():
        logger.warning('Drives not unlocked yet.')
        Sched = django_rq.get_scheduler('default')
        Sched.enqueue_in(datetime.timedelta(hours=1), Expire_Expired)
        exit()    

    for E in addressbook.address.Address.objects.filter(expires__lt=datetime.date.today()):
        logger.debug('Contact %s has an expired key' % E)
        E.user_state = addressbook.address.Address.FAIL
        E.save()


@job
def TX_Handshake(fingerprint=None,
                   loop_protection=False,
                   reset_request=False,
                   ):
    # check / load passphrase cache
    # get or create conversation based on fingerprint
    # verify we're sending to a .onion domain
    # add loop_protection header if enabled
    # add reset_request header if enabled
    # queue handshake to SMTP with above headers
    pass

        
@job
def RX_Handshake(fingerprint=None, handshake=None):
    # check / load passphrase cache
    # decrypt encrypted handshake
    # reset from-address address state if handshake is unintelligible
    # if we don't have a conversation associated with handshake's fingerprint, start one
    # if we already have a shaken conversation, enable loop protection and resend our half of the shake
    # handshake the conversation, if we error out reset it
    # advance address user_state
    pass


# unpack axolotl into its own routine?


@job
def RX_Socialist_Millionaire(fingerprint=None, axolotl=None, symmetric=None):
    # check / load passphrase cache
    # verify address user_state hasn't already been authenticated
    # if conversation doesn't exist, delay requeue this message and await handshake
    # if SMP state object doesn't exist, initialize it
    # decrypt axolotl
    # if decrypt fails, reply with SMP reset request and demote user_state
    # if decrypt contains SMP reset request, reset SMP
    # if my SMP isn't fully initialized, symmetric encrypt the decrypt and requeue
    # advance SMP state
    # if more steps remain, queue reply
    # if SMP fails, reinitialize SMP and set user_state
    # if SMP matches, remove SMP and advance user_state
    pass
