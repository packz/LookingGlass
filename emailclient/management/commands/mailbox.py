
from django.core.management.base import BaseCommand

import getpass
from optparse import make_option

import emailclient.filedb

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '<None>'
    help = 'Mailbox commands'

    option_list = BaseCommand.option_list + (
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    default=False,
                    dest='dump',
                    help='Dump mailbox contents'),
        )

    def handle(self, *args, **settings):
        for Msg in emailclient.filedb.sorted_messages_in_folder(folderName=''):
            print emailclient.filedb.msg_key_from_msg(Msg)
