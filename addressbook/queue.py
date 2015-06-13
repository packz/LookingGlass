
from django.db import models
from django.db.models import Q

import re
from uuid import uuid4
from types import StringType

import addressbook
import ratchet
import smp
import emailclient.utils
import thirtythirty.exception
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

SMP_Objects = smp.models.SMP.objects
SMP_Objects.init_for('smp')

class QRunner(models.Manager):
    def __queue_local(self, destination=None,
                      payload=None,
                      headers=None):
        """
        P2P connection to other LG2 users
        """
        if not headers:
            headers = []
        Headers = [
            ('X-Lookingglass-Overhead', 'True'),
            ]
        if len(headers) > 0:
            Headers.extend(headers)
        emailclient.utils.submit_to_smtpd(Payload=payload,
                                          Destination=destination,
                                          Headers=Headers,
                                          Subject='Cryptographic overhead')
        
    
    def Run(self, passphrase=None, do_not_repeat_these=None):
        if not do_not_repeat_these:
            do_not_repeat_these = []
        Engine = {
            Queue.AXOLOTL:'Axolotl',
            Queue.ADDRESS_RST:'Address_Reset',
            Queue.GPG_PK_PULL:'Keyserver_Pull',
            Queue.GPG_PK_PUSH:'Keyserver_Push',
            Queue.SERVER_INFO:'Server_Info',
            Queue.SOCIALISM:'Socialist_Millionaire',
            Queue.QCOMMIE:'Queued_SMP',
            }

        for Msg in Queue.objects.exclude(
            direction = Queue.SMP_Replay
            ):
            if Msg.id in do_not_repeat_these: continue
            do_not_repeat_these.append(Msg.id)
            if Msg.message_type == Queue.UNKNOWN:
                logger.warning('Got an unexpected message in the Queue... %s' % Msg)
                continue
            AsString = Engine[Msg.message_type]
            try:
                logger.debug('Entering %s for %s' % (AsString, Msg.address))
                getattr(self, AsString)(passphrase, Msg)
            except addressbook.address.Address.DoesNotExist:
                logger.debug('Address disappeared midstream - probably an Axo thang')
        if Queue.objects.filter(
            ~Q(pk__in = do_not_repeat_these)  # `~` inverts
            ).filter(
            ~Q(direction = Queue.SMP_Replay)
            ).count() > 0:
            self.Run(passphrase=passphrase, do_not_repeat_these=do_not_repeat_these)


    def Address_Reset(self, passphrase=None, Message=None):
        logger.debug('%s requested a state reset' % Message.address)
        Message.address.delete_local_state(passphrase)
        addressbook.queue.Queue.objects.create(
            address=Message.address,
            body=Message.body,
            direction=addressbook.queue.Queue.RX,
            message_type=addressbook.queue.Queue.AXOLOTL,
            )
        Message.delete()


    def Keyserver_Push(self, passphrase=None, Message=None):
        if Message and Message.direction == Queue.RX:
            logger.warning('Got a PK publish RX message unexpectedly')
            return False
        Me = addressbook.utils.my_address()
        logger.debug('Pushing')
        Resp = addressbook.gpg.push_to_keyserver()
        if Resp['failed']:
            emailclient.utils.submit_to_smtpd(Payload="""The upstream server seems to have experienced a temporary problem during registration.
The error is:
`%s`
We'll try registration again in a bit and see if it magically starts working.
""" % '\n'.join(Resp['status']),
                                              Destination=Me.email,
                                              Subject='Temporary problem - key registration',
                                              From='Sysop <root>')
            return False
        else:
            Message.delete()
            Me.comment = 'KS Accepted - %s' % ' '.join(Resp['status'])
            Me.save()
            return True

    def __get_axo_body(self, old_uuid=None):
        Axo = Queue.objects.filter(address=old_uuid,
                                   message_type=Queue.AXOLOTL,
                                   direction=Queue.RX).first()
        if Axo: return Axo.body
        

    def Keyserver_Pull(self, passphrase=None, Message=None):
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        RL = addressbook.utils.time_lock()
        if RL.is_locked('UPSTREAM'):
            logger.warning('We are querying the keyserver too hard - backing off')
            return False
                
        Me = addressbook.utils.my_address()
        
        Resp = None
        try:
            if re.search('^[0-9A-Fa-f]{5,40}$', Message.body):
                Resp = addressbook.gpg.pull_from_keyserver(fingerprint=Message.body)
            else:
                Resp = addressbook.gpg.pull_from_keyserver(covername=Message.body)
                
        except addressbook.exception.MultipleMatches as Matches:
            logger.debug(Matches)
            Message.address.user_state = addressbook.address.Address.FAIL
            Message.address.save()
            emailclient.utils.submit_to_smtpd(Payload="""The upstream server returned many keys for "%s".
This is exciting new territory in errors!  Please fill out a bug report!  Thank you!
""" % Message.address.covername,
            Destination=Me.email,
            Subject='FATAL problem - many users go by "%s"' % Message.address.covername,
            From='Sysop <root>')
            Message.delete()
            
        except addressbook.exception.NoKeyMatch:
            logger.debug('No matches')
            Message.address.user_state = addressbook.address.Address.FAIL
            Message.address.save()
            emailclient.utils.submit_to_smtpd(Payload="""No upstream server knows "%s".
This may be a typo in the covername - please bother a developer to write the synonym code in a bug report!  Thank you!
""" % Message.address.covername,
            Destination=Me.email,
            Subject='FATAL problem - no one by the name of "%s"' % Message.address.covername,
            From='Sysop <root>')
            Message.delete()
            
        except addressbook.exception.KeyserverTimeout:
            logger.debug('Keyservers all timed out - TEMPFAIL')
            emailclient.utils.submit_to_smtpd(Payload="""The upstream server seems to have experienced a temporary problem during key lookup for "%s".
We'll try again in a bit and see if it magically starts working.
""" % Message.address.covername,
            Destination=Me.email,
            Subject='Temporary problem - key lookup for "%s"' % Message.address.covername,
            From='Sysop <root>')
            

    def Axolotl(self, passphrase=None, Message=None):
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        if Message.address.is_me:
            logger.warning('Got a request to handshake myself?  Piss off.')
            Message.delete()
            return False

        if Message.address.system_use:
            logger.warning('Got a request to handshake a system user.  No.')
            Message.delete()
            return False
        
        if Message.direction == Queue.TX:
            logger.debug('Got request to send Axo SYN: %s' % Message.address.fingerprint)
            try:
                Convo = ratchet.conversation.Conversation.\
                        objects.get(UniqueKey=Message.address.fingerprint)
            except ratchet.conversation.Conversation.DoesNotExist:
                Convo = ratchet.conversation.Conversation.\
                        objects.initiate_handshake_for(
                    unique_key=Message.address.fingerprint,
                    passphrase=passphrase)
                logger.debug('Created conversation with %s' % Message.address.email)
            Domain = Message.address.email.split('@')[-1]
            if re.search('(?i)\.onion$', Domain):
                # legit
                Loop_Header = []
                if re.search('multiple init', Message.body):
                    logger.warning('multiple init attempts - add header to warn other side of possible loop')
                    Loop_Header.append(('X-Lookingglass-Axo-Loop', 'True'))
                elif re.search('conversation reset', Message.body):
                    logger.debug('signalling this is a reset request for %s' % Message.address)
                    Loop_Header.append(('X-Lookingglass-Address-Reset', 'True'))
                try:
                    HS = Convo.my_handshake(Passphrase=passphrase)
                    self.__queue_local(
                        destination=Message.address.email,
                        payload=HS,
                        headers=Loop_Header,
                        )
                    logger.debug('Axo SYN SMTP queued to: %s' % Message.address.email)
                except ratchet.exception.Missing_Handshake:
                    logger.warning('Other side has signalled for a restart')
                    Message.address.user_state = addressbook.address.Address.KNOWN
                    Message.address.save()
                    ratchet.conversation.Conversation.objects.filter(
                        UniqueKey=Message.address.fingerprint
                        ).delete()
                    smp.models.SMP.objects.filter(
                        UniqueKey=Message.address.fingerprint
                        ).delete()
                    Message.direction = Queue.RX  # whip that shit right round
                    Message.save()
                    return                     # FIXME: debug this reset code
            else:
                logger.warning("This doesn't look like a hidden service domain.  I don't talk to those people.  Time for the advanced menu.")
            Message.delete()
        elif Message.direction == Queue.RX:
            try:
                HS = ratchet.handshake.EncryptedHandshake(Import=Message.body,
                                                          Passphrase=passphrase)
                if HS.FPrint == None:
                    logger.error('Axo handshake from %s came without a fingerprint.' % Message.address)
                    Message.delete()
                    return
            except ratchet.exception.Bad_Passphrase:
                logger.critical("Can't see into this handshake!")
                Message.message_type = Queue.ADDRESS_RST
                Message.save()
                return
            try:
                Who = ratchet.conversation.Conversation.\
                      objects.get(UniqueKey=HS.FPrint)
                logger.debug('Got Axo ACK from %s' % HS.FPrint)
            except ratchet.conversation.Conversation.DoesNotExist:
                try:
                    Who = ratchet.conversation.Conversation.\
                          objects.initiate_handshake_for(
                        unique_key=HS.FPrint,
                        passphrase=passphrase)
                except ratchet.conversation.exception.No_Address:
                    logger.error('We have not finished looking up the key for %s - bailing out of handshake for now.' % HS.FPrint)
                    return
                # turn around and send our shake out
                Queue.objects.create(address=Message.address,
                                     direction=Queue.TX,
                                     message_type=Queue.AXOLOTL,
                                     )
                logger.debug('Got Axo SYN from %s, sending our shake' % HS.FPrint)
            if Who.their_fingerprint() is not None:
                logger.warning('Multiple conversation init attempts from %s' % addressbook.address.Address.objects.get(fingerprint=HS.FPrint))
                if re.search('Axolotl-Loop', Message.body):
                    logger.debug('Loop protection enabled.  Stopping now.')
                else:
                    logger.debug("We're probably getting a shake request...")
                    Queue.objects.create(address=Message.address,
                                         direction=Queue.TX,
                                         body='multiple init attempts',
                                         message_type=Queue.AXOLOTL,
                                         )
            else:
                try:
                    Who.greetings(HS)
                except AttributeError:
                    logger.error('ratchet synch state is waaaay out of whack - start over')
                    Message.address.remote_restart(passphrase)
                    Message.delete()
                    return
                Who.save()
                Message.address.user_state = addressbook.address.Address.NOT_VETTED
                Message.address.save()
                if Who.IAmAlice:
                    logger.debug('greetings() with %s established, I am Alice' % Message.address.email)
                else:
                    logger.debug('greetings() with %s established, I am Bob' % Message.address.email)
            Message.delete()
        else:
            logger.error('ZOMGBBQ - what manner of Axolotl handshake is this?')


    def Socialist_Millionaire(self, passphrase=None, Message=None):
        """
        We provide for limited recovery in case the msg is lost in transit (Queue.SMP_Replay) - but
        we can't cover for when the other side's ratchet advances and THEN blows up.
        For that, we have to start over.
        """
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        try: SMP_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        if Message.direction == Queue.TX:
            Domain = Message.address.email.split('@')[-1]
            if re.search('(?i)\.onion$', Domain):
                # legit
                self.__queue_local(
                    destination=Message.address.email,
                    payload=Message.body)
                logger.debug('SMP SMTP queued to: %s' % Message.address.email)
            else:
                # FIXME: SMP step button on dossier advanced
                logger.warning("This doesn't look like a hidden service domain.  I don't talk to those people.  Time for the advanced menu.")
            logger.debug('Freezing output so we can replay it later')
            Message.direction = Queue.SMP_Replay
            Message.save()
        elif Message.direction == Queue.RX:
            if Message.address.user_state > addressbook.address.Address.VETTING:
                logger.warning('I already know: %s' % Message.address.email)
                Message.delete()
                return
            try:
                Convo = ratchet.conversation.Conversation.objects.get(
                    UniqueKey = Message.address.fingerprint
                    )
            except ratchet.conversation.Conversation.DoesNotExist:
                logger.warning("Conversation for %s doesn't exist - could indicate delayed Axolotl greetings()" % Message.address)
                # DON'T DELETE THE MESSAGE HERE                
                return
            try:
                MySMP = smp.models.SMP.objects.get(UniqueKey = Message.address.fingerprint)
            except smp.models.SMP.DoesNotExist:
                # FIXME: check the addressbook user state
                logger.debug("We're behind the curve!  Creating SMP for %s" % Message.address)
                MySMP = smp.models.SMP.objects.hash_secret(Conversation=Convo,
                                                           passphrase=passphrase)
            try:
                Got = Convo.decrypt(Message.body)
            except:
                logger.warning("Let's let the other side know something went sideways...")
                try:
                    self.__queue_local(
                        destination=Message.address.email,
                        payload=Convo.encrypt('Axolotl decrypt error'))
                except ratchet.exception.Broken_State:
                    logger.critical('This is one effed up conversation.')
                    Message.address.remote_restart(passphrase)
                    Message.delete()
                    return
                MySMP.remove(fail=True)
                logger.debug('Returned %s to %s' % (Message.address.email,
                                                    Message.address.get_user_state_display()))
                Message.delete()
                return
            logger.debug('SMP step successfully decrypted!  IT IS A MIRACLE.')
            if 'Axolotl decrypt error' in Got:
                logger.critical('other side says there is a problem.  bail.')
                MySMP.remove(fail=True)
                logger.debug('Returned %s to %s' % (Message.address.email,
                                                    Message.address.get_user_state_display()))
                Message.delete()
                return
            if ((MySMP.Shared_Secret is None) or (not MySMP.IAmAlice and MySMP.step < 2)):
                logger.debug('Freezing state - looks like we may go into the wall...')
                Step = smp.models.SMPStep(Import=Got)
                MySMP.Question = Step.Question
                MySMP.save()
                Queue.objects.create(
                    address = Message.address,
                    body = str(addressbook.gpg.symmetric(passphrase=passphrase,
                                                         msg=Got)),
                    direction = Queue.RX,
                    message_type = Queue.QCOMMIE,
                    )
                Message.delete()
                logger.debug('State returns okay, now hodling.')
                return
            try:
                logger.debug('Attempting to advance SMP state...')
                Send = MySMP.advance_step(Got)
            except smp.exception.Socialist_Misstep as e:
                logger.error('I got the wrong step number: %s' % e)
                # FIXME: need more proof that this is or isn't necessary
                # MySMP.remove(fail=True)
                # return
            if type(Send) is StringType:
                # we could have matching secrets, be Alice, and still need to notify Bob all is well
                Queue.objects.create(
                    address = Message.address,
                    body = Convo.encrypt(plaintext=Send),
                    direction = Queue.TX,
                    message_type = Queue.SOCIALISM,
                    )
                logger.debug('SMTP queued step: %s/5' % MySMP.step)
            if ((Send is False) or ((MySMP.step == 5) and (MySMP.Secrets_Match is False))):
                logger.warning('Uhoh, sumwun done didus rong.')
                MySMP.remove(fail=True)
                logger.debug('Returned %s to %s' % (Message.address.email,
                                                    Message.address.get_user_state_display()))
            if MySMP.Secrets_Match is True:
                logger.debug('~~CHORUS OF ANGELS HERE~~')
                MySMP.remove(fail=False)
            Message.delete()
        else:
            logger.error('ZOMGBBQ - what manner of socialism is this?')


    def Queued_SMP(self, passphrase=None, Message=None):
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        try: SMP_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        try:
            MySMP = smp.models.SMP.objects.get(UniqueKey = Message.address.fingerprint)
        except smp.models.SMP.DoesNotExist:
            logger.error("I can't find the SMP object for %s, and cannot continue" % Message.address.email)
            Message.delete()
            return
        try:
            Convo = ratchet.conversation.Conversation.objects.get(
                UniqueKey = Message.address.fingerprint)
        except ratchet.conversation.Conversation.DoesNotExist:
            logger.error("I can't find the Axolotl conversation for %s, and cannot continue" % Message.address.email)
            Message.delete()
            return
        Got = str(addressbook.gpg.decrypt(msg=Message.body,
                                          passphrase=passphrase))
        try:
            Send = MySMP.advance_step(Got)
        except smp.exception.Unset_Secret:
            logger.warning("You'll need to set the secret for this instance, to continue.")
            return
        except smp.exception.Socialist_Misstep as e:
            logger.critical('Got some steps out of order: %s' % e)
            Message.delete()
            return
        Address = Message.address
        Message.delete()
        logger.debug("Got the convo, got the secret, got the correct step - let's do this thing")
        Send_as_Step = smp.models.SMPStep(Import=Send)
        Queue.objects.create(                    
            address = Address,
            body = Convo.encrypt(plaintext=Send),
            direction = Queue.TX,
            message_type = Queue.SOCIALISM,
            )
        logger.debug("Dequeued SMP for %s - step %s/5" % (Address, Send_as_Step.Step))


class Queue(models.Model):
    body = models.TextField(null=False)
    address = models.ForeignKey('Address')
    messageid = models.TextField(unique=True, default=lambda: str(uuid4()))
    
    creation = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    objects = QRunner()

    class Meta:
        get_latest_by = 'modified'

    RX = 'RX'
    SMP_Replay = 'RP'
    TX = 'TX'
    direction_choices = (
        (RX, 'I got some data'),
        (SMP_Replay, 'In case of data loss during msg send, we keep last SMP msg'),
        (TX, 'I am queuing outbound data'),
        )
    direction = models.CharField(max_length=2,
                                 choices=direction_choices,
                                 default=RX)

    UNKNOWN     = 'WTFBBQ'
    AXOLOTL     = 'AXOLUL'
    AXOANONHS   = 'AXOWHO'
    ADDRESS_RST = 'ADDRST'
    GPG_PK_PULL = 'GPGPLL'
    GPG_PK_PUSH = 'GPGPSH'
    SERVER_INFO = 'SERVUP'
    SOCIALISM   = 'SMPSTP'
    QCOMMIE     = 'QCOMMY'
    message_type_choices = (
        (UNKNOWN, 'I do not know what is going on'),
        (AXOLOTL, 'Axolotl handshake'),
        (AXOANONHS, 'Axolotl anonymous handshake'),
        (GPG_PK_PULL, 'Requesting GPG public key from the cloud'),
        (GPG_PK_PUSH, 'I am sending my GPG public key data into the cloud'),
        (ADDRESS_RST, 'Address reset request'),
        (SERVER_INFO, 'Server health report request'),
        (SOCIALISM, 'Socialist millionaire protocol'),
        (QCOMMIE, 'Temporarily queued socialist millionaire protocol'),
        )
    message_type = models.CharField(max_length=6,
                                    choices=message_type_choices,
                                    default=UNKNOWN)

    def __unicode__(self):
        return u'%s: %s - [%s:%s]' % (self.id, self.address.email,
                                      self.get_direction_display(),
                                      self.get_message_type_display())
