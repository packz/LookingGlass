
from django.db import models

import hashlib
import os
import random
import struct
from types import LongType, StringType

import addressbook
import exception
import ratchet
import thirtythirty.db_locker
from thirtythirty.settings import LOOKINGGLASS_VERSION_STRING

import logging
logger = logging.getLogger(__name__)


def mulm(x, y, mod):
    return x * y % mod


def createRandomExponent():
    """
    pi has a HWRNG, let's use it.
    """
    x = random.SystemRandom()
    return x.getrandbits(192*8)


def sha256(message):
    return long(hashlib.sha256(str(message)).hexdigest(), 16)


class SMPStep(ratchet.utils.b64Formatter):
    def __init__(self,
                 Step=0,
                 Payload={},
                 Question=None,
                 Import=None):
        sFormat = """%s"""
        rFormat = """^(?P<Payload>.+)$"""
        super(SMPStep, self
              ).__init__(str_format = sFormat,
                         re_format = rFormat,
                         repr_show = ['NOHEX_Step', 'NOHEX_Version'])
        self.Payload = Payload
        self.Step = Step
        self.Question = Question
        self.Version = LOOKINGGLASS_VERSION_STRING
        if Import:
            self.loads(Import=Import)

    def loads(self, Import=None):
        if type(Import) is not StringType: return Import
        jPayload = self.deserialize(Import)
        self.Payload = jPayload['Payload']
        self.Step = jPayload['Step']
        self.Version = jPayload['Version']
        self.Question = jPayload['Question']

    def dumps(self):
        return self.serialize(Payload={'Step':self.Step,
                                       'Payload':self.Payload,
                                       'Question':self.Question,
                                       'Version':self.Version,
                                       },
                              Format=False)


class SMPMgr(thirtythirty.db_locker.LockManager,
             models.Manager,):
    """
    We use this pattern
    https://docs.djangoproject.com/en/1.6/ref/models/instances/
    in order to init the SMP properly
    as well as spin up the LockManager @ the right time
    """
    def hash_secret(self,
                    Conversation=None,
                    question=None,
                    passphrase=None,
                    secret=None):
        """
        Pass the Alice flag straight through from the Axolotl Conversation
        Sort the Axo fingerprints and the shared secret and call that the unencrypted secret
        """
        if not Conversation:
            raise(exception.Need_Axolotl_First('Need to setup Axolotl Conversation, first.'))
        mySMP = self.create(UniqueKey=Conversation.UniqueKey,
                            IAmAlice=Conversation.IAmAlice,
                            Question=question,
                            step=1)
        self.init_for('smp')  # from LockManager
        mySMP.create_secret(secret=secret)
        mySMP.save()
        return mySMP


class SMP(models.Model):
    """
    Original:
    https://shanetully.com/2013/08/mitm-protection-via-the-socialist-millionaire-protocol-otr-style/

    A useful whitepaper:
    http://www.cypherpunks.ca/~iang/pubs/impauth.pdf
    """
    UniqueKey = models.CharField(primary_key=True, max_length=60)
    Question = models.CharField(max_length=100, null=True)
    Shared_Secret = models.CharField(max_length=56, null=True)
    
    Secrets_Match = models.BooleanField(default=False)
    step = models.IntegerField(default=0,
                               choices=[ (X,X) for X in range(0,6) ])
    IAmAlice = models.BooleanField(default=True)

    # HOW ABOUT A BIG PLATE OF STATE?
    """
|------+---------------+-------------+-------------+-----------|
| Step | Alice Assigns | Alice Reads | Bob Assigns | Bob Reads |
|------+---------------+-------------+-------------+-----------|
|    1 | x2/x3         |             |             |           |
|------+---------------+-------------+-------------+-----------|
|    2 |               |             | g3a         | Secret    |
|      |               |             | gb2/gb3     |           |
|      |               |             | pb          |           |
|      |               |             | qb          |           |
|      |               |             | x3          |           |
|------+---------------+-------------+-------------+-----------|
|    3 | g3b           | Secret      |             |           |
|      | pa/pb         | x2/x3       |             |           |
|      | qa/qb         |             |             |           |
|------+---------------+-------------+-------------+-----------|
|    4 |               |             |             | g3a       |
|      |               |             |             | gb2/gb3   |
|      |               |             |             | pb        |
|      |               |             |             | qb        |
|      |               |             |             | x3        |
|------+---------------+-------------+-------------+-----------|
|    5 |               | g3b         |             |           |
|      |               | pa/pb       |             |           |
|      |               | qa/qb       |             |           |
|      |               | x3          |             |           |
|------+---------------+-------------+-------------+-----------|
    """
    g3a = models.TextField()
    g3b = models.TextField()
    gb2 = models.TextField()
    gb3 = models.TextField()
    pa  = models.TextField()
    pb  = models.TextField()
    qa  = models.TextField()
    qb  = models.TextField()
    x2  = models.TextField()
    x3  = models.TextField()

    objects = SMPMgr()

    rfc3526g5 = long(  # the notorious (1536 bit) P.R.I.M.E.
        '2410312426921032588552076022197566074856950548502459942654116941' +\
        '9581088316826122288900938582613416146732271414779040121965036489' +\
        '5705058263194273070680500922306273474534107340669624601458936165' +\
        '9774041027169249453200378729434170325843778659198143763193776859' +\
        '8695240889401955773461198435453015470437472077499697637500843089' +\
        '2633929555996888245787241299381012913029459299994792636526405928' +\
        '4647209730384947211681434464714438488520940127459844288859336526' +\
        '896320919633919'
        )
    MD5_Typo_Check = '6180e6871ff0c6bbf615b89202a931a3'
    assert type(rfc3526g5) == LongType
    assert MD5_Typo_Check == hashlib.md5(str(rfc3526g5)).hexdigest()

    modOrder = (rfc3526g5-1) / 2
    gen = 2


    def __unicode__(self):
        A = addressbook.address.Address.objects.get(
            fingerprint=self.UniqueKey)        
        Name = 'Alice'
        if not self.IAmAlice: Name = 'Bob'
        return u'<%s in %s mode, on step %s, %sly matched>' % (A.covername,
                                                               Name, self.step,
                                                               self.Secrets_Match)


    def remove(self, fail=True):
        A = addressbook.address.Address.objects.get(
            fingerprint=self.UniqueKey)
        if fail:
            A.user_state = addressbook.address.Address.NOT_VETTED
            A.smp_failures = models.F('smp_failures') + 1
        else:
            A.user_state = addressbook.address.Address.AUTHED
            A.smp_failures = 0
            R = ratchet.conversation.Conversation.objects.get(
                UniqueKey = A.fingerprint
                )
            R.verify_fingerprint(True)
            R.save()
        A.save()
        addressbook.queue.Queue.objects.filter(
            address=A,
            direction=addressbook.queue.Queue.SMP_Replay,
            ).delete()
        self.delete()
        

    def create_secret(self, secret=None, conversation=None):
        if secret is None:
            return False
        if self.step >= 3:
            raise(exception.Secret_Already_Set("You're in too deep, now."))
        if self.Shared_Secret:
            logger.warning('Secret was already set when I was asked to reset it.')
        Convo = conversation
        if Convo is None:
            if self.UniqueKey is None:
                raise(exception.Need_Axolotl_First('I am far too simple to authenticate before we exchange greetings()'))
            try:
                Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=self.UniqueKey)
            except:
                raise(exception.Need_Axolotl_First('I am far too simple to authenticate before we exchange greetings()'))
        L = Convo.my_fingerprint()
        R = Convo.their_fingerprint()
        if ((L is None) or (R is None)):
            raise(exception.Need_Axolotl_First('I am far too simple to authenticate before we exchange greetings()'))
        if L < R:
            Secret = '%s%s%s' % (L, R, secret)
        else:
            Secret = '%s%s%s' % (R, L, secret)
        self.Shared_Secret = hashlib.sha224(str(Secret)).hexdigest()
        self.save()
        return True
    

    def advance_step(self, sStep=None):
        Step = SMPStep(Import=sStep)
        if ((Step.Step == 0) and self.IAmAlice and (self.step == 1)):
            self.step = 2
            jP = self.__step1()
            self.save()
            return jP.dumps()
        elif ((Step.Step == 1) and (not self.IAmAlice) and (self.step == 1)):
            self.step = 3
            jP = self.__step2(Step)
            self.save()
            return jP.dumps()
        elif ((Step.Step == 2) and self.IAmAlice and (self.step == 2)):
            self.step = 4
            jP = self.__step3(Step)
            self.save()
            return jP.dumps()
        elif ((Step.Step == 3) and (not self.IAmAlice) and (self.step == 3)):
            self.step = 5
            jP = self.__step4(Step)
            self.save()
            return jP.dumps()
        elif ((Step.Step == 4) and self.IAmAlice and (self.step == 4)):
            self.step = 5
            jP = self.__step5(Step)
            self.save()
            return jP # finally maybe True!
        elif self.step == 5:
            return self.Secrets_Match
        else:
            raise(exception.Socialist_Misstep('I got step %s, but I am on step %s' % (Step.Step, self.step)))


    def __step1(self):
        """
        Alice initiates
        """
        self.x2 = createRandomExponent()
        self.x3 = createRandomExponent()

        g2 = pow(self.gen,
                 self.x2,
                 self.rfc3526g5)
        g3 = pow(self.gen,
                 self.x3,
                 self.rfc3526g5)

        (c1, d1) = self.createLogProof('1', self.x2)
        (c2, d2) = self.createLogProof('2', self.x3)

        Step = SMPStep(Step=1,
                       Question=self.Question,
                       Payload={
                           'c1':c1,
                           'c2':c2,
                           'd1':d1,
                           'd2':d2,
                           'g2':g2,
                           'g3':g3,
                           })
        return Step
    

    def __step2(self, Step):
        """
        Bob takes the ball
        """
        g2a = Step.Payload['g2']
        g3a = Step.Payload['g3']
        c1 = Step.Payload['c1']
        c2 = Step.Payload['c2']
        d1 = Step.Payload['d1']
        d2 = Step.Payload['d2']

        if not self.isValidArgument(g2a) or not self.isValidArgument(g3a):
            raise ValueError("Invalid g2a/g3a values")

        if not self.checkLogProof('1', g2a, c1, d1):
            raise ValueError("Proof 1 check failed")

        if not self.checkLogProof('2', g3a, c2, d2):
            raise ValueError("Proof 2 check failed")

        self.g3a = g3a

        x2 = createRandomExponent()
        self.x3 = createRandomExponent()
        r = createRandomExponent()

        g2 = pow(self.gen,
                 x2,
                 self.rfc3526g5)
        g3 = pow(self.gen,
                 self.x3,
                 self.rfc3526g5)

        (c3, d3) = self.createLogProof('3', x2)
        (c4, d4) = self.createLogProof('4', self.x3)

        self.gb2 = pow(g2a,
                       x2,
                       self.rfc3526g5)
        self.gb3 = pow(g3a,
                       self.x3,
                       self.rfc3526g5)

        self.pb = pow(self.gb3,
                      r,
                      self.rfc3526g5)
        if not self.Shared_Secret:
            raise(exception.Unset_Secret('You need to hash_secret() before you can continue'))
        LongSecret = long(self.Shared_Secret, 16)
        self.qb = mulm(pow(self.gen,
                           r,
                           self.rfc3526g5),
                       pow(self.gb2,
                           LongSecret,
                           self.rfc3526g5),
                       self.rfc3526g5)

        (c5, d5, d6) = self.createCoordsProof('5', self.gb2, self.gb3, r)

        # g2b, g3b, pb, qb, all the c's and d's
        Step = SMPStep(Step=2,
                       Question=self.Question,
                       Payload={
                           'c3':c3,
                           'c4':c4,
                           'c5':c5,
                           'd3':d3,
                           'd4':d4,
                           'd5':d5,
                           'd6':d6,
                           'g2':g2,
                           'g3':g3,
                           'pb':self.pb,
                           'qb':self.qb,
                           })
        return Step


    def __step3(self, Step):
        """
        Back to Alice
        """
        c3 = Step.Payload['c3']
        c4 = Step.Payload['c4']
        c5 = Step.Payload['c5']
        d3 = Step.Payload['d3']
        d4 = Step.Payload['d4']
        d5 = Step.Payload['d5']
        d6 = Step.Payload['d6']
        g2b = Step.Payload['g2']
        g3b = Step.Payload['g3']
        pb = Step.Payload['pb']
        qb = Step.Payload['qb']

        if not self.isValidArgument(g2b) or not self.isValidArgument(g3b) or \
           not self.isValidArgument(pb) or not self.isValidArgument(qb):
            raise ValueError("Invalid g2b/g3b/pb/qb values")

        if not self.checkLogProof('3', g2b, c3, d3):
            raise ValueError("Proof 3 check failed")

        if not self.checkLogProof('4', g3b, c4, d4):
            raise ValueError("Proof 4 check failed")

        self.g3b = g3b

        ga2 = pow(g2b,
                  long(self.x2),
                  self.rfc3526g5)
        ga3 = pow(self.g3b,
                  long(self.x3),
                  self.rfc3526g5)

        if not self.checkCoordsProof('5', c5, d5, d6, ga2, ga3, pb, qb):
            raise ValueError("Proof 5 check failed")

        s = createRandomExponent()

        self.qb = qb
        self.pb = pb
        self.pa = pow(ga3,
                      s,
                      self.rfc3526g5)
        if not self.Shared_Secret:
            raise(exception.Unset_Secret('You need to hash_secret() before you can continue'))
        LongSecret = long(self.Shared_Secret, 16)
        self.qa = mulm(pow(self.gen,
                           s,
                           self.rfc3526g5),
                       pow(ga2,
                           LongSecret,
                           self.rfc3526g5),
                       self.rfc3526g5)

        (c6, d7, d8) = self.createCoordsProof('6', ga2, ga3, s)

        inv = self.invm(qb)
        self.ra = pow(mulm(self.qa, inv, self.rfc3526g5),
                      long(self.x3),
                      self.rfc3526g5)

        (c7, d9) = self.createEqualLogsProof('7', self.qa, inv, long(self.x3))

        # Sends pa, qa, ra, c6, d7, d8, c7, d9
        Step = SMPStep(Step=3,
                       Payload={
                           'c6':c6,
                           'c7':c7,
                           'd7':d7,
                           'd8':d8,
                           'd9':d9,
                           'pa':self.pa,
                           'qa':self.qa,
                           'ra':self.ra,
                           })
        return Step


    def __step4(self, Step):
        """
        Hello, Bob here
        """
        c6 = Step.Payload['c6']
        c7 = Step.Payload['c7']
        d7 = Step.Payload['d7']
        d8 = Step.Payload['d8']
        d9 = Step.Payload['d9']
        pa = Step.Payload['pa']
        qa = Step.Payload['qa']
        ra = Step.Payload['ra']

        if not self.isValidArgument(pa) or \
               not self.isValidArgument(qa) or \
               not self.isValidArgument(ra):
            raise ValueError("Invalid pa/qa/ra values")

        if not self.checkCoordsProof('6', c6, d7, d8, long(self.gb2), long(self.gb3), pa, qa):
            raise ValueError("Proof 6 check failed")

        if not self.checkEqualLogs('7', c7, d9, long(self.g3a), mulm(qa, self.invm(long(self.qb)), self.rfc3526g5), ra):
            raise ValueError("Proof 7 check failed")

        inv = self.invm(long(self.qb))
        rb = pow(mulm(qa, inv, self.rfc3526g5),
                 long(self.x3),
                 self.rfc3526g5)

        (c8, d10) = self.createEqualLogsProof('8', qa, inv, long(self.x3))

        rab = pow(ra,
                  long(self.x3),
                  self.rfc3526g5)

        inv = self.invm(long(self.pb))
        if rab == mulm(pa,
                       inv,
                       self.rfc3526g5):
            self.Secrets_Match = True

        Step = SMPStep(Step=4,
                       Payload={
                           'rb':rb,
                           'c8':c8,
                           'd10':d10,
                           })
        return Step


    def __step5(self, Step):
        """
        Out of Bob's kindness, Alice gets the memo
        """
        rb = Step.Payload['rb']
        c8 = Step.Payload['c8']
        d10 = Step.Payload['d10']

        if not self.isValidArgument(rb):
            raise ValueError("Invalid rb values")

        if not self.checkEqualLogs('8', c8, d10,
                                   long(self.g3b),
                                   mulm(long(self.qa),
                                        self.invm(long(self.qb)),
                                        self.rfc3526g5),
                                   rb):
            raise ValueError("Proof 8 check failed")

        rab = pow(rb,
                  long(self.x3),
                  self.rfc3526g5)

        inv = self.invm(long(self.pb))
        if rab == mulm(long(self.pa),
                       inv,
                       self.rfc3526g5):
            self.Secrets_Match = True
            return True
        else:
            return False


    def createLogProof(self, version, x):
        randExponent = createRandomExponent()
        c = sha256(version + str(pow(self.gen, randExponent, self.rfc3526g5)))
        d = (randExponent - mulm(x, c, self.modOrder)) % self.modOrder
        return (c, d)


    def checkLogProof(self, version, g, c, d):
        gd = pow(self.gen,
                 d,
                 self.rfc3526g5)
        gc = pow(g,
                 c,
                 self.rfc3526g5)
        gdgc = gd * gc % self.rfc3526g5
        return (sha256(version + str(gdgc)) == c)


    def createCoordsProof(self, version, g2, g3, r):
        r1 = createRandomExponent()
        r2 = createRandomExponent()

        tmp1 = pow(g3, r1, self.rfc3526g5)
        tmp2 = mulm(
            pow(self.gen,
                r1,
                self.rfc3526g5),
            pow(g2,
                r2,
                self.rfc3526g5),
            self.rfc3526g5)

        c = sha256(version + str(tmp1) + str(tmp2))

        # TODO: make a subm function
        d1 = (r1 - mulm(r,
                        c,
                        self.modOrder)) % self.modOrder
        LongSecret = long(self.Shared_Secret, 16)
        d2 = (r2 - mulm(LongSecret,
                        c,
                        self.modOrder)) % self.modOrder

        return (c, d1, d2)


    def checkCoordsProof(self, version, c, d1, d2, g2, g3, p, q):
        tmp1 = mulm(
            pow(g3,
                d1,
                self.rfc3526g5),
            pow(p,
                c,
                self.rfc3526g5),
            self.rfc3526g5)

        tmp2 = mulm(
            mulm(
                pow(self.gen,
                    d1,
                    self.rfc3526g5),
                pow(g2,
                    d2,
                    self.rfc3526g5),
                self.rfc3526g5),
            pow(q,
                c,
                self.rfc3526g5),
            self.rfc3526g5)

        cprime = sha256(version + str(tmp1) + str(tmp2))

        return (c == cprime)


    def createEqualLogsProof(self, version, qa, qb, x):
        r = createRandomExponent()
        tmp1 = pow(self.gen,
                   r,
                   self.rfc3526g5)
        qab = mulm(qa,
                   qb,
                   self.rfc3526g5)
        tmp2 = pow(qab,
                   r,
                   self.rfc3526g5)

        c = sha256(version + str(tmp1) + str(tmp2))
        tmp1 = mulm(x,
                    c,
                    self.modOrder)
        d = (r - tmp1) % self.modOrder

        return (c, d)


    def checkEqualLogs(self, version, c, d, g3, qab, r):
        tmp1 = mulm(
            pow(self.gen,
                d,
                self.rfc3526g5),
            pow(g3,
                c,
                self.rfc3526g5),
            self.rfc3526g5)

        tmp2 = mulm(
            pow(qab,
                d,
                self.rfc3526g5),
            pow(r,
                c,
                self.rfc3526g5),
            self.rfc3526g5)

        cprime = sha256(version + str(tmp1) + str(tmp2))
        return (c == cprime)


    def invm(self, x):
        return pow(x,
                   self.rfc3526g5-2,
                   self.rfc3526g5)


    def isValidArgument(self, val):
        return (val >= 2 and val <= self.rfc3526g5-2)
