
from django.test import TestCase
from django.db import IntegrityError

import uuid

import ratchet

class RatchetTest(TestCase):
    def geterset(self, k1name='.ALICE', k2name='.BOB'):
        try:
            Alice = ratchet.conversation.Conversation.objects.initiate_handshake_for(unique_key=k2name, passphrase='1234')
            Bob   = ratchet.conversation.Conversation.objects.initiate_handshake_for(unique_key=k1name, passphrase='1234')
        except IntegrityError:
            Alice = ratchet.conversation.Conversation.objects.get(UniqueKey=k2name)
            Bob = ratchet.conversation.Conversation.objects.get(UniqueKey=k1name)
        self.assertNotEqual(Alice, None)
        self.assertNotEqual(Bob, None)
        return Alice, Bob


    def cut_to_the_jibber_jabber(self, AliceName=None, BobName=None):
        if not AliceName: AliceName = str(uuid.uuid4())
        if not BobName: BobName = str(uuid.uuid4())
        Alice, Bob = self.geterset(AliceName, BobName)

        Alice_HS = ratchet.handshake.HandshakeFactory( Import=Alice.my_handshake() )
        Bob_HS   = ratchet.handshake.HandshakeFactory( Import=Bob.my_handshake() )

        Alice.greetings(Bob_HS)
        Bob.greetings(Alice_HS)

        Alice.verify_fingerprint(True)
        Bob.verify_fingerprint(True)
        return Alice, Bob


    def test_fingerprint_transmits(self):
        Alice, Bob = self.geterset()
        Alice_HS = ratchet.handshake.HandshakeFactory( Import=Alice.my_handshake() )
        Bob_HS   = ratchet.handshake.HandshakeFactory( Import=Bob.my_handshake() )

        Alice.greetings(Bob_HS)
        Bob.greetings(Alice_HS)

        self.assertEqual(Alice.my_fingerprint(), Bob.their_fingerprint())
        self.assertEqual(Bob.my_fingerprint(), Alice.their_fingerprint())


    def test_overshake(self):
        self.cut_to_the_jibber_jabber('aloose', 'borb')
        self.assertRaises(ratchet.exception.Missing_Handshake, self.cut_to_the_jibber_jabber, 'aloose', 'borb')
        
    
    def test_handshake_deletes(self):
        AliceName = str(uuid.uuid4())
        BobName = str(uuid.uuid4())
        Alice, Bob = self.geterset(AliceName, BobName)

        self.assertEqual(hasattr(Alice, 'Handshake'), True)
        self.assertEqual(hasattr(Bob, 'Handshake'), True)

        Alice_HS = ratchet.handshake.HandshakeFactory( Import=Alice.my_handshake() )
        Bob_HS   = ratchet.handshake.HandshakeFactory( Import=Bob.my_handshake() )

        Alice.greetings(Bob_HS)
        Bob.greetings(Alice_HS)

        Alice.verify_fingerprint(True)
        Bob.verify_fingerprint(True)

        # we need to reload, as the Handshakes are cached now
        Alice = None
        Bob = None
        Alice, Bob = self.geterset(AliceName, BobName)

        self.assertEqual(hasattr(Alice, 'Handshake'), False)
        self.assertEqual(hasattr(Bob, 'Handshake'), False)


    def test_initial_encrypt(self):
        Alice, Bob = self.cut_to_the_jibber_jabber()

        A2B = 'Watson, come here, I need you'
        B2A = 'Gospel of Luke 2:14'
        
        M1a = Alice.encrypt(plaintext=A2B)
        M1b = Bob.encrypt(plaintext=B2A)

        self.assertEqual(Bob.decrypt(M1a), A2B)
        self.assertEqual(Alice.decrypt(M1b), B2A)


    def test_bad_msg(self):
        Alice, Bob = self.cut_to_the_jibber_jabber()

        A2B = 'Watson, come here, I need you'
        B2A = 'Gospel of Luke 2:14'

        self.assertRaises(ratchet.exception.Undecipherable, Alice.decrypt, B2A)


    def test_msg_number_increase(self):
        Alice, Bob = self.cut_to_the_jibber_jabber()

        A2B = 'Watson, come here, I need you'
        B2A = 'Gospel of Luke 2:14'
        
        M1a = Alice.encrypt(plaintext=A2B)
        M1b = Bob.encrypt(plaintext=B2A)

        Alice.decrypt(M1b)
        Bob.decrypt(M1a)        
        
        self.assertEqual(Alice.NumberRx, 1)
        self.assertEqual(Bob.NumberRx, 1)


    def test_ratchet_advance(self):
        Alice, Bob = self.cut_to_the_jibber_jabber()

        A2B = 'Watson, come here, I need you'
        B2A = 'Gospel of Luke 2:14'
        
        M1a = Alice.encrypt(plaintext=A2B)
        M1b = Bob.encrypt(plaintext=B2A)

        self.assertEqual(Bob.decrypt(M1a), A2B)
        self.assertEqual(Alice.decrypt(M1b), B2A)

        M2a = Alice.encrypt(plaintext=A2B)
        M2b = Bob.encrypt(plaintext=B2A)

        self.assertNotEqual(M1a, M2a)
        self.assertNotEqual(M1b, M2b)

        self.assertRaises(ratchet.exception.Vanished_MessageKey, Alice.decrypt, M1b)
        self.assertRaises(ratchet.exception.Vanished_MessageKey, Bob.decrypt, M1a)


    def test_skipped_key(self):
        Alice, Bob = self.cut_to_the_jibber_jabber()

        A2B  = 'Watson, come here, I need you'
        A2B2 = 'Richard Branson'
        B2A  = 'Gospel of Luke 2:14'
        B2A2 = 'Clive Barker'
        
        M1a = Alice.encrypt(plaintext=A2B)
        M1b = Alice.encrypt(plaintext=A2B2)
        M2a = Bob.encrypt(plaintext=B2A)
        M2b = Bob.encrypt(plaintext=B2A2)

        self.assertEqual(Bob.decrypt(M1b), A2B2)

        self.assertEqual(ratchet.conversation.Skipped_Key.objects.filter(Convo=Alice).count(), 0)
        self.assertEqual(ratchet.conversation.Skipped_Key.objects.filter(Convo=Bob).count(), 1)

        self.assertEqual(Bob.decrypt(M1a), A2B)
        self.assertEqual(ratchet.conversation.Skipped_Key.objects.filter(Convo=Bob).count(), 0)
