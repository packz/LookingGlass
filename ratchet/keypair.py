
from django.db import models

from curve25519 import keys as ECkey

#import ratchet

class Keypair(models.Model):
    tx = models.BinaryField(null=True)
    rx = models.BinaryField(null=True)
    prv = models.BinaryField(null=True)

    class Meta:
        abstract = True


    def __unicode__(self):
        return u'T=%s/R=%s/P=%s' % (
            ratchet.utils.human_readable(self.tx),
            ratchet.utils.human_readable(self.rx),
            ratchet.utils.human_readable(self.prv))


    def genEC(self):
        key = ECkey.Private()
        self.tx = key.get_public().serialize()
        self.prv = key.private
        return self.prv, self.tx


# oh, the chagrin
class HeaderKey(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='HeaderKey')

class NextHeader(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='NextHeader')

class ChainKey(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='ChainKey')

class DHIdentity(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='DHIdentity')

class DHRatchet(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='DHRatchet')

class Handshake(Keypair):
    Convo = models.OneToOneField('Conversation',
                              related_name='Handshake')
