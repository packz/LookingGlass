
from django.core.management.base import BaseCommand

from optparse import make_option

import getpass
import os

import addressbook
import thirtythirty.bug_report as TTBR
import thirtythirty.hdd as TTH
import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '<NONE>'
    help = 'Emergency bug report'

    option_list = BaseCommand.option_list + (
        make_option('-p', '--pass', '--passphrase',
                    action='store',
                    dest='passphrase',
                    default=None,
                    help='Specify passphrase',
                    ),
        )

    def handle(self, *args, **settings):
        if not TTU.query_daemon_states('tor'):
            print "I can't send a bug report without tor running."
            
        for V in TTH.Volumes():
            if not V.is_mounted():
                if os.path.exists(TTS.LUKS['key_file']) and not settings['passphrase']:
                    settings['passphrase'] = file(TTS.LUKS['key_file'], 'r').read()
                if not settings['passphrase']:
                    settings['passphrase'] = getpass.getpass()
                try:
                    V.unlock(settings['passphrase'])
                except TTE.CannotStartLuks:
                    logger.warning('Bad passphrase on %s' % V.Name)
                    exit(-1)

        BR = TTBR.Bug_Report()
        BR.send(settings['passphrase'])
        if settings['passphrase'] and addressbook.gpg.verify_symmetric(settings['passphrase']):
            print 'Sent an encrypted major bug report'
        else:
            print 'Sent an unencrypted major bug report'
