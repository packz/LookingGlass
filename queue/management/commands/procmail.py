
from django.core.management.base import BaseCommand

import sys
import email
from os.path import exists

import django_rq

import addressbook
import emailclient
import queue

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = None
    help = 'Parse email on stdin into queue'

    def handle(self, *args, **settings):
        Raw = sys.stdin.read()
        Msg = email.message_from_string(Raw)
        MType = addressbook.utils.msg_type(Raw)
        Payload = emailclient.utils.text_payload(Msg)
        Queue = django_rq.get_queue()
        if not 'X-Lookingglass-Overhead' in Msg:
            logger.error("Message doesn't have our X-header, is this actually destined for the user?")
            exit(-1)
            
        if Msg['Message-Id'] in Queue.job_ids:
            logger.error('Already inserted this message into queue.')
            exit(-1)
        
        if MType == 'PGP-CLEARSIGN':
            From_Addr = addressbook.address.objects.message_detective(Msg)
            if not From_Addr:
                logger.error('Unknown GPG clearsign')
                exit(-1)

            # bcast message -> Queue

        elif MType == 'AXO-HS':
            From_Addr = addressbook.address.objects.message_detective(Msg)
            if not From_Addr:
                logger.info('Got an unanticipated handshake from %s' % Msg['Reply-To'])
                KSP = django_rq.enqueue(queue.keyserver.Pull, email=Msg['Reply-To'])
                django_rq.enqueue(queue.address.Got_Handshake, fingerprint=KSP.result, handshake=Payload,
                                  job_id=Msg['Message-Id'],
                                  depends_on=RST,
                                  )
                exit()
                                
            if 'X-Lookingglass-Address-Reset' in Msg:
                RST = django_rq.enqueue(queue.address.Reset, fingerprint=From_Addr.fingerprint)
                django_rq.enqueue(queue.address.Got_Handshake, fingerprint=From_Addr.fingerprint, handshake=Payload,
                                  job_id=Msg['Message-Id'],
                                  depends_on=RST,
                                  )
                exit()
            
            elif 'X-Lookingglass-Axo-Loop' in Msg:
                Sched = django_rq.get_scheduler('default')
                Sched.enqueue_in(datetime.timedelta(minutes=30),
                                 queue.address.Got_Handshake, fingerprint=From_Addr.fingerprint, handshake=Payload,
                                 job_id=Msg['Message-Id'])
                exit()

            django_rq.enqueue(queue.address.Got_Handshake, fingerprint=From_Addr.fingerprint, handshake=Payload,
                              job_id=Msg['Message-Id'])
