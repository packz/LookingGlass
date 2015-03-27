
from django.core.management.base import BaseCommand

from optparse import make_option

import getpass
import os

import thirtythirty.exception as TTE
import thirtythirty.hdd as TTH
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '<NONE>'
    help = 'Initialization of the LookingGlass environment'
    option_list = BaseCommand.option_list + (
        make_option('-p', '--pass', '--passphrase',
                    action='store',
                    dest='passphrase',
                    default=None,
                    help='Set (new) passphrase',
                    ),
        make_option('--unlock',
                    action='store_true',
                    dest='unlock',
                    default=False,
                    help='Unlock drives',
                    ),
        make_option('--key-file',
                    action='store',
                    dest='keyfile',
                    default=None,
                    help='Use keyfile rather than key on commandline',
                    ),
        make_option('-l', '--old',
                    action='store',
                    dest='old',
                    default=None,
                    help='When changing passphrase, this is previous key',
                    ),
        make_option('--dump', '--list', '--print',
                    action='store_true',
                    dest='print',
                    default=False,
                    help='Show status',
                    ),
        make_option('--csv',
                    action='store_true',
                    dest='csv',
                    default=False,
                    help='Show status as CSV',
                    ),
        make_option('--create',
                    action='store',
                    dest='create',
                    default=None,
                    help='Create a single volume'),
        make_option('--create-all',
                    action='store_true',
                    dest='create_all',
                    default=False,
                    help='Create all logical volumes',
                    ),
        make_option('--change-pw',
                    action='store_true',
                    dest='changepw',
                    default=False,
                    help='Update passphrase',
                    ),
        make_option('--delete',
                    action='store',
                    dest='delete',
                    default=None,
                    help='Remove a logical volume',
                    ),
        make_option('--decimate',
                    action='store_true',
                    dest='decimate',
                    default=False,
                    help='Remove all logical volumes',
                    ),
        )


    def handle(self, *args, **settings):
        if os.path.exists(TTS.LUKS['key_file']):
            settings['passphrase'] = file(TTS.LUKS['key_file'], 'r').read()
        if settings['keyfile'] and os.path.exists(settings['keyfile']):
            settings['passphrase'] = file(settings['keyfile'], 'r').read()
        if not settings['passphrase']:
            settings['passphrase'] = getpass.getpass()

        if settings['print'] or settings['csv']:
            for V in TTH.Volumes(unlisted=False):
                if settings['print']:
                    print V
                if settings['csv']:
                    print V.csv()
            exit(0)

        if settings['decimate']:
            for V in TTH.Volumes(unlisted=False):
                V.lock()
                try: V.remove()
                except: pass
            for F in ['gpg.key', 'covername', 'drive.key', 'luks.key']:
                try: os.unlink('/run/shm/%s' % F)
                except: pass
            try: os.unlink(TTS.GPG['export'])
            except: pass
            exit()

        if not settings['passphrase']:
            print 'Need a passphrase to do that.'
            exit(-1)

        if settings['unlock']:
            for V in TTH.Volumes():
                if not V.is_mounted():
                    try:
                        V.unlock(settings['passphrase'])
                    except TTE.CannotStartLuks:
                        logger.warning('Bad passphrase on %s' % V.Name)
                        exit(-1)
            exit()
                    
        if settings['create'] or settings['delete']:
            for V in TTH.Volumes(unlisted=True):
                if V.Name == settings['create']:
                    V.create(settings['passphrase'])
                if V.Name == settings['delete']:
                    V.remove()
                    
        if settings['create_all']:
            for V in TTH.Volumes(unlisted=False):
                V.create(settings['passphrase'])

        if settings['changepw']:
            for V in TTH.Volumes(unlisted=False):
                V.change_passphrase(new=settings['passphrase'], old=settings['old'])
