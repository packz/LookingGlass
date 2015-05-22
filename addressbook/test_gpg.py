
from django.test import TestCase

import addressbook

PASSPHRASE = file('/run/shm/email.key', 'r').read()

class GPGTest(TestCase):
    # def test_only_one_me(self):
    #     addressbook.address.Address.objects.rebuild_addressbook()
    #     logger.warning( addressbook.utils.my_address() )
    #     self.assertEqual(addressbook.address.Address, type(addressbook.utils.my_address()))


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


    def test_decrypt_asymmetric(self):
        ciphertext = """-----BEGIN PGP MESSAGE-----
Version: GnuPG v1.4.12 (GNU/Linux)

hQIMA82Edzlay3K8AQ//Q7PWOE+vvGkavcHeCGOs9TnrspqSMMnfPARL17g3M1ds
YoAHMgCJOT35HqoeQgN6cTdNsXjA9Gee22KyZrVyG0XkePPbJ8axs2OPOv40m0BU
JG9rZdJsEs3FoX/LTMIrf/mmZB+Wq0C2Tge9YNd7qCHc/UkLPLoR/B/VOPwY+GZp
k+2Csa6wCNR+pzntdWPtJW7DzzoADEhLE3QA2g35WRnf3Yc06hyDtFsqdgbN5Yzy
UZ6VBYvcUFA+Weu8ScDtVGOb7fz/hRIy7bcbvE9i2q1YxrOjY/zfYNy89wOH7dE8
Us0n270efOfH6GZHS5KdTDQCHvFrSRtDR1+fKtW/GB0txQ4l+WU51HhWgrf8D5dO
OBGpZaHRbtXyBPLbpUuAM0exRaWh3Lyh3oea+UCO+nvLBmldbjVar7TYgypeJeM6
QCCZR/dXzPUZlGneAK7/xK61BsMqbp6fBkgyb1+QAkyEMiptBR3+Z5vQ63iUZJw4
NOcQmWlqjfmOGNyTp8nPRtP4GEPS2EIa+1Iqje/p/jhsn1E6nXzXL+UzMEGb7H/Z
C19/IGMqpaMvbsLTgG4gZcpmukZAokHPVYowHcbYV1gnf90zzlcL3JsDzpe7oo5G
1ycQRwffAQv9W+cS1lydiPZ/GCOWMalSs651e5AdhFJltoF6zEj1bkF+VJQXdH3S
RQGpNEcQovcrnnyEcgmfeiDumB7Wfv2DoI1lKp/JVDqDVIrYTZF+V+EB2gDgj4iW
VWOY0twi3xzNYYgW/hHNFju93YPkmg==
=a3ze
-----END PGP MESSAGE-----
        """
        plaintext = 'fuck you.\n'
        self.assertEqual(plaintext,
                         addressbook.gpg.decrypt(ciphertext,
                                                 passphrase=PASSPHRASE).data)
        
