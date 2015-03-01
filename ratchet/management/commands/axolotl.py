
from django.db.models import Q
from django.core.management.base import BaseCommand

import getpass
from optparse import make_option
import os
from sys import stdin
from uuid import uuid4

import addressbook
import emailclient.utils
import ratchet
import thirtythirty.exception
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '[COVERNAME|FINGERPRINT|EMAIL|NICKNAME]'
    help = 'Axolotl management interface'
    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    default=False,
                    dest='dump',
                    help='Show current conversation states'),
        make_option('--detail',
                    action='store_true',
                    default=False,
                    dest='detail',
                    help='Show detailed conversation states'),
        make_option('--export',
                    action='store_true',
                    dest='export',
                    default=False,
                    help='Export handshake'),
        make_option('--autosend',
                    action='store_true',
                    dest='autosend',
                    default=False,
                    help='Queue exported handshake to email automatically'),
        make_option('--import',
                    action='store_true',
                    dest='import',
                    default=False,
                    help='Import handshake'),
        make_option('--verify',
                    action='store_true',
                    dest='verify',
                    default=False,
                    help='Verify a fingerprint'),
        make_option('--delete',
                    action='store_true',
                    dest='delete',
                    default=False,
                    help='Delete a conversation'),
        make_option('--subject',
                    action='store',
                    default=None,
                    dest='subject',
                    help='encrypted message subject'),
        make_option('--encrypt',
                    action='store_true',
                    dest='encrypt',
                    default=False,
                    help='Encrypt message'),
        make_option('--decrypt',
                    action='store_true',
                    dest='decrypt',
                    default=False,
                    help='Decrypt message - CAUTION: advances ratchet (only works once)'),
        make_option('-t', '--optimistic',
                    action='store_true',
                    dest='optimism',
                    default=False,
                    help='Optimistic decrypt - TRY ALL THE THINGS'),
        make_option('-p', '--passphrase',
                    action='store',
                    default=False,
                    dest='passphrase',
                    help='Specify passphrase on commandline (lazy and bad and gives you warts)'),
        )
            

    def handle(self, *args, **settings):
        if settings['encrypt'] and settings['decrypt']:
            logger.error('Those are mutually exclusive options.')
            exit(-1)

        if not settings['passphrase']:
            if os.path.exists(TTS.PASSPHRASE_CACHE):
                fh = file(TTS.PASSPHRASE_CACHE, 'r')
                settings['passphrase'] = fh.read()
            else:
                P = getpass.getpass()
                C = getpass.getpass('Confirm:')
                if P != C:
                    logger.error("Don't match - wah wah.")
                    exit(-1)
                settings['passphrase'] = P

        # decrypt the ratchet database
        ratchet.conversation.Conversation.objects.init_for('ratchet')
        try:
            ratchet.conversation.Conversation.objects.decrypt_database(settings['passphrase'])
        except thirtythirty.exception.Target_Exists:
            pass

        if settings['delete']:
            Sucksess = False
            for Arg in args:
                for Addr in addressbook.address.Address.objects.filter(
                    is_me = False,
                    system_use = False,
                    ).filter(
                    Q(covername__icontains=Arg) |\
                    Q(nickname__icontains=Arg) |\
                    Q(email__icontains=Arg) |\
                    Q(fingerprint__icontains=Arg)):
                    try:
                        ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint).delete()
                    except: pass
                    Addr.user_state = addressbook.address.Address.KNOWN
                    Addr.save()
                    print 'Demoting %s to KNOWN' % Addr.email
                    Sucksess = True
            if not Sucksess:
                print 'Obstinately deleted NOTHING'

        if settings['dump']:
            print '#{:^41}{:^41} {:^4}{:^40}'.format('My_FP', 'Their_FP', 'Tx/Rx', 'Address')
            for C in ratchet.conversation.Conversation.objects.all():
                FP = C.UniqueKey
                print '{:^42}{:^41} {:^4}'.format(C.my_fingerprint(), C.their_fingerprint(), '%02d/%02d' % (C.NumberTx, C.NumberRx)),
                A = addressbook.address.Address.objects.filter(fingerprint=FP).first()
                if A: print A.email
                else: print FP
            exit()

        if settings['detail']:
            if ((len(args) == 0) or (args[0] == 'all')):
                for Addr in addressbook.address.Address.objects.all():
                    try:
                        Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
                        print Addr.covername, Convo
                    except ratchet.conversation.Conversation.DoesNotExist: pass
                    
            else:
                for Arg in args:
                    for Addr in addressbook.address.Address.objects.filter(
                        is_me = False,
                        system_use = False,
                        ).filter(
                        Q(covername__icontains=Arg) |\
                        Q(nickname__icontains=Arg) |\
                        Q(email__icontains=Arg) |\
                        Q(fingerprint__icontains=Arg)):
                        try:
                            Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
                            print Addr.covername, Convo
                        except ratchet.conversation.Conversation.DoesNotExist: pass
            exit()

        if ((settings['optimism']) and (len(args) == 0) and (settings['decrypt'])):
            args = [ x.fingerprint for x in addressbook.address.Address.objects.filter(
                is_me = False,
                system_use = False).all() ]
            logger.debug('ALL the conversations: %s' % args)

        if settings['import']:
            logger.debug('Attempting to import handshake')
            try:
                HS = ratchet.handshake.EncryptedHandshake(Import=stdin.read(),
                                                          Passphrase=settings['passphrase'])
            except ratchet.exception.Bad_Passphrase:
                logger.critical('Cannot decrypt that handshake.  Fail.')
                return
            Addr = addressbook.address.Address.objects.get(fingerprint=HS.FPrint)
            logger.debug('Handshake found for %s' % Addr)
            if Addr.user_state != addressbook.address.Address.KNOWN:
                logger.warning('...but %s are not in the proper frame of mind to shake.' % Addr)
                return
            try:
                Convo = ratchet.conversation.Conversation.\
                        objects.get(UniqueKey=Addr.fingerprint)
            except ratchet.conversation.Conversation.DoesNotExist:
                Convo = ratchet.conversation.Conversation.\
                        objects.initiate_handshake_for(
                    unique_key=Addr.fingerprint,
                    passphrase=settings['passphrase'])
            Convo.greetings(HS)
            Convo.save()
            if Addr.user_state == addressbook.address.Address.KNOWN:
                Addr.user_state = addressbook.address.Address.NOT_VETTED
                Addr.save()
        
        if (settings['encrypt'] or settings['decrypt'] or
            settings['export'] or
            settings['verify']):
            Found_One = False
            for Arg in args:
                for Addr in addressbook.address.Address.objects.filter(
                    is_me = False,
                    system_use = False,
                    ).filter(
                    Q(covername__icontains=Arg) |\
                    Q(nickname__icontains=Arg) |\
                    Q(email__icontains=Arg) |\
                    Q(fingerprint__icontains=Arg)):
                    Found_One = True
                    if settings['export']:
                        if Addr.user_state >= addressbook.address.Address.NOT_VETTED:
                            logger.warning('%s is already shook one' % Addr.email)
                        if settings['autosend']:
                            logger.debug('Queuing an Axolotl SYN to %s' % Addr.email)
                            addressbook.queue.Queue.objects.create(
                                address = Addr,
                                direction = addressbook.queue.Queue.TX,
                                message_type = addressbook.queue.Queue.AXOLOTL,
                                messageid=str(uuid4()),
                                )
                        else:
                            try:
                                Convo = ratchet.conversation.Conversation.\
                                        objects.get(UniqueKey=Addr.fingerprint)
                            except ratchet.conversation.Conversation.DoesNotExist:
                                Convo = ratchet.conversation.Conversation.\
                                        objects.initiate_handshake_for(
                                    unique_key=Addr.fingerprint,
                                    passphrase=settings['passphrase'])
                            print Convo.my_handshake(Passphrase=settings['passphrase'])
                    elif settings['verify']:
                        Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
                        Convo.verify_fingerprint(True)
                        print Addr.covername, Convo
                    elif settings['encrypt']:
                        Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
                        logger.debug('Conversation loaded')
                        print 'Conversation loaded - EOF to send'
                        Payload = stdin.read()
                        PL = Convo.encrypt(Payload)
                        emailclient.utils.submit_to_smtpd(Payload=PL,
                                                          Destination=Addr.email,
                                                          Subject=settings['subject'])
                        logger.debug('Encrypted - queued to %s' % Addr.email)
                        print 'Enqueued and sending.'
                    elif settings['decrypt']:
                        try:
                            Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
                        except:
                            continue
                        logger.debug('Conversation loaded')
                        Payload = stdin.read()
                        try:
                            print Convo.decrypt(Payload)
                        except ratchet.exception.Vanished_MessageKey:
                            logger.critical('Message already decrypted: keys are gone.')
                        except ratchet.exception.Undecipherable:
                            logger.critical("Message undecipherable: didn't make a lick of sense")
                    else:
                        Found_One = False

            if not Found_One:
                logger.error("Couldn't find a user.  :(")
            else:
                QR = addressbook.queue.QRunner()
                QR.Run(passphrase=settings['passphrase'])
