
from django.db import models

from os import rename, chmod
from os.path import exists
from stat import S_IRUSR, S_IWUSR
from shutil import copyfile
from subprocess import call

import cStringIO
import sqlite3

from thirtythirty.settings import DATABASES
import exception
import addressbook

import logging
logger = logging.getLogger(__name__)


class LockManager(object):
    Test = {
        'BACKUP':'/tmp/test.gpg~',
        'LOCKED':'/tmp/test.gpg',
        'NAME':'/run/shm/test.sqlite',
        }
    
    def init_for(self, db_name=None):
        if db_name:
            self.__backup  = DATABASES[db_name]['BACKUP']
            self.__decrypt = DATABASES[db_name]['NAME']
            self.__encrypt = DATABASES[db_name]['LOCKED']
        else:  # test harness
            self.__backup  = self.Test['BACKUP']
            self.__decrypt = self.Test['NAME']
            self.__encrypt = self.Test['LOCKED']

    
    def recover_database(self):
        logger.debug('recovering %s' % self.__backup)
    	copyfile(self.__backup,
                 self.__encrypt)


    def encrypt_database(self, passphrase=None):
        if exists(self.__encrypt):
            raise(exception.Target_Exists('Already locked?'))
	if not addressbook.gpg.verify_symmetric(passphrase):
            raise(exception.Bad_Passphrase('I refuse to use some crazy password'))
        if not exists(self.__decrypt):
            raise(exception.Missing_Database('Holy crap, no database either?  HOZED.'))
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
            call(['/usr/bin/shred', '--remove', self.__decrypt])
            logger.debug('shredded %s' % self.__decrypt)
            return True
	else:
            logger.critical('encrypting %s failed' % self.__decrypt)
            raise(exception.Locking_Problem('Encryption failed'))


    def decrypt_database(self, passphrase=None):
        if exists(self.__decrypt):
            raise(exception.Target_Exists('Already unlocked?'))
        if not addressbook.gpg.verify_symmetric(passphrase):
            raise(exception.Bad_Passphrase('I refuse to use some crazy password'))
        if not exists(self.__encrypt):
            raise(exception.Missing_Database('Holy crap, no database either?  HOZED.'))
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
            raise(exception.Locking_Problem('Decryption failed'))
