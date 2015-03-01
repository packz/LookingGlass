
from django.core.management.base import BaseCommand

from optparse import make_option

import addressbook
import emailclient

import thirtythirty.updater as TTU
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '[Server_URI]'
    help = 'System upgrader'

    option_list = BaseCommand.option_list + (
        make_option('--force',
                    action='store_true',
                    dest='force',
                    default=False,
                    help="Override rate limiter",
                    ),
        make_option('--install',
                    action='store_true',
                    dest='install',
                    default=False,
                    help="Install!  WHAO!  WARNING!",
                    ),
        make_option('--validate-anything-with-bits', '--megagape',
                    action='store_true',
                    dest='valid_override',
                    default=False,
                    help="I don't give a rip if the signature isn't valid",
                    ),
        )


    def alert_user_new_updates(self,
                               Version=None,
                               ChangeLog=None):
        Me = addressbook.utils.my_address()
        PL = """
        A newer version of LookingGlass is available!
        
        To install it, go to "Settings" in the navbar (next to LOCKDOWN).
        Open the "System administration" tab.
        Click "Update".
        ~CROSS YOUR FINGERS~
        ~WAIT FOR POSSIBLE REBOOT~
        ~DO NOT REMOVE POWER~
        ~BITE NAILS~
        Enjoy!"""
        if ChangeLog:
            PL += """\n\n\n\n\n\nCHANGELOG:
----------
%s
""" % ChangeLog
        emailclient.utils.submit_to_smtpd(
            # FIXME: need some way to |safe this.
            Payload=PL,
            Destination=Me.email,
            Subject='New update available: %s' % Version,
            From='Sysop <root>')

    def handle(self, *args, **settings):
        Cached = TTU.Available()
        if Cached:
            if not settings['force']:
                logger.debug('Already have version %s in cache' % Cached)
                exit(0)
            else:
                logger.debug('Already have version %s in cache' % Cached)
                logger.debug('Specified new dl anyway')
            
        URI = TTU.Scan(TTS.UPSTREAM['updates'][0]['uri'])
        if not URI and not settings['force']:
            logger.debug('Already up to date')
            exit(0)
        
        Cache = TTU.Cache(Data_URI=URI)
        logger.debug('Got %s' % Cache)
        
        if not TTU.Validate(Cache):
            if not settings['valid_override']:
                logger.warning('Invalid signature on %s' % Cache)
                exit(-1)
            else:
                logger.warning('Bad signature, but signature override is on...')

        self.alert_user_new_updates(
            Version=TTU.Version(Cache),
            ChangeLog=TTU.ChangeLog(Cache)
            )

        if settings['install']:
            for F in TTU.Unpack(Cache):
                logger.debug(F)
                
            TTU.Cleanup()
