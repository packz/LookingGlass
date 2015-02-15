
from django.db import models
from django.utils import timezone

from curve25519 import keys as ECkey
from datetime import datetime, timedelta
from hashlib import sha224, sha256
from passlib.utils.pbkdf2 import pbkdf2
from struct import unpack_from
from types import BufferType, StringType

import thirtythirty.db_locker
import ratchet

import logging
logger = logging.getLogger(__name__)


class Skipped_Key(models.Model):
    """
    Used when messages get out of order.
    We freeze the ratchet state and start a countdown.
    """
    Convo = models.ForeignKey('Conversation')
    HeaderKeyRx = models.BinaryField()
    MessageKey = models.BinaryField(unique=True)
    Creation = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'%s|%s' % (self.Convo.UniqueKey,
                           self.Creation)



class ConversationMgr(thirtythirty.db_locker.LockManager,
                      models.Manager,):
    """
    We use this pattern
    https://docs.djangoproject.com/en/1.6/ref/models/instances/
    in order to init the Conversation properly
    as well as spin up the LockManager @ the right time
    """
    def __init__(self, *args, **kwargs):
        thirtythirty.db_locker.LockManager.__init__(self)
        models.Manager.__init__(self, *args, **kwargs)
    
    def initiate_handshake_for(self, unique_key=None, passphrase=None):
        """
        Others there are whose hands have sunbeams in them...
        """
        self.init_for('ratchet')
        Convo = self.create(UniqueKey=unique_key)
        Convo.begin_at_the_beginening()
        Convo.save()
        return Convo

    def with_pending_handshakes(self):
        ret = []
        for X in Conversation.objects.all():
            if hasattr(X, 'Handshake'): ret.append(X)
        return ret

    

class Conversation(models.Model):
    """
    Protocol: Axolotl
    https://github.com/trevp/axolotl/wiki/newversion
    
    Adapted for Django from Pyaxo source
    https://github.com/rxcomm/pyaxo

    Gives a nice breakdown
    https://whispersystems.org/blog/advanced-ratcheting/

    Conversation() acts as the key management portion

    AnonymousHandshake() has no source information, recipient must attach it to proper Address()
    EncryptedHandshake() adds a source fingerprint to the handshake
    """
    UniqueKey = models.CharField(primary_key=True, max_length=60)
    RootKey = models.BinaryField(null=True)
    NumberTx = models.IntegerField(default=0)
    NumberRx = models.IntegerField(default=0)
    BobsFirst = models.BooleanField(default=True)
    IAmAlice = models.BooleanField(default=True)

    objects = ConversationMgr()

    def __unicode__(self):
        ret = u'[%s]' % (
        ratchet.utils.human_readable(self.UniqueKey)
            )
        if self.UniqueKey[0] == '.':
            ret = u'[%s]' % (self.UniqueKey)
        if self.DHIdentity.rx:
            if self.IAmAlice:
                ret += ' [ALICE]'
            else:
                ret += ' [BOB]'
        ret += ' [%02d/%02d]' % (self.NumberTx, self.NumberRx)
        if not hasattr(self, 'Handshake'):
            ret += ' # FINGERPRINT VERIFIED'
        ret += '\n'
        for KName in [
            'ChainKey',
            'DHIdentity',
            'DHRatchet',
            'Handshake',
            'HeaderKey',
            'NextHeader',
            'RootKey',
            ]:
            if not hasattr(self, KName): continue
            K = getattr(self, KName)
            for Dir in [
                'prv',
                'rx',
                'tx',
                ]:
                if not hasattr(K, Dir): continue
                if not getattr(K, Dir): continue
                ret += u'%s.%s: %s\n' % (
                    KName,
                    Dir,
                    ratchet.utils.human_readable(
                        getattr(K, Dir)),
                    )
        return ret


    def __pyaxo_fp(self, fp=None):
        fprint = ''
        for i in range(0, len(fp), 4):
            fprint += fp[i:i+2] + ':'
        return fprint[:-1]
        

    def my_fingerprint(self, pyaxo=True):
        """
        for OOB comparison
        """
        if not self.DHIdentity.tx: return None
        rawFP = sha224(
            self.DHIdentity.tx
            ).hexdigest().upper()
        if not pyaxo: return ratchet.utils.human_readable(rawFP)
        else: return self.__pyaxo_fp(rawFP)


    def their_fingerprint(self, pyaxo=True):
        """
        for OOB comparison
        """
        if not self.DHIdentity.rx: return None
        rawFP = sha224(
            self.DHIdentity.rx
            ).hexdigest().upper()
        if not pyaxo: return ratchet.utils.human_readable(rawFP)
        else: return self.__pyaxo_fp(rawFP)


    def __purge_skipped_keys(self):
        WeekAgo = timezone.now() - timedelta(days=7)
        Skipped_Key.objects.filter(Creation__lt=WeekAgo).delete()
                

    def save(self, *args, **kwargs):
        for Z in ['HeaderKey',
                  'NextHeader',
                  'ChainKey',
                  'DHIdentity',
                  'DHRatchet']:
            if hasattr(self, Z):
                getattr(self, Z).save()
        if hasattr(self, 'staging'):
            for SK in self.staging:
                SK.save()
        self.__purge_skipped_keys()
        super(Conversation, self).save(*args, **kwargs)


    def my_handshake(self, Passphrase=None):
        if not hasattr(self, 'Handshake'):
            raise(ratchet.exception.Missing_Handshake('Pretty sure I shook already'))
        if Passphrase:
            logger.debug('Encrypted handshake')
            ret = ratchet.handshake.EncryptedHandshake(
                DHIdentityTx = self.DHIdentity.tx,
                HandshakeTx = self.Handshake.tx,
                DHRatchetTx = self.DHRatchet.tx,
                )
            return ret.dumps(to_fp=self.UniqueKey,
                             Passphrase=Passphrase)
        else:
            logger.debug('Anonymous handshake')
            ret = ratchet.handshake.AnonymousHandshake(
                DHIdentityTx = self.DHIdentity.tx,
                HandshakeTx = self.Handshake.tx,
                DHRatchetTx = self.DHRatchet.tx,
                )
            return ret.dumps()
    

    def begin_at_the_beginening(self):
        """
        run by the mgr instance
        """
        # create header, nextheader, chain, DH's
        ratchet.keypair.HeaderKey(Convo=self).save()
        ratchet.keypair.NextHeader(Convo=self).save()
        ratchet.keypair.ChainKey(Convo=self).save()
        ratchet.keypair.DHIdentity(Convo=self).save()
        ratchet.keypair.DHRatchet(Convo=self).save()

        # ephemeral - delete after we've verify_fingerprint(True)'d
        ratchet.keypair.Handshake(Convo=self).save()
        self.staging = []

        # init DHs and the handshake
        for Z in [self.DHIdentity,
                  self.DHRatchet,
                  self.Handshake,]:
            Z.genEC()
            Z.save()


    def __pbkdf(self,
                what=None,
                bit=None):
        return pbkdf2(what, bit,
                      10, prf='hmac-sha256')


    def __buffer_to_str(self, buffr=None):
        """
        curve25519 wants str() not buffer()
        sqlite3 binary fields return as buffer()
        this flimflams the hoosegow
        """
        return ''.join(unpack_from('c'*len(buffr), buffr))


    def __genDH(self,
              a=None,
              B=None):
        if type(a) is BufferType:
            a = self.__buffer_to_str(a)
        if type(B) is BufferType:
            B = self.__buffer_to_str(B)
        key = ECkey.Private(secret=a)
        return key.get_shared_key(
            ECkey.Public(B))


    def __tripleDH(self,
                 a=None, a0=None,
                 B=None, B0=None):
        if self.IAmAlice:
            return sha256(self.__genDH(a, B0) +
                          self.__genDH(a0, B) +
                          self.__genDH(a0, B0)).digest()
        else:
            return sha256(self.__genDH(a0, B) +
                          self.__genDH(a, B0) +
                          self.__genDH(a0, B0)).digest()


    def __alice_init(self, KDF=None, Ratchet=None):
        self.RootKey = self.__pbkdf(KDF, b'\x00')
        self.HeaderKey.tx = self.__pbkdf(KDF, b'\x01')
        self.HeaderKey.rx = self.__pbkdf(KDF, b'\x02')
        self.NextHeader.tx = self.__pbkdf(KDF, b'\x03')
        self.NextHeader.rx = self.__pbkdf(KDF, b'\x04')
        self.ChainKey.tx = self.__pbkdf(KDF, b'\x05')
        self.ChainKey.rx = self.__pbkdf(KDF, b'\x06')
        self.DHRatchet.prv = None
        self.DHRatchet.tx = None
        self.DHRatchet.rx = Ratchet
        self.BobsFirst = False


    def __bob_init(self, KDF=None):
        self.RootKey = self.__pbkdf(KDF, b'\x00')
        self.HeaderKey.rx = self.__pbkdf(KDF, b'\x01')
        self.HeaderKey.tx = self.__pbkdf(KDF, b'\x02')
        self.NextHeader.rx = self.__pbkdf(KDF, b'\x03')
        self.NextHeader.tx = self.__pbkdf(KDF, b'\x04')
        self.ChainKey.rx = self.__pbkdf(KDF, b'\x05')
        self.ChainKey.tx = self.__pbkdf(KDF, b'\x06')
        self.DHRatchet.rx = None
        self.BobsFirst = True


    def greetings(self, HS=None):
        """
        all options are the other ID's parts
        kinda like in Fargo
        """
        if self.__buffer_to_str(self.DHIdentity.tx) < HS.DHIdentityTx:
            self.IAmAlice = True
        else:
            self.IAmAlice = False
        self.DHIdentity.rx = HS.DHIdentityTx
        Key_Derivation = self.__tripleDH(self.DHIdentity.prv,
                                         self.Handshake.prv,
                                         HS.DHIdentityTx,
                                         HS.HandshakeTx)
        if self.IAmAlice:
            self.__alice_init(KDF=Key_Derivation,
                              Ratchet=HS.DHRatchetTx)
        else:
            self.__bob_init(KDF=Key_Derivation)
        self.save()


    def verify_fingerprint(self, verified=False):
        if not verified: return False
        self.Handshake.delete()
        self.save()
        return True


    def __stage_skipped(self, HeaderKeyRx=None,
                      NumberRx=None,
                      NumberPurported=None,
                      ChainKeyRx=None):
        """
        everything here is 'purported'
        """
        if not hasattr(self, 'staging'):
            self.staging = []
        pChainKey = ChainKeyRx
        logging.debug('save %s skipped keys, advance ratchet' % (NumberPurported - NumberRx))
        for i in range(NumberPurported - NumberRx):
            MessageKey = sha256(pChainKey + '0').digest()
            pChainKey = sha256(pChainKey + '1').digest()
            self.staging.append(
                Skipped_Key(Convo=self,
                            HeaderKeyRx=HeaderKeyRx,
                            MessageKey=MessageKey))
        MessageKey = sha256(pChainKey + '0').digest()
        pChainKey = sha256(pChainKey + '1').digest()
        return pChainKey, MessageKey


    def __check_skipped(self, ciphertext=None):
        for SK in Skipped_Key.objects.filter(Convo=self):
            logging.debug('checking skipped keys')
            Msg = ratchet.message.Message(HeaderKey=SK.HeaderKeyRx,
                                          MessageKey=SK.MessageKey,
                                          Ciphertext=ciphertext)
            if Msg.Payload:
                logging.debug('a skipped key that works!')
                SK.delete()
                return Msg
        return ratchet.message.Message(Ciphertext=ciphertext)


    def encrypt(self, plaintext=None,
                pyaxo_compat=False):
        if self.DHRatchet.tx == None:
            self.DHRatchet.genEC()
            self.NumberTx = 0
        MessageKey = sha256(
            self.ChainKey.tx + '0'
            ).digest()
        Msg = ratchet.message.Message(MessageKey = MessageKey,
                                      HeaderKey = self.HeaderKey.tx,
                                      NumberTx = self.NumberTx,
                                      DHRatchetTx = self.DHRatchet.tx,
                                      Payload = plaintext)
        self.NumberTx += 1
        self.ChainKey.tx = sha256(
            self.ChainKey.tx + '1'
            ).digest()
        self.save()
        return Msg.dumps(pyaxo_compat=pyaxo_compat)


    def decrypt(self, ciphertext=None):
        # Try our luck with skipped msgs
        Msg = self.__check_skipped(ciphertext)
        if Msg.Payload:
            return Msg.Payload

        # No, okay, with current header key, then?
        logging.debug('skipped keys all fail - how about the current one?')
        Msg.set_keys(HeaderKey=self.HeaderKey.rx)
        if Msg.DHRatchetTx:
            Msg.HeaderKey = None # freeze the header state
            ChainKey, MessageKey = self.__stage_skipped(
                HeaderKeyRx = self.HeaderKey.rx,
                NumberRx = self.NumberRx,
                NumberPurported = Msg.NumberTx,
                ChainKeyRx = self.ChainKey.rx,
                )
            Msg.set_keys(MessageKey=MessageKey)
            if not Msg.Payload:
                raise(ratchet.exception.Vanished_MessageKey(
                    'I have no message keys that match this message, but can see the header OK'))
            if self.BobsFirst:
                self.DHRatchet.rx = Msg.DHRatchetTx
                self.RootKey = sha256(
                    self.RootKey +\
                    self.__genDH(
                        self.DHRatchet.prv,
                        self.DHRatchet.rx)
                    ).digest()
                self.HeaderKey.tx = self.NextHeader.tx
                if self.IAmAlice:
                    self.NextHeader.tx = self.__pbkdf(
                        self.RootKey, b'\x03')
                    self.ChainKey.tx = self.__pbkdf(
                        self.RootKey, b'\x05')
                else:
                    self.NextHeader.tx = self.__pbkdf(
                        self.RootKey, b'\x04')
                    self.ChainKey.tx = self.__pbkdf(
                        self.RootKey, b'\x06')
                self.DHRatchet.prv = None
                self.DHRatchet.tx = None
                self.BobsFirst = False
                
        else:  # One.  Last.  Shot.
            Msg.set_keys(HeaderKey=self.NextHeader.rx)
            if not Msg.DHRatchetTx:
                raise(ratchet.exception.Undecipherable(
                    'I have no header keys that match this message'))
            Msg.HeaderKey = None # freeze the header state
            self.__stage_skipped(
                HeaderKeyRx = self.HeaderKey.rx,
                NumberRx = self.NumberRx,
                NumberPurported = Msg.NumberTx,
                ChainKeyRx = self.ChainKey.rx)
            RootKey = sha256(
                self.RootKey +\
                self.__genDH(
                    self.DHRatchet.prv,
                    self.DHRatchet.rx)).digest()
            HeaderKey = self.NextHeader.rx
            if self.IAmAlice:
                NextHeader = self.__pbkdf(RootKey, b'\x04')
                ChainKey = self.__pbkdf(RootKey, b'\x06')
            else:
                NextHeader = self.__pbkdf(RootKey, b'\x03')
                ChainKey = self.__pbkdf(RootKey, b'\x05')
            ChainKey, MessageKey = self.__stage_skipped(
                HeaderKeyRx = HeaderKey,
                NumberRx = 0,
                NumberPurported = Msg.NumberTx,
                ChainKeyRx = ChainKey)
            Msg.set_keys(MessageKey=MessageKey)
            if not Msg.Payload:
                raise(ratchet.exception.Vanished_MessageKey(
                    'I can derive the header keys, but cannot reach the payload'))
            self.RootKey = RootKey
            self.HeaderKey.rx = HeaderKey
            self.NextHeader.rx = NextHeader
            self.DHRatchet.rx = Msg.DHRatchetTx
            self.RootKey = sha256(
                self.RootKey +\
                self.__genDH(
                    self.DHRatchet.prv,
                    self.DHRatchet.rx)).digest()
            self.HeaderKey.tx = self.NextHeader.tx
            if self.IAmAlice:
                self.NextHeader.tx = self.__pbkdf(
                    self.RootKey, b'\x03')
                self.ChainKey.tx = self.__pbkdf(
                    self.RootKey, b'\x05')
            else:
                self.NextHeader.tx = self.__pbkdf(
                    self.RootKey, b'\x04')
                self.ChainKey.tx = self.__pbkdf(
                    self.RootKey, b'\x06')
            self.DHRatchet.prv = None
            self.DHRatchet.tx = None
        self.NumberRx = Msg.NumberTx + 1
        self.ChainKey.rx = ChainKey
        self.save()
        return Msg.Payload
