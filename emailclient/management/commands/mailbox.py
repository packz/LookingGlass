
from django.core.management.base import BaseCommand

from optparse import make_option

import emailclient.filedb

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
            if len(args) == 0:
                args = ['']
            for Folder in args:
                for Msg in emailclient.filedb.sorted_messages_in_folder(folderName=Folder):
                    print emailclient.filedb.msg_key_from_msg(Msg)
        else:
            for MsgID in args:
                Msg = emailclient.filedb.fast_folder_find(MsgID).get(MsgID)
                if Msg:
                    print Msg

