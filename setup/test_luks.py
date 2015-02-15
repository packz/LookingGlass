
from django.test import TestCase
from django.db import IntegrityError

from os.path import exists
from shutil import copyfile
import os
import subprocess

import luks

class LUKSTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        LV = 'testing'
        Testing = luks.Mount_Map[LV]
        try: os.remove(Testing['keyfile'])
        except OSError: pass
        try: os.remove('%s.old' % Testing['keyfile'])
        except OSError: pass
        luks.remove()


    def test_all(self):
        LV = 'testing'
        Testing = luks.Mount_Map[LV]
        file(Testing['keyfile'], 'w').write('test')
        
        luks.create(Logical_Volume=LV,
                    Key_File=Testing['keyfile'])
        luks.lock(Logical_Volume=LV)

        file(Testing['keyfile'], 'w').write('test')
        luks.unlock(Logical_Volume=LV,
                    Key_File=Testing['keyfile'])

        copyfile(Testing['keyfile'], '%s.old' % Testing['keyfile'])
        file(Testing['keyfile'], 'w').write('changed')

        luks.change_passphrase(Logical_Volume=LV,
                               Key_File=Testing['keyfile'])
        luks.resize(Logical_Volume=LV)
        luks.lock(Logical_Volume=LV)
