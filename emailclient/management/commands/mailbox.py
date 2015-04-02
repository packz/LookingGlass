
from django.core.management.base import BaseCommand

from optparse import make_option

import emailclient.email

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '[MAILBOX|KEYS...]'
    help = 'Mailbox commands'

    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    default=False,
                    dest='dump',
                    help='Dump message keys'),
        )

    def handle(self, *args, **settings):
        if settings['dump']:
            
