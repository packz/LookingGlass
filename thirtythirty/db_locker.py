
from os import rename, chmod
from os.path import exists
from stat import S_IRUSR, S_IWUSR
from shutil import copyfile
from subprocess import call

import cStringIO
import sqlite3

import addressbook
import emailclient
import thirtythirty

import logging
logger = logging.getLogger(__name__)


def alert_user_auto_recovery():
    Me = addressbook.utils.my_address()
    emailclient.utils.submit_to_smtpd(
        Payload="""
        I lost my databases!
        This can happen when power is pulled (say in an emergency) without hitting LOCKDOWN.
        I will recover the last known state they were in, but you may need to redo any recent traffic.
        Both inbound and outbound email will be affected.
        A competent designer will fix this at some point in the future, sorry.
        """,
        Destination=Me.email,
        Subject='Uh oh, here comes inconvenience.',
        From='Sysop <root>')


def alert_user_serious_badness():
    Me = addressbook.utils.my_address()
    for A in addressbook.address.Address.objects.filter(is_me=False, system_use=False):
        A.user_state = addressbook.address.Address.KNOWN
        A.save()
    emailclient.utils.submit_to_smtpd(
        Payload="""
        I lost my databases!
        I tried to recover them, but I can't even find the backups.
        We've failed so safe, we gotta start over.
        The best I can do is get you a copy of your contact list - you'll have to reauthenticate them.
        I'm very sorry.
        Please contact support, and we will attempt to help.
        """,
        Destination=Me.email,
        Subject='TOTAL OBLITERATION',
        From='Sysop <root>')


class LockManager(object):
    Test = {
        'BACKUP':'/tmp/test.gpg~',
        'LOCKED':'/tmp/test.gpg',
        'NAME':'/run/shm/test.sqlite',
        }
    
    def init_for(self, db_name=None):
        if db_name:
            self.__backup  = thirtythirty.settings.DATABASES[db_name]['BACKUP']
            self.__decrypt = thirtythirty.settings.DATABASES[db_name]['NAME']
            self.__encrypt = thirtythirty.settings.DATABASES[db_name]['LOCKED']
        else:  # test harness
            self.__backup  = self.Test['BACKUP']
            self.__decrypt = self.Test['NAME']
            self.__encrypt = self.Test['LOCKED']

    
    def recover_database(self):
        logger.debug('recovering %s' % self.__backup)
        copyfile(self.__backup,
                 self.__encrypt)


    def encrypt_database(self, passphrase=None, location=None):
        """
        location is only used for test framework - do not use
        """
        if exists(self.__encrypt):
            raise(thirtythirty.exception.Target_Exists('Already locked?'))
        if not addressbook.gpg.verify_symmetric(passphrase=passphrase, location=location):
            raise(thirtythirty.exception.Bad_Passphrase('I refuse to use some crazy password'))
        if not exists(self.__decrypt):
            raise(thirtythirty.exception.Missing_Database('Holy crap, no database either?  HOZED.'))
        conn = sqlite3.connect(self.__decrypt)
        dump = cStringIO.StringIO()
        for D in conn.iterdump():
            dump.write('%s\n' % D)
        conn.close()
        dump.seek(0)
        K = addressbook.gpg.symmetric(dump,
                                      filename=self.__encrypt,
                                      passphrase=passphrase)
        dump.close()
        logger.debug('encrypted %s to %s' % (self.__decrypt, self.__encrypt))
        if K and K.ok:
            call(['/usr/bin/shred', '--force', '--remove', self.__decrypt])
            logger.debug('shredded %s' % self.__decrypt)
            return True
        else:
            logger.critical('encrypting %s failed' % self.__decrypt)
            raise(thirtythirty.exception.Locking_Problem('Encryption failed'))


    def decrypt_database(self, passphrase=None, loop_protector=False, location=None):
        """
        location only used for testing, to pass thru to verify_symmetric
        """
        if exists(self.__decrypt):
            raise(thirtythirty.exception.Target_Exists('Already unlocked?'))
        if not addressbook.gpg.verify_symmetric(passphrase=passphrase, location=location):
            raise(thirtythirty.exception.Bad_Passphrase('I refuse to use some crazy password'))
        if not exists(self.__encrypt):
            if not loop_protector:
                # engage autorecovery
                logger.critical('Whoops!  Database got deleted out from under us.')
                alert_user_auto_recovery()
                self.recover_database()
                return self.decrypt_database(passphrase, True)
            else:
                logger.critical('Okay, shit is really fucked up.')
                alert_user_serious_badness()
                raise(thirtythirty.exception.Missing_Database('Holy crap, no database either?  HOZED.'))
        cryptid = file(self.__encrypt, 'rb').read()
        logger.debug('decrypted %s to %s' % (self.__encrypt, self.__decrypt))
        K = addressbook.gpg.decrypt(cryptid,
                                    passphrase=passphrase)
        if K and K.ok:
            conn = sqlite3.connect(self.__decrypt)
            chmod(self.__decrypt, S_IRUSR | S_IWUSR)
            conn.executescript(K.data)
            conn.commit()
            conn.close()
            rename(self.__encrypt, self.__backup)
            return True
        else:
            logger.critical('decrypting %s failed' % self.__encrypt)
            raise(thirtythirty.exception.Locking_Problem('Decryption failed'))
