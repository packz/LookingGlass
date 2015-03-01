
from django.core.management.base import BaseCommand
from django.db.models import Q

import datetime
import email
import sys
import getpass
from optparse import make_option
from os.path import exists
from uuid import uuid4

import addressbook
import emailclient.utils

from thirtythirty.settings import PASSPHRASE_CACHE

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '[QUEUE_IDs...]'
    help = 'Manage asynchronous queue'

    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    default=False,
                    dest='dump',
                    help='Dump queue contents'),
        make_option('--delete',
                    action='store_true',
                    default=False,
                    dest='delete',
                    help='Delete by ID'),
        make_option('--register',
                    action='store_true',
                    default=False,
                    dest='register',
                    help='Push a public key registration request into the queue'),
        make_option('--cname', '--covername', '--cn',
                    action='store',
                    default=None,
                    dest='covername',
                    help='Push a covername query into the queue'),
        make_option('--fprint', '--fingerprint', '--fp',
                    action='store',
                    default=None,
                    dest='fingerprint',
                    help='Push a fingerprint query into the queue'),
        make_option('--run',
                    action='store_true',
                    default=False,
                    dest='queue_run',
                    help='Execute any pending queue requests'),
        make_option('--procmail',
                    action='store_true',
                    default=False,
                    dest='procmail',
                    help='Parse emails into queue'),
        make_option('-p', '--passphrase',
                    action='store',
                    default=False,
                    dest='passphrase',
                    help='Specify passphrase on commandline (lazy and bad and gives you warts)'),
        )

    def procmail(self):
        Raw = sys.stdin.read()
        Msg = email.message_from_string(Raw)
        MType = addressbook.utils.msg_type(Raw)
        Payload = emailclient.utils.text_payload(Msg)
        if not 'X-Lookingglass-Overhead' in Msg:
            logger.warning("Message doesn't have our X-header, is this actually destined for the user?")
            return False
        if addressbook.queue.Queue.objects.filter(messageid=Msg['Message-Id']).count() != 0:
            logger.warning('Already inserted this message into queue: %s' % Msg['Message-Id'])
            return None
        if MType == 'PGP-CLEARSIGN':
            Addr = addressbook.address.objects.message_detective(Msg)
            if not Addr:
                logger.warning('Unknown GPG clearsign: %s' % Msg['Message-Id'])
                return False
            if not Addr.system_use:
                logger.error('GPG clearsign from a non-system account: %s' % Msg['Message-Id'])
                return False
            logger.debug('Got a clearsign system request %s' % Payload)
            addressbook.queue.Queue.objects.create(address=Addr,
                                                   body=Payload,
                                                   messageid=Msg['Message-Id'],
                                                   direction=addressbook.queue.Queue.RX,
                                                   message_type=addressbook.queue.Queue.SERVER_INFO)
        
        elif MType == 'AXO-HS':
            I_Know_You = False
            try:
                Addr = addressbook.address.Address.objects.get(email__iexact=Msg['Reply-To'])
                I_Know_You = True
            except addressbook.address.Address.DoesNotExist:
                # procmail() is assumed run from procmailrc, so cannot expect passphrase to run the queue
                logger.error('Need to query the keyserver for unanticipated handshake: %s' % Msg['Reply-To'])
                Addr = addressbook.address.Address.objects.add_by_covername(Msg['Reply-To'])
            # we need to add the HS to the queue even as we seek info about the shaker
            if I_Know_You and addressbook.queue.Queue.objects.filter(address=Addr,
                                                                     messageid=Msg['Message-Id'],
                                                                     direction=addressbook.queue.Queue.RX,
                                                                     message_type=addressbook.queue.Queue.AXOLOTL).count() != 0:
                logger.warning('Already have a Axolotl handshake queued via %s' % Msg['Message-Id'])
                return True
            if 'X-Lookingglass-Axo-Loop' in Msg:
                RL = addressbook.utils.time_lock()
                if RL.is_locked('QUEUE'):
                    logger.critical('We may have a loop here.  Proactively stall out until we get things straight.')
                    return False
            logger.debug('Axolotl handshake queued from %s' % Msg['From'])
            addressbook.queue.Queue.objects.create(address=Addr,
                                                   body=Payload,
                                                   messageid=Msg['Message-Id'],
                                                   direction=addressbook.queue.Queue.RX,
                                                   message_type=addressbook.queue.Queue.AXOLOTL)

        elif MType == 'AXO-MSG':
            try:
                Addr = addressbook.address.Address.objects.get(email__iexact=Msg['From'])
            except addressbook.address.Address.DoesNotExist:
                logger.error('We got an Axolotl message from %s without an associated conversation' % Msg['From'])
                return False
            logger.debug('Axolotl message recieved - treating it as an SMP payload.')
            addressbook.queue.Queue.objects.create(address=Addr,
                                                   body=Payload,
                                                   messageid=Msg['Message-Id'],
                                                   direction=addressbook.queue.Queue.RX,
                                                   message_type=addressbook.queue.Queue.SOCIALISM)
        else:
            logger.error('Message type is out of place: %s' % Msg['Message-Id'])
            return False

        # finally...
        return True


    def handle(self, *args, **settings):
        # manage GPG key expiration
        for E in addressbook.address.Address.objects.filter(expires__lt=datetime.date.today()):
            E.user_state = addressbook.address.Address.FAIL
            E.save()
        
        if settings['dump']:
            print addressbook.queue.Queue.objects.all()
            exit()

        elif settings['procmail']:
            P = self.procmail()
            Exit = -1
            if ((P is True) or (P is None)):
                Exit = 0
            if exists(PASSPHRASE_CACHE):
                settings['passphrase'] = file(PASSPHRASE_CACHE).read()
                QR = addressbook.queue.QRunner()
                QR.Run(passphrase=settings['passphrase'])
            exit(Exit)

        elif settings['delete']:
            for QID in args:
                addressbook.queue.Queue.objects.filter(id=QID).delete()
            print addressbook.queue.Queue.objects.all()
            exit()

        if not settings['passphrase']:
            if exists(PASSPHRASE_CACHE):
                settings['passphrase'] = file(PASSPHRASE_CACHE).read()
            else:
                P = getpass.getpass()
                C = getpass.getpass('Confirm:')
                if P != C:
                    print "Don't match - wah wah."
                    exit(-1)
                settings['passphrase'] = P
        if not settings['passphrase']:
            print 'idk wtf - passphrase failure all round'
            exit(-1)

        if not addressbook.gpg.verify_symmetric(settings['passphrase']):
            print 'Bad passphrase - *bonk*'
            exit(-1)

        if settings['covername']:
            print addressbook.address.Address.objects.add_by_covername(settings['covername'])
            QR = addressbook.queue.QRunner()
            QR.Run(passphrase=settings['passphrase'])            
            exit()

        elif settings['fingerprint']:
            print addressbook.address.Address.objects.add_by_fingerprint(settings['fingerprint'])
            QR = addressbook.queue.QRunner()
            QR.Run(passphrase=settings['passphrase'])
            exit()

        elif settings['register']:
            MyCN = addressbook.utils.my_address().covername
            if addressbook.queue.Queue.objects.filter(body=MyCN).count() != 0:
                print 'Looks like that is already enqueued'
                exit(-1)
            addressbook.queue.Queue.objects.create(address=addressbook.utils.my_address(),
                                                   direction=addressbook.queue.Queue.TX,
                                                   messageid=str(uuid4()),
                                                   message_type=addressbook.queue.Queue.GPG_PK_PUSH,
                                                   body=MyCN)
            QR = addressbook.queue.QRunner()
            QR.Run(passphrase=settings['passphrase'])
            exit()

        if settings['queue_run']:
            QR = addressbook.queue.QRunner()
            QR.Run(passphrase=settings['passphrase'])
