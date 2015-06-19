
from django.core.management.base import BaseCommand

from optparse import make_option

import django_rq
from django_rq import job

import addressbook
import queue
from queue.utils import Passphrase_or_requeue

import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)


def test_task(wtf=None):
    import time
    logger.warning('start: %s' % wtf)
    time.sleep(10)
    logger.warning('stop: %s' % wtf)

    
@Passphrase_or_requeue
def test_secret_task(wtf=None, Passphrase=None):
    import time
    logger.warning('start: %s / %s' % (wtf, Passphrase))
    time.sleep(10)
    logger.warning('stop: %s / %s' % (wtf, Passphrase))

    

class Command(BaseCommand):
    args = '<NONE>'
    help = 'RQ interface'

    option_list = BaseCommand.option_list + (
        make_option('--test',
                    action='store_true',
                    dest='test',
                    default=False,
                    help='Test task for the queue',
                    ),
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    dest='dump',
                    default=False,
                    help='Dump queue contents',
                    ),
        make_option('--register', '--push',
                    action='store_true',
                    dest='register',
                    default=False,
                    help='Push registration to keyservers',
                    ),
        make_option('--pull',
                    action='store',
                    dest='pull',
                    default=None,
                    help='Pull covername PULL from keyservers',
                    ),
        make_option('--flush-schedule', '--fs',
                    action='store_true',
                    dest='flush_schedule',
                    default=False,
                    help='Delete (flush) scheduled tasks',
                    ),
        make_option('--unlock',
                    action='store_true',
                    dest='unlock',
                    default=False,
                    help='Drive unlock',
                    ),
        )

    def showStats(self):
        import pprint
        q = django_rq.get_queue()
        qp = django_rq.get_queue('needs_passphrase')
        s = django_rq.get_scheduler()
        pp = pprint.PrettyPrinter()
        print
        print 'Job Queue:'
        pp.pprint( q.jobs )
        pp.pprint( qp.jobs )
        print
        print 'Scheduled tasks:'
        pp.pprint( s.get_jobs(with_times=True) )
        print
    
    def handle(self, *args, **settings):
        if settings['test']:
            print 'here we go!'
            NP = django_rq.get_queue('needs_passphrase')
            DF = django_rq.get_queue()
            NP.enqueue(test_task)
            DF.enqueue(test_secret_task)
            print 'did it!'
        elif settings['register']:
            queue.keyserver.Push.delay()
        elif settings['pull']:
            django_rq.enqueue(queue.keyserver.Pull, covername=settings['pull'])
        elif settings['flush_schedule']:
            S = django_rq.get_scheduler()
            for Task in S.get_jobs():
                S.cancel(Task)
            self.showStats()
        elif settings['unlock']:
            queue.hdd.Unlock.delay()
        else:
            self.showStats()
