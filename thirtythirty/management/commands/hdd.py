
from django.core.management.base import BaseCommand

from optparse import make_option

import getpass
import os
import time

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
        make_option('--lock',
                    action='store_true',
                    dest='lock',
                    default=False,
                    help='Lock drives',
                    ),
        make_option('--unlock',
                    action='store_true',
                    dest='unlock',
                    default=False,
                    help='Unlock drives',
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
        make_option('--crypttab',
                    action='store_true',
                    dest='crypttab',
                    default=False,
                    help='print out default crypttab',
                    ),
        make_option('--fstab',
                    action='store_true',
                    dest='fstab',
                    default=False,
                    help='print out default fstab',
                    ),
        )


    def handle(self, *args, **settings):
        if settings['lock']:
            for V in TTH.Volumes():
                V.lock()
            exit(0)

        if settings['print'] or settings['csv']:
            for V in TTH.Volumes(unlisted=False):
                if settings['print']:
                    print V
                if settings['csv']:
                    print V.csv()
            exit(0)

        if settings['decimate']:
            print "This will PERMANENTLY erase the LUKS volumes.  Are you sure? (Type 'YES')",
            Y = raw_input()
            if Y != 'YES':
                print 'Your drives remain safe'
                exit(-1)
            print 'HOSING EVERYTHING WITH PAIN IN FIVE - AWAIT PAIN'
            time.sleep(5)
            print 'PAIN INBOUND'
            for V in TTH.Volumes(unlisted=False):
                V.lock()
                try: V.remove()
                except: pass
            for F in ['gpg.key', 'covername', 'drive.key', 'luks.key']:
                try: os.unlink('/dev/shm/%s' % F)
                except: pass
            try: os.unlink(TTS.GPG['export'])
            except: pass
            exit()

        if os.path.exists(TTS.LUKS['key_file']):
            settings['passphrase'] = file(TTS.LUKS['key_file'], 'r').read()
        if not settings['passphrase']:
            settings['passphrase'] = getpass.getpass()

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


        fmt = {}
        fmt['username'] = getpass.getuser()

        if settings['crypttab']:
            print '''
# <target name>	<source device>		<key file>	<options>

# This group gets set up with a dynamic passphrase on boot

# <target name>	<source device>		<key file>	<options>
swp		/dev/LookingGlass/swp		/dev/urandom	swap
tmp		/dev/LookingGlass/tmp		/dev/urandom	tmp=ext2,precheck=/bin/true,,size=256,hash=sha256,cipher=aes-cbc-essiv:sha256
log		/dev/LookingGlass/log		/dev/urandom	tmp=ext2,precheck=/bin/true,,size=256,hash=sha256,cipher=aes-cbc-essiv:sha256

# This group gets set up via the web interface

# <target name>	<source device>			<key file>		<options>
tor_var		/dev/LookingGlass/tor_var	/run/shm/luks.key	noauto,luks
testing		/dev/LookingGlass/testing	/run/shm/luks.key	noauto,luks
postfix_etc	/dev/LookingGlass/postfix_etc	/run/shm/luks.key	noauto,luks
pi_mail		/dev/LookingGlass/pi_mail	/run/shm/luks.key	noauto,luks
pi_gpg		/dev/LookingGlass/pi_gpg	/run/shm/luks.key	noauto,luks
pi_electrum	/dev/LookingGlass/pi_electrum	/run/shm/luks.key	noauto,luks
'''

        if settings['fstab']:
            print '''# random passphrase on reboot
/dev/mapper/swp	    	none		swap	sw			0	0
/dev/mapper/tmp		/tmp		ext2	defaults,noatime	0	0
/dev/mapper/log		/var/log	ext2	defaults,noatime	0	0

# managed by LG
/dev/mapper/tor_var		/var/lib/tor	    ext4    noauto,noatime	0	0
/dev/mapper/postfix_etc		/etc/postfix        ext4    noauto,noatime	0	0
/dev/mapper/pi_mail		/home/%(username)s/Maildir    ext4    noauto,noatime	0	0
/dev/mapper/pi_gpg		/home/%(username)s/.gnupg	    ext4    noauto,noatime	0	0
/dev/mapper/pi_electrum		/home/%(username)s/.electrum  ext4    noauto,noatime	0	0
/dev/mapper/testing		/mnt/testing	    ext4    noauto,noatime	0	0
''' % fmt