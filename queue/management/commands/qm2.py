
from django.core.management.base import BaseCommand

from optparse import make_option

import django_rq

import queue
import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)


@django_rq.job
def test_task():
    import time
    logger.debug('start')
    time.sleep(10)
    logger.debug('end')


class Command(BaseCommand):
    args = '<NONE>'
    help = 'RQ interface'

    option_list = BaseCommand.option_list + (
        make_option('--test',
                    action='store_true',
                    dest='test',
                    default=False,
                    help='Push a test task onto the queue',
                    ),
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    dest='dump',
                    default=False,
                    help='Dump queue contents',
                    ),
        make_option('--register',
                    action='store_true',
                    dest='register',
                    default=False,
                    help='Push registration task onto the queue',
                    ),                    
        )

    def handle(self, *args, **settings):
        if settings['dump']:
            import redis
            import rq
            q = rq.Queue(connection=redis.Redis())
            print len(q), q.jobs
        elif settings['test']:
            print 'here we go!'
            test_testerson.delay()
            print 'did it!'
        elif settings['register']:
            queue.keyserver.Push.delay()
