
from django.core.management.base import BaseCommand

from optparse import make_option

import os.path

import addressbook
import emailclient

import thirtythirty.utils as TTUtil
import thirtythirty.updater as TTUp
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
                    help="DO IT NO STAHP",
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
        if os.path.exists(TTS.UPSTREAM['update_lock']): return
        Me = addressbook.utils.my_address()
        PL = """
        A newer version of LookingGlass is available!
        
        To install it, go to "Settings" in the navbar (next to LOCKDOWN).
        Open the "Updates" tab.
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
        TTUtil.popen_wrapper(['/bin/touch',
                               TTS.UPSTREAM['update_lock']],
                              sudo=False)

    def handle(self, *args, **settings):            
        URI = TTUp.Scan(TTS.UPSTREAM['updates'][0]['uri'])
        if not URI and not settings['force']:
            logger.debug('Already up to date')
            exit(0)

        if not settings['force'] and os.path.exists(TTS.UPSTREAM['update_lock']):
            # we probably have something genuinely email-worthy to talk about
            os.unlink(TTS.UPSTREAM['update_lock'])

        Cache = TTUp.Update_Cache(Data_URI=URI,
                                  Checksum_URI='%s.sum.asc' % URI)
        if Cache:
            logger.debug('Got %s' % Cache)

        Cache = TTUp.Available()
        if not Cache:
            logger.warning('Nothing new in cache - bailing')
            exit()
        logger.debug('Reloading from cache: %s' % Cache['version'])
        
        if not TTUp.Validate(Cache['filename']):
            if not settings['valid_override']:
                logger.warning('Invalid signature on %s' % Cache['filename'])
                exit(-1)
            else:
                logger.warning('Bad signature, but signature override is on...')

        self.alert_user_new_updates(
            Version=TTUp.Version(Cache['filename']),
            ChangeLog=TTUp.ChangeLog(Cache['filename'])
            )

        if settings['install']:
            for F in TTUp.Unpack(Cache['filename']):
                logger.debug(F)
                
            TTUp.Cleanup()
