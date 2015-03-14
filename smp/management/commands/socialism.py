
from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Q

import os.path
import getpass
from optparse import make_option
from uuid import uuid4

import addressbook
import ratchet
import smp.models
import thirtythirty

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

SMP_Objects = smp.models.SMP.objects
SMP_Objects.init_for('smp')

class Command(BaseCommand):
    args = '<None>'
    help = 'Manage contact authentication states'

    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    default=False,
                    dest='dump',
                    help='List authentication states'),
        make_option('--init',
                    action='store',
                    default=False,
                    dest='init',
                    help='Initialize socialism'),
        make_option('--secret',
                    action='store',
                    default=False,
                    dest='secret',
                    help='Set secret'),
        make_option('--resend',
                    action='store',
                    default=False,
                    dest='resend',
                    help='Resend last message (only works if message was lost in transit)'),
        make_option('--delete',
                    action='store',
                    default=False,
                    dest='delete',
                    help='Delete conversation'),
        make_option('-p', '--passphrase',
                    action='store',
                    default=False,
                    dest='passphrase',
                    help='Specify passphrase on commandline (lazy and bad and gives you warts)'),
        )


    def __lookup_address(self, Search_Term=None):
        Who = addressbook.address.Address.objects.filter(
            is_me=False,
            system_use=False,
            ).filter(
            Q(covername__icontains=Search_Term) |\
            Q(nickname__icontains=Search_Term) |\
            Q(email__icontains=Search_Term) |\
            Q(fingerprint__icontains=Search_Term))
        if len(Who) > 1:
            print 'Too broad - I got these results: %s' % Who
            return None
        elif len(Who) == 0:
            print 'Unfound.'
            return None
        else:
            return Who[0]


    def handle(self, *args, **settings):
        if not settings['passphrase']:
            if os.path.exists(TTS.PASSPHRASE_CACHE):
                fh = file(TTS.PASSPHRASE_CACHE, 'r')
                settings['passphrase'] = fh.read()
            else:
                settings['passphrase'] = getpass.getpass()

        try: SMP_Objects.decrypt_database(settings['passphrase'])
        except thirtythirty.exception.Target_Exists: pass

        if settings['dump']:
            print smp.models.SMP.objects.all()
            exit()

        if settings['delete']:
            Who = self.__lookup_address(settings['delete'])
            if not Who: exit(-1)
            S = smp.models.SMP.objects.filter(UniqueKey=Who.fingerprint)
            if len(S) == 1:
                print 'Demoting %s to merely secure.' % Who.email
                S[0].remove(fail=True)
            exit()

        if settings['resend']:
            Who = self.__lookup_address(settings['resend'])
            if not Who: exit(-1)
            Resend = addressbook.queue.Queue.objects.filter(
                address=Who,
                direction=addressbook.queue.Queue.SMP_Replay).order_by('-modified').first()
            if Resend:
                print 'Found a saved state - resendering'
                logger.debug('Found a saved state - resendering')
                Resend.direction = addressbook.queue.Queue.TX
                Resend.save()
            else:
                print 'I have no saved state for %s and so suck and fail' % Who.email
                logger.critical('I have no saved state for %s and so suck and fail' % Who.email)
                Who.smp_failures = models.F('smp_failures') + 1
                Who.save()
                addressbook.queue.Queue.objects.filter(address=Who,
                                                       direction=addressbook.queue.Queue.SMP_Replay,
                                                       ).delete()
                S.delete()
            exit()

        if settings['init'] or settings['secret']:
            Search_Term = settings['init'] or settings['secret']
            Who = self.__lookup_address(Search_Term)
            if not Who: exit(-1)
            if Who.user_state > addressbook.address.Address.VETTING:
                print 'I already know: %s' % Who.email
                exit(-1)

            try: Ratchet_Objects.decrypt_database(settings['passphrase'])
            except thirtythirty.exception.Target_Exists: pass

            Convo = ratchet.conversation.Conversation.objects.get(
                UniqueKey = Who.fingerprint
                )
            
            S = smp.models.SMP.objects.filter(UniqueKey=Who.fingerprint)
            if len(S) == 0:
                print 'What is your secret question (this will be **UNENCRYPTED**)?',
                Question = raw_input()
                print 'What shared secret would you like?',
                Secret = raw_input()
                S = smp.models.SMP.objects.hash_secret(
                    Conversation = Convo,
                    passphrase = settings['passphrase'],
                    question = Question,
                    secret = Secret)
                Who.user_state = addressbook.address.Address.VETTING
                Who.save()
                if S.IAmAlice:
                    Body = S.advance_step()
                    print 'Initiating contact'
                else:
                    # a "please Alice at me" packet...
                    Body = smp.models.SMPStep(Question=Question).dumps()
                    S.step = 1
                    S.save()
                    print 'Asking for initial packet'
                if addressbook.queue.Queue.objects.filter(address=Who,
                                                          direction=addressbook.queue.Queue.TX
                                                          ).count() == 0:
                    addressbook.queue.Queue.objects.create(
                        address = Who,
                        body = Convo.encrypt(plaintext=Body),
                        direction = addressbook.queue.Queue.TX,
                        message_type = addressbook.queue.Queue.SOCIALISM,
                        messageid=str(uuid4()),
                        )
                    print 'Queued SMP step to %s' % Who.email
                    QR = addressbook.queue.QRunner()
                    QR.Run(passphrase=settings['passphrase'])
                else:
                    print 'SMP step already queued to %s' % Who.email
            elif len(S) == 1 and settings['init']:
                print 'Already initialized - awaiting response'
            elif len(S) == 1 and settings['secret']:
                S = S[0]
                print 'The secret question you have received: `%s`' % S.Question
                print 'Enter secret, plz?',
                Secret = raw_input()
                S.create_secret(secret=Secret)
                QR = addressbook.queue.QRunner()
                QR.Run(passphrase=settings['passphrase'])
