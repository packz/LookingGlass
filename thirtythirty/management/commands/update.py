
from django.core.management.base import BaseCommand

from optparse import make_option

import addressbook
import emailclient

import thirtythirty.updater
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = '[Server_URI]'
    help = 'System upgrader'

    option_list = BaseCommand.option_list + (
        make_option('--check',
                    action='store_true',
                    dest='check',
                    default=False,
                    help="Check for updates and download to cache",
                    ),
        make_option('--force',
                    action='store_true',
                    dest='force',
                    default=False,
                    help="Override rate limiter",
                    ),
        make_option('--email-user',
                    action='store_true',
                    dest='email',
                    default=False,
                    help="Email local admin re: update available",
                    ),
        make_option('--install',
                    action='store_true',
                    dest='install',
                    default=False,
                    help="Install!  WHAO!  WARNING!",
                    ),
        make_option('--validate-anything-with-bits', '--no-check', '--megagape',
                    action='store_true',
                    dest='valid_override',
                    default=False,
                    help="I don't give a rip if the signature isn't valid",
                    ),
        )


    def alert_user_new_updates(self, Version=None):
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
        Enjoy!
        """
        # FIXME: add changelog / notes here
        emailclient.utils.submit_to_smtpd(
            # FIXME: need some way to |safe this.
            Payload=PL,
            Destination=Me.email,
            Subject='New update available: %s' % Version,
            From='Sysop <root>')

    def handle(self, *args, **settings):
        U = thirtythirty.updater.Updater()            
        
        GMR = U.GetMostRecent(asString=True)
        UDA = U.MoreRecentAvailable()
        if not UDA:
            logger.debug('Already up to date - on %s, found %s' % (TTS.LOOKINGGLASS_VERSION_STRING, GMR))
            exit(0)

        logger.debug('Found a new version: %s' % GMR)
        
        DL = U.Download()
        logger.debug('Downloaded version %02d.%02d.%02d' % (int(DL[0]), int(DL[1]), int(DL[2])))

        Fingerprint = U.ClearsignedBy()
        if not Fingerprint:
            logger.error('Signature hosed or no signature.')
            exit(-1)

        ok = False
        if Fingerprint in TTS.UPSTREAM['trusted_prints']:
            ok = True

        A = U.Validate(Fingerprint)
        if not A.system_use and not settings['valid_override']:
            logger.error("fingerprint for %s isn't marked system_use - refusing to update" % A.covername)
            exit(-1)

        if not A.system_use and settings['valid_override']:
            logger.warning('fingerprint for %s is bogus -- but check was overrided!' % A.covername)
            ok = True

        if settings['check'] and ok:
            # FIXME: need a rate limiter.
            self.alert_user_new_updates('%02d.%02d.%02d' % (int(DL[0]), int(DL[1]), int(DL[2])))
            exit(0)
                    
        if ((not settings['check']) and
            (ok) and
            (settings['install'])):
            File_List = U.Unpack()
            logger.debug('unpacked %s files' % len(File_List))
            fh = file(TTS.UPSTREAM['update_log'], 'w')
            for File in File_List:
                fh.write(File)
                fh.write('\n')
            fh.close()
            logger.debug('wrote update log to %s' % TTS.UPSTREAM['update_log'])
            U.Cleanup()
