
from django.core.management.base import BaseCommand

from optparse import make_option

import redis
import rq
import django_rq

import time

import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)


@django_rq.job
def test_testerson():
    logger.debug('start')
    time.sleep(10)
    logger.debug('end')


class Command(BaseCommand):
    args = '<NONE>'
    help = 'RQ interface'

    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    dest='dump',
                    default=False,
                    help='Dump queue contents',
                    ),
        )

    def handle(self, *args, **settings):
        if settings['dump']:
            q = rq.Queue(connection=redis.Redis())
            print len(q), q.jobs
        else:
            print 'here we go!'
            test_testerson.delay()
            print 'did it!'
