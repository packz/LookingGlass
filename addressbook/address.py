
from django.db import models

import datetime
import re
from uuid import uuid4

import addressbook
import ratchet
import smp.models
import thirtythirty

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

SMP_Objects = smp.models.SMP.objects
SMP_Objects.init_for('smp')


class AddressMgr(models.Manager):
    def __parse_uid(self, uid=None):
        """
        if the use case is >more< users on LG, then this should be more strict
        right now, allows backwards compat with GPG users that aren't on the bandwagon
        """
        UE = re.search(
            '^(?P<Name>[^(]+) (\((?P<Comment>[^\)]+)\) )?<(?P<Email>[^@]+@[^\)]+)>$',
            uid)
        if not UE: return False
        ret = {}
        for K, V in UE.groupdict().items():
            if V: ret[K] = V.upper()
        Name = UE.group('Name').split(' ')
        if len(Name) == 2:
            # as it should be
            ret['First'] = Name[0]
            ret['Last'] = Name[-1]
        return ret


    def Restore(self, newSelf={}):
        if not newSelf.has_key('fingerprint'):
            logger.debug('no fingerprint')
            return None
        A = self.add_by_fingerprint(newSelf['fingerprint'])
        for X in ['covername', 'nickname']:
            if Entry[X]:
                setattr(A, X, Entry[X])
        A.save()
        return A


    def import_key(self, keydata=None):
        if not keydata: return None
        FP = addressbook.GPG.import_keys(keydata)
        self.rebuild_addressbook()
        if FP.count != 1:
            logger.warning('Imported multiple keys!')
        return FP.fingerprints


    def delete_key(self, fingerprint=None, passphrase=None):
        """
        coordinates deleting address state

        y u try to ruin my package manager?
        """
        if not passphrase:
            return False
        if not fingerprint:
            return False
        
        try: SMP_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass

        try:
            addressbook.queue.Queue.objects.filter(
                address=self,
                direction=addressbook.queue.Queue.SMP_Replay,
                ).delete()
            if fingerprint in TTS.UPSTREAM['trusted_prints']:
                logger.warning('Nice try - you cannot delete this user')
                A = addressbook.address.Address.objects.get(
                    fingerprint=fingerprint
                    )
                A.system_use = True
                A.user_state = addressbook.address.Address.KNOWN
                A.save()
            else:
                addressbook.GPG.delete_keys(fingerprint)
                addressbook.address.Address.objects.get(
                    fingerprint=fingerprint
                    ).delete()
            logger.warning('Flushing ratchet and SMP state')
            ratchet.conversation.Conversation.objects.filter(
                UniqueKey=fingerprint
                ).delete()
            smp.models.SMP.objects.filter(
                UniqueKey=fingerprint
                ).delete()
        except:
            return False
        
        return True


    def add_by_covername(self, covername=None):
        Email_Strip = re.sub('@.*', '', covername.upper())
        DeJunk = re.sub('[^ .A-Z]+', '', Email_Strip)
        Dot_Strip = re.sub('[\. ]+', ' ', DeJunk)
        Covername = Dot_Strip
        if len(Covername.split(' ')) != 2: return None
        try:
            A = Address.objects.get(covername=Covername)
            if A.covername == 'LAST BOX':
                A.system_use = False
                A.save()
        except Address.DoesNotExist:
            A = Address.objects.create(fingerprint=str(uuid4()),
                                       email=str(uuid4()),
                                       covername=Covername)
            A.save()
            H = addressbook.queue.Queue.objects.create(
                address=A,
                direction=addressbook.queue.Queue.TX,
                message_type=addressbook.queue.Queue.GPG_PK_PULL,
                body=Covername,
                messageid=str(uuid4()), # Don't remove this, even though `default` should handle it...  it wasn't.
                )
            logger.debug('Added request for %s' % Covername)
        return A


    def add_by_email(self, email=None):
        """
        # FIXME: write this
        """
        pass


    def add_by_fingerprint(self, fingerprint=None):
        fprint = re.sub('[^A-F0-9]+', '', fingerprint.upper())
        if not (8 <= len(fprint) <= 40):
            return False
        try:
            A = Address.objects.get(fingerprint=fprint)
        except Address.DoesNotExist:
            A = Address.objects.create(fingerprint=fprint,
                                       email=str(uuid4()))
            H = addressbook.queue.Queue.objects.create(
                address=A,
                messageid=str(uuid4()), # Don't remove this, even though `default` should handle it...  it wasn't.
                direction=addressbook.queue.Queue.TX,
                message_type=addressbook.queue.Queue.GPG_PK_PULL,
                body=fprint)
            logger.debug('Added request for %s' % fprint)
        return A


    def remove_removed(self):
        ret = []
        GPG_Keys = [ X['fingerprint'].upper() for X in addressbook.GPG.list_keys() ]
        for Key in Address.objects.filter(
            is_me=False,
            system_use=False,
            ):
            if Key.fingerprint.upper() not in GPG_Keys:
                ret.append(Key.covername)
                Key.delete()
        return ret
    
    
    def rebuild_addressbook(self, Private=False):
        ret = []
        for Key in addressbook.GPG.list_keys(Private):
            A, created = Address.objects.get_or_create(
                fingerprint = Key['fingerprint'].upper()
                )
            if not created:
                logger.debug('I already know %s' % A.email)
                continue
            ret.append(A)
            if Private:
                A.is_me = True
                A.user_state = Address.AUTHED
            else:
                A.user_state = Address.KNOWN
            if Key['expires'] != '':
                A.expires = datetime.date.fromtimestamp(
                    int(Key['expires'])
                    )
            Parsed = self.__parse_uid(Key['uids'][0])
            if Parsed:
                if Parsed.has_key('Name'):
                    A.covername = Parsed['Name']
                if Parsed.has_key('Comment'):
                    A.comment = Parsed['Comment']
                if Parsed.has_key('Email'):
                    A.email = Parsed['Email']
            if Key['fingerprint'].upper() in TTS.UPSTREAM['trusted_prints']:
                logger.debug('%s recognised as system_use' % A.email)
                A.system_use = True
            A.save()
            logger.debug("Hello, %s - let's get to know each other." % A.email)
        return ret


    def message_detective(self, Msg=None):
        """
        from an email message, locate the Address likely being referred to
        """
        FP = addressbook.GPG.verify(Msg.as_string())
        A = Address.objects.filter(fingerprint=FP.pubkey_fingerprint) 
        if A.count() == 1:
            return A[0]
        Domain = re.search('(?:@)([^>]+)', Msg['From'])
        if not Domain: return False
        Domain = Domain.group(1)
        A = Address.objects.filter(email__iendswith=Domain)
        if A.count() == 1:
            return A[0]
        return False
        

class Address(models.Model):
    """
    We use this to hold state that we can't keep in the GPG database.
    gnupg gives us a less than optimal index into the GPG data, so
    we cache the pertinent fields (via rebuild_addressbook())
    violating the SPOT rule like a boss
    """
    nickname = models.CharField(max_length=50, null=True)
    fingerprint = models.CharField(
        primary_key=True,
        max_length=40,
        default=str(uuid4())) # borken?

    covername    = models.CharField(max_length=85, unique=True)
    comment      = models.CharField(max_length=100, null=True)
    email        = models.CharField(max_length=100, unique=True)
    expires      = models.DateField(null=True)
    is_me        = models.BooleanField(default=False)
    system_use   = models.BooleanField(default=False)
    smp_failures = models.IntegerField(default=0)

    objects = AddressMgr()

    FAIL       = 0
    UNKNOWN    = 20
    KNOWN      = 40
    NOT_VETTED = 60
    VETTING    = 80
    AUTHED     = 100
    user_state_choices = (
        (FAIL,       'Badness and pain'),
        (UNKNOWN,    'Looking up email address'),
        (KNOWN,      'Negotiating forward secrecy'),
        (NOT_VETTED, 'Shared secret limbo'),
        (VETTING,    'Shared secret comparison in progress'),
        (AUTHED,     'Authenticated'),
        )
    user_state = models.IntegerField(choices=user_state_choices,
                                     default=UNKNOWN)

    Verbose = {
        FAIL:    """
        <p>Something terminal has happened.</p>
        <p>Possibilities:</p>
        <ol>
          <li>I have been unable to look up the user (wrong covername, unlisted covername).</li>
          <li>The user's key has expired.</li>
        </ol>
        <p>If you have manually added this user (via advanced-menu chicanery) ignore this warning and proceed to authenticatin'.</p>
        """,
        UNKNOWN: """
        <p>The keyserver is being contacted to locate this contact's <a href='https://en.wikipedia.org/wiki/Public-key_cryptography'>encryption key</a> and <a href='https://en.wikipedia.org/wiki/Tor_%28anonymity_network%29#Hidden_services'>address</a>.</p>
        <p>Email is unpossible until we get those.  Please be patient.</p>
        <p>If this condition lasts for more than an hour, please file a <a href='BUG_REPORT_URL'>bug report</a> or join the <a href='CHAT_URL'><span class='glyphicon glyphicon-comment'></span> Chat</a> and harass a developer.</p>
        """,
        KNOWN:   """
        <p>We are waiting for the contact to acknowledge our handshake, so that we can begin <a href='https://en.wikipedia.org/wiki/Forward_secrecy'>forward secret</a> email.</p>
        <p>Encrypted email may be sent, but will be insecure against future <a href='https://otr.cypherpunks.ca/otr-codecon.pdf'>key compromise</a>.</p>
        """,
        NOT_VETTED: """
        <p>We need to compare our <a href='https://en.wikipedia.org/wiki/Shared_secret'>shared secret</a>.  You'll need to think of something only you and your contact would know.  If you fail multiple challenges, be very careful with your communications as there may be a <a href='https://en.wikipedia.org/wiki/Man-in-the-middle_attack'>man in the middle</a>.</p>
        <p>Questions should be specific and not 'researchable' by counterintelligence.</p>
        <p>Examples:</p>
        <dl class='dl-horizontal'>
        <dt>Poor:</dt>
        <dd>Maiden names, hair color, pet names.</dd>

        <dt>Middling:</dt>
        <dd>What poster is on the wall of my shop?  What class did we first meet in?</dd>

        <dt>Not so shabby:</dt>
        <dd>What did we talk about at dinner the other night?  What's the punchline to that joke I keep telling you?</dd>
        </dl>
        """,
        VETTING:  """
        <p>We are <a href='http://twistedoakstudios.com/blog/Post3724_explain-it-like-im-five-the-socialist-millionaire-problem-and-secure-multi-party-computation'>comparing</a> our <a href='http://blog.cryptographyengineering.com/2014/11/zero-knowledge-proofs-illustrated-primer.html'>shared secret</a> to exclude the possibility that anyone is <a href='https://en.wikipedia.org/wiki/Man-in-the-middle_attack'>intercepting our messages</a>.</p>
        <p>This process may take a bit to complete if you and your contact are not online at the same time.</p>
        <p>We are at step SMP_STEP out of 5.</p>
        <p>In the meantime, email is encrypted, and keys are discarded after every message.</p>
        <p>If the authentication process <span class='text-danger'>fails</span> after this step, verify that you are using the same format for the secret (all lowercase, numbers only, letters only, no punctuation, etc).</p>
        <p>If the authentication process <span class='text-danger'>fails repeatedly</span> after this step, you should move to a more paranoid security posture.</p>
        """,
        AUTHED:  """
        <p>Your shared secrets match.</p>
        <p>This is currently the highest level of authentication and security.</p>
        <p>Excellent work.</p>
        <p>Git to insurrectin'.</p>
        """,
        }


    def __unicode__(self):
        ret = u'%s [%s]' % (self.covername, self.fingerprint)
        if self.is_me: ret += u' (this is you)'
        return ret


    def delete_local_state(self, passphrase=None):
        if not passphrase: return False
        try: Ratchet_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass
        try: SMP_Objects.decrypt_database(passphrase)
        except thirtythirty.exception.Target_Exists: pass
        try:
            ratchet.conversation.Conversation.objects.get(
                UniqueKey = self.fingerprint
                ).delete()
        except ratchet.conversation.Conversation.DoesNotExist:
            pass
        try:
            smp.models.SMP.objects.get(
                UniqueKey = self.fingerprint
                ).delete()
        except smp.models.SMP.DoesNotExist:
            pass
        addressbook.queue.Queue.objects.filter(
            address=self,
            message_type=addressbook.queue.Queue.QCOMMIE,
            ).delete()
        self.user_state = self.KNOWN
        self.save()
        return True


    def remote_restart(self, passphrase=None):
        if not passphrase: return False
        if not self.delete_local_state(passphrase): return False
        addressbook.queue.Queue.objects.create(
            address=self,
            body='conversation reset',
            direction=addressbook.queue.Queue.TX,
            message_type=addressbook.queue.Queue.AXOLOTL,
            )


    def Backup(self):
        return {'covername':self.covername,
                'email':self.email,
                'fingerprint':self.fingerprint,
                'nickname':self.nickname,
                'is_me':self.is_me,
                'type':'Address',
                # FIXME: need to unlock the DB to reach this
#                'conversation':self.Conversation().Export(),
                }

    def magic(self, name='magic'):
        FL = self.covername.upper().split(' ')
        if len(FL) != 2: return self.covername
        if name == 'first': return FL[0]
        elif name == 'last': return FL[-1]
        elif name == 'magic':
            if self.nickname:
                return self.nickname.upper()
            else:
                return FL[-1]
        else: return '%s %s' % (FL[0], FL[-1])


    def public_key(self):
        return addressbook.GPG.export_keys(self.fingerprint)
    

    def asymmetric(self, msg=None,
                   armor=True,
                   filename=None,
                   passphrase=None):
        """
        Armor is turned off for encrypted Axolotl handshake
        """
        if not passphrase: return False
        if not filename:
            result = addressbook.GPG.encrypt(msg,
                                             armor=armor,
                                             recipients=self.fingerprint,
                                             always_trust=True,
                                             sign=addressbook.utils.my_address().fingerprint,
                                             passphrase=passphrase)
        else:
            result = addressbook.GPG.encrypt_file(file(filename, 'rb'),
                                                  output='%s.asc' % filename,
                                                  armor=armor,
                                                  recipients=self.fingerprint,
                                                  always_trust=True,
                                                  sign=addressbook.utils.my_address().fingerprint,
                                                  passphrase=passphrase)
        # FIXME: error states passed in result.stderr should raise exceptions here...
        if not result.ok:
            logger.critical('Something jacked up in GPG encryption... %s' % str(result.__dict__))
            return False
        if armor: return str(result)
        return result
