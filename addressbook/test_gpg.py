
from django.test import TestCase

import addressbook

class GPGTest(TestCase):
    def test_only_one_me(self):
        addressbook.address.Address.objects.rebuild_addressbook()
        self.assertEqual(addressbook.address.Address, type(addressbook.utils.my_address()))


    def test_decrypt_symmetric(self):
        ciphertext = """-----BEGIN PGP MESSAGE-----
Version: GnuPG v1.4.12 (GNU/Linux)

jA0EAwMC+ID6ZtW1vi9gySIwhXUWySDl46i4sVGAsbD8h60uYts6ZTONbeWf3lpE
O1Dd
=+no9
-----END PGP MESSAGE-----"""
        self.assertEqual('test message',
                         addressbook.gpg.decrypt(ciphertext,
                                     passphrase='1234').data)


    def test_encrypt_symmetric(self):
        plaintext = 'test message'
        ciphertext = addressbook.gpg.symmetric(msg=plaintext,
                                   passphrase='1234').data
        self.assertEqual(plaintext,
                         addressbook.gpg.decrypt(ciphertext,
                                     passphrase='1234').data)


