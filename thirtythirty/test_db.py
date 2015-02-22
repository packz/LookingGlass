
from django.test import TestCase
from django.db import IntegrityError

from os.path import exists
import os
import sqlite3
import datetime

import thirtythirty.exception
import thirtythirty.db_locker

class DatabaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        D = thirtythirty.db_locker.LockManager()
        for X in ['NAME', 'LOCKED', 'BACKUP']:
            try: os.remove(D.Test[X])
            except OSError: pass


    @classmethod
    def tearDownClass(cls):
        D = thirtythirty.db_locker.LockManager()
        for X in ['NAME', 'LOCKED', 'BACKUP']:
            try: os.remove(D.Test[X])
            except OSError: pass


    def setUp(self):
        self.make_empty_db()
        
    
    def make_empty_db(self):
        D = thirtythirty.db_locker.LockManager()
        if exists(D.Test['NAME']): return
        conn = sqlite3.connect(D.Test['NAME'],
                               detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        curs = conn.cursor()
        curs.execute("""
        create table 'cockblocker9000' (
        'suckweasel' varchar(10),
        'devonian' datetime default current_timestamp
        );""")
        curs.execute("""
        insert into 'cockblocker9000' (suckweasel) values (
        'BITCHTITS'
        );""")
        conn.commit()
        conn.close()
        
    
    def test_bad_passwd(self):
        D = thirtythirty.db_locker.LockManager()
        D.init_for()
        self.assertRaises(thirtythirty.exception.Bad_Passphrase, D.encrypt, '1235')


    def check_decrypt_within_time_limit(self, D):
        Now = datetime.datetime.now()
        Too_Old = datetime.timedelta(minutes=2)
        conn = sqlite3.connect(D.Test['NAME'],
                               detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        curs = conn.cursor()
        curs.execute("""
        select devonian as "[timestamp]" from cockblocker9000 limit 1;
        """)
        self.assertEqual((Now - curs.fetchone()[0]) > Too_Old, False)


    def check_creates_backup(self, D):
        D.decrypt('1234')
        self.assertEqual(exists(D.Test['BACKUP']), True)
        self.assertEqual(exists(D.Test['LOCKED']), False)
        self.assertEqual(exists(D.Test['NAME']), True)
        self.check_decrypt_within_time_limit(D)
        

    def test_encrypt(self):
        D = thirtythirty.db_locker.LockManager()
        D.init_for()
        self.assertEqual(exists(D.Test['LOCKED']), False)
        self.assertEqual(exists(D.Test['NAME']), True)
        D.encrypt('1234')
        self.assertEqual(exists(D.Test['LOCKED']), True)
        self.assertEqual(exists(D.Test['NAME']), False)
        self.check_creates_backup(D)
