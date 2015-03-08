
from django.core.management.base import BaseCommand

from optparse import make_option

import getpass
from os.path import exists
from subprocess import call

import addressbook.gpg
import thirtythirty.exception
import ratchet
import smp.models

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = '<NONE>'
    help = 'Lock/Unlock/Restore databases manually'
    option_list = BaseCommand.option_list + (
        make_option('--verbose',
                    action='store_true',
                    default=False,
                    dest='verbose',
                    help='Puke out more info'
                    ),
        make_option('--unlock',
                    action='store_const',
                    dest='mode',
                    const='unlock',
                    default=None,
                    help='Decrypt ratchet database',
                    ),
        make_option('--lock',
                    action='store_const',
                    dest='mode',
                    const='lock',
                    default=None,
                    help='Encrypt ratchet database',
                    ),
        make_option('--recover',
                    action='store_const',
                    dest='mode',
                    const='recover',
                    default=None,
                    help='Recover ratchet database',
                    ),
        make_option('--headless',
                    action='store_true',
                    default=False,
                    dest='headless',
                    help='Headless operation - do not prompt for passphrase'
                    ),
        make_option('-p', '--passphrase',
                    action='store',
                    default=None,
                    dest='passphrase',
                    help='Specify passphrase on commandline (lazy and bad and gives you warts)'),
        )

    
    def handle(self, *args, **settings):
        if ((exists(TTS.PASSPHRASE_CACHE)) and (not settings['passphrase'])):
            settings['passphrase'] = file(TTS.PASSPHRASE_CACHE, 'r').read()

        if not settings['passphrase'] and not settings['headless']:
            settings['passphrase'] = getpass.getpass()

        if not addressbook.gpg.verify_symmetric(settings['passphrase']):
            if not settings['headless']:
                logger.critical('JACKHOLED - password wrong.')
                exit(-1)
            else:
                # silent exit for cron
                exit()

        ratchet.conversation.Conversation.objects.init_for('ratchet')
        smp.models.SMP.objects.init_for('smp')

        if settings['mode'] == 'lock':
            try: ratchet.conversation.Conversation.objects.encrypt_database(settings['passphrase'])
            except thirtythirty.exception.Target_Exists as e:
                if settings['verbose']: logger.warning(e)
            except thirtythirty.exception.Missing_Database as e:
                if settings['verbose']: logger.warning(e)
            try: smp.models.SMP.objects.encrypt_database(settings['passphrase'])
            except thirtythirty.exception.Target_Exists as e:
                if settings['verbose']: logger.warning(e)
            except thirtythirty.exception.Missing_Database as e:
                if settings['verbose']: logger.warning(e)
                
        elif settings['mode'] == 'unlock':
            try: ratchet.conversation.Conversation.objects.decrypt_database(settings['passphrase'])
            except thirtythirty.exception.Target_Exists: pass
            try: smp.models.SMP.objects.decrypt_database(settings['passphrase'])
            except thirtythirty.exception.Target_Exists: pass
            
        elif settings['mode'] == 'recover':
            ratchet.conversation.Conversation.objects.recover_database(settings['passphrase'])
            smp.models.SMP.objects.recover_database(settings['passphrase'])
