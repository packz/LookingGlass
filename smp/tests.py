
from django.test import TestCase
from django.db import IntegrityError

import uuid

import exception
import models
import ratchet.conversation
import ratchet.exception
import ratchet.handshake


class SocialistTest(TestCase):
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

        try:
            Alice_HS = ratchet.handshake.HandshakeFactory( Import=Alice.my_handshake() )
            Bob_HS   = ratchet.handshake.HandshakeFactory( Import=Bob.my_handshake() )
            Alice.greetings(Bob_HS)
            Bob.greetings(Alice_HS)
            Alice.verify_fingerprint(True)
            Bob.verify_fingerprint(True)
        except ratchet.exception.Missing_Handshake: pass

        return Alice, Bob


    def marx_lenin(self, AN=None, BN=None):
        TA, TB = self.cut_to_the_jibber_jabber(AN, BN)
        Secret = '1234'
        try:
            AS = models.SMP.objects.hash_secret(Conversation=TB, secret=Secret)
            BS = models.SMP.objects.hash_secret(Conversation=TA, secret=Secret)
        except IntegrityError:
            AS = models.SMP.objects.get(UniqueKey=TB)
            BS = models.SMP.objects.get(UniqueKey=TA)

        if not AS.IAmAlice:
            temp = AS
            AS = BS
            BS = temp
        return AS, BS


    def test_no_axo_no_peas(self):
        TA, TB = self.geterset()
        Secret = '1234'
        self.assertRaises(exception.Need_Axolotl_First, models.SMP.objects.hash_secret, secret=Secret)


    def test_secret_salting(self):
        AS, BS = self.marx_lenin()
        self.assertEqual(AS.Shared_Secret, BS.Shared_Secret)


    def test_bob_refuses_to_initiate(self):
        AS, BS = self.marx_lenin()
        self.assertRaises(exception.Socialist_Misstep, BS.advance_step)


    def test_doublestuffing_and_result_stability(self):
        AS, BS = self.marx_lenin()
        A1 = AS.advance_step()
        A2 = BS.advance_step(A1)
        self.assertRaises(exception.Socialist_Misstep, AS.advance_step)
        self.assertRaises(exception.Socialist_Misstep, BS.advance_step, A1)
        self.assertRaises(exception.Socialist_Misstep, AS.advance_step, A1)
        A3 = AS.advance_step(A2)
        A4 = BS.advance_step(A3)
        self.assertRaises(exception.Socialist_Misstep, AS.advance_step, A2)
        self.assertRaises(exception.Socialist_Misstep, AS.advance_step, A3)
        self.assertEqual(BS.advance_step(A3), True)
        self.assertEqual(BS.advance_step(A4), True)
        A5 = AS.advance_step(A4)
        self.assertEqual(AS.advance_step(A5), True)
        self.assertEqual(BS.advance_step(A5), True)


    def test_acid_burn_vs_crash_override(self):
        """
        if the secrets don't match, go to the pool on the roof
        """
        AS, BS = self.marx_lenin()
        AS.create_secret(secret='hack the planet!')
        A1 = AS.advance_step()
        A2 = BS.advance_step(A1)
        A3 = AS.advance_step(A2)
        A4 = BS.advance_step(A3)
        A5 = AS.advance_step(A4)
        self.assertEqual(AS.Secrets_Match, False)
        self.assertEqual(BS.Secrets_Match, False)


    def test_without_persistence(self):
        """
        keeps the objects in memory
        makes sure the algo works at all
        """
        AS, BS = self.marx_lenin()
        A1 = AS.advance_step()
        A2 = BS.advance_step(A1)
        A3 = AS.advance_step(A2)
        A4 = BS.advance_step(A3)
        A5 = AS.advance_step(A4)
        self.assertEqual(AS.Secrets_Match, True)
        self.assertEqual(BS.Secrets_Match, True)


    def test_with_persistence(self):
        """
        deletes state after each interchange
        makes sure we have the state captured properly in the DB
        """
        AS, BS = self.marx_lenin()
        AN     = AS.UniqueKey
        BN     = BS.UniqueKey
        
        A1 = AS.advance_step()
        A2 = BS.advance_step(A1)

        # erase state
        AS, BS = None, None

        # load state
        AS = models.SMP.objects.get(pk=AN)
        BS = models.SMP.objects.get(pk=BN)

        A3 = AS.advance_step(A2)
        A4 = BS.advance_step(A3)

        # zipzap
        AS, BS = None, None

        # load state
        AS = models.SMP.objects.get(pk=AN)
        BS = models.SMP.objects.get(pk=BN)

        A5 = AS.advance_step(A4)
        
        self.assertEqual(AS.Secrets_Match, True)
        self.assertEqual(BS.Secrets_Match, True)
