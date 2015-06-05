
from types import StringType, DictType

import addressbook
import ratchet

import logging
logger = logging.getLogger(__name__)


def HandshakeFactory(*args, **kwargs):
    """
    <Slipknot>
    Come on down, to the HandshakeFactory yeah
    Gonna shake your /mind/
    Snakes and shit

    Boo, fucking skeletons are in there
    Magnets, how do they woooooooooooooooork!?
    HandshakeFactory HandshakeFactory HandshakeFactory

    ~27 minute guitar solo~
    </Metallica>
    """
    try:
        strip_pwd = kwargs.copy()
        strip_pwd.pop('Passphrase', None)
        return AnonymousHandshake(*args, **strip_pwd)
    except ratchet.exception.Broken_Format: pass
    return EncryptedHandshake(*args, **kwargs)
    

class AnonymousHandshake(ratchet.utils.b64Formatter):
    def __init__(self,
                 DHIdentityTx=None,
                 HandshakeTx=None,
                 DHRatchetTx=None,
                 Covername=None,
                 Import=None):
        sFormat = """-----BEGIN AXOLOTL HANDSHAKE-----
Version: %s

%s-----END AXOLOTL HANDSHAKE-----"""
        rFormat = """(?smx) # dotall, multiline, verbose
^\-\-\-\-\-BEGIN\ AXOLOTL\ HANDSHAKE\-\-\-\-\-\W
^Version:\ [^\n]+\W+
^\W+
^(?P<Payload>.+)\W+
^\-\-\-\-\-END\ AXOLOTL\ HANDSHAKE\-\-\-\-\-"""
        Fields = [
            'Covername',
            'DHIdentityTx',
            'DHRatchetTx',
            'HandshakeTx',
            ]
        super(AnonymousHandshake, self
              ).__init__(str_format = sFormat,
                         re_format = rFormat,
                         repr_show=Fields)
        self.Covername = Covername
        if DHIdentityTx and HandshakeTx and DHRatchetTx:
            self.set_hs(DHIdentityTx=DHIdentityTx,
                        HandshakeTx=HandshakeTx,
                        DHRatchetTx=DHRatchetTx)
        if Import:
            self.loads(Import=Import)


    def set_hs(self, DHIdentityTx=None,
               DHRatchetTx=None,
               HandshakeTx=None,):
        self.DHIdentityTx = DHIdentityTx
        self.DHRatchetTx = DHRatchetTx
        self.HandshakeTx = HandshakeTx


    def loads(self, Import=None):
        jPayload = self.deserialize(Import)
        if type(jPayload) is StringType:
            raise(ratchet.exception.Broken_Format(
                'I think this may be an encrypted, not anonymous, handshake'))
        for K, V in self.from_b64(jPayload).items():
            setattr(self, K, V)


    def dumps(self):
        bPayload = self.to_b64({
            'b64_DHIdentityTx':self.DHIdentityTx,
            'b64_DHRatchetTx':self.DHRatchetTx,
            'b64_HandshakeTx':self.HandshakeTx,
            'nonce':100,
            })
        return self.serialize(bPayload)



class EncryptedHandshake(ratchet.utils.b64Formatter):
    def __init__(self,
                 DHIdentityTx=None,
                 HandshakeTx=None,
                 DHRatchetTx=None,
                 Passphrase=None,
                 Import=None,):
        sFormat = """-----BEGIN AXOLOTL HANDSHAKE-----
Version: %s

%s-----END AXOLOTL HANDSHAKE-----"""
        rFormat = """(?smx) # dotall, multiline, verbose
^\-\-\-\-\-BEGIN\ AXOLOTL\ HANDSHAKE\-\-\-\-\-\W
^Version:\ [^\n]+\W+
^\W+
^(?P<Payload>.+)\W+
^\-\-\-\-\-END\ AXOLOTL\ HANDSHAKE\-\-\-\-\-"""
        Fields = [
            'DHIdentityTx',
            'DHRatchetTx',
            'HandshakeTx',
            ]
        self.FPrint = None
        self.DHIdentityTx = None
        self.HandshakeTx = None
        super(EncryptedHandshake, self
              ).__init__(str_format = sFormat,
                         re_format = rFormat,
                         repr_show=Fields)
        self.set_hs(DHIdentityTx=DHIdentityTx,
                    HandshakeTx=HandshakeTx,
                    DHRatchetTx=DHRatchetTx)
        if Import and Passphrase:
            self.loads(Import=Import,
                       Passphrase=Passphrase)


    def set_hs(self, DHIdentityTx=None,
               DHRatchetTx=None,
               HandshakeTx=None):
        if DHIdentityTx: self.DHIdentityTx = DHIdentityTx
        if DHRatchetTx: self.DHRatchetTx = DHRatchetTx
        if HandshakeTx: self.HandshakeTx = HandshakeTx


    def loads(self, Import=None,
              Passphrase=None):
        xPayload = self.deserialize(Import)
        if type(xPayload) is DictType:
            raise(ratchet.exception.Actually_Anonymous('This is an anonymous handshake'))
        jPayload = addressbook.gpg.decrypt(xPayload,
                                           passphrase=Passphrase)
        if not jPayload:
            raise(ratchet.exception.Bad_Passphrase(
                'Could not decrypt our handshake'))
        self.FPrint = jPayload.pubkey_fingerprint or jPayload.key_id
        Payload = self.deserialize(jPayload.data)
        for K, V in self.from_b64(Payload).items():
            if K == 'FPrint':
                logger.warning('Someone tried to slip me a fingerprint...')
                continue
            setattr(self, K, V)


    def dumps(self, to_fp=None,
              Passphrase=None):
        to_encode = {
            'b64_DHIdentityTx':self.DHIdentityTx,
            'b64_HandshakeTx':self.HandshakeTx,
            'nonce':100,
            }
        if hasattr(self, 'DHRatchetTx'):
            to_encode['b64_DHRatchetTx'] = self.DHRatchetTx
        bPayload = self.to_b64(to_encode)
        jPayload = self.serialize(Payload=bPayload,
                                  b64=False,
                                  Format=False)
        To_Whom = addressbook.address.Address.objects.get(fingerprint=to_fp)
        xPayload = To_Whom.asymmetric(msg=jPayload,
                                      passphrase=Passphrase,
                                      armor=False,)
        if not xPayload:
            raise(ratchet.exception.Bad_Passphrase('Could not encrypt our handshake'))
        return self.serialize(Payload=xPayload.data)
