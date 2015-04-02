
from django.db.models import Q

import email
import subprocess
import mailbox

import addressbook
import emailclient

from ratchet.utils import hulk_smash_unicode

import thirtythirty.settings as TTS
MAIL_ROOT = '/home/%s/Maildir/' % TTS.USERNAME

import logging
logger = logging.getLogger(__name__)

def Folders(hidden=False):
    Root = mailbox.Maildir(MAIL_ROOT, factory=False).list_folders()
    Root.insert(0, '')
    ret = []
    for F in Root:
        if ((hidden) and (F in ['admin', 'trash'])): continue
        ret.append(LGFolder(F))
    return ret


class LGFolder(mailbox.Maildir):
    def __init__(self, Folder=''):
        return super(LGFolder, self).__init__(MAIL_ROOT, factory=False).get_folder(Folder)

    def new_mail(self):
        count = 0
        for MK in self.keys():
            if 'S' not in self.get(MK).get_flags():
                count += 1
        return count

        

class LGEmail(email.mime.multipart.MIMEMultipart,
              mailbox.MaildirMessage):    
    def get_date(self):
        return 0 

    def Locate(self, key_or_id=None):
        """
        We may get either the message-id (in the headers) or the maildir filename
        Find message, whereever it may seek to hide
        """
        if self.has_key('location') and self.location:
            return self.location
        Search = re.compile(key_or_id)
        Parse  = re.compile('%s/(?P<Folder>\.[^\/]+\/)?(cur|new|tmp)\/(?P<MK>[^:]+)(:2[^:]*)?:Message-I[dD]: (?P<MID>.*)$' % MAIL_ROOT)
        for Message in subprocess.check_output(['/usr/bin/find',
                                                MAIL_ROOT,
                                                '-type', 'f',
                                                '-exec',
                                                '/bin/grep',
                                                '--with-filename',
                                                '^Message-I[dD]',
                                                '{}',
                                                ';'
                                                ]).split('\n'):
            if Search.search(Message):
                P = Parse.search(Message)
                if P:
                    ret = P.groupdict()
                    if not ret['Folder']:
                        ret['Folder'] = LGFolder()
                    else:
                        ret['Folder'] = LGFolder(ret['Folder'][1:-1])
                    self.location = ret
                    return ret
        self.location = None
        return None


    def Decrypt(self, Passphrase=None):
        if not addressbook.gpg.verify_symmetric(Passphrase):
            raise(emailclient.exception.Bad_Passphrase('Lame passphrase'))


    def Attach(self,
               Filename=None,
               Passphrase=None):
        if not os.path.exists(filename):
            raise(emailclient.exception.No_Attachment("Can't find %s" % filename))
        part = email.MIMEBase.MIMEBase('application', 'octet-stream')
        part.set_payload(file(filename, 'rb').read())
        email.Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % filename)
        self.attach(part)


    def __who_to(self, To=None):
        To = addressbook.address.Address.objects.filter(
            Q(covername__icontains=to) |\
            Q(nickname__icontains=to) |\
            Q(email__icontains=to) |\
            Q(fingerprint__iexact=fp)
            )
        if len(To) != 1:
            raise addressbook.exception.Ambiguous_To('`%s` is too vague.' % To)
        return To[0].email


    def Format(self,
               To=None, From=None,
               Headers=[],
               Date=None, Subject=None,
               Body=None,
               Attach=[],
               Passphrase=None):
        if Body:
            self.preamble = hulk_smash_unicode(Body)
        for A in Attach:
            self.Attach(A)
        for Hr in Headers:
            Hk, Hv = Hr # will break on weird RFC2231 hash values that are insane and deserve breaking
            self.add_header(Hk, Hv)
        for X in ['Subject', 'To', 'From', 'Date']:
            # otherwise we'll add multiple values
            del self[X]
        self['Subject'] = Subject
        self['To'] = self.__who_to(To)
        if From:
            self['From'] = From
        else:
            self['From'] = addressbook.utils.my_address().email
        self.set_unixfrom(self['From'])
        self['Reply-To'] = self['From']
        if Date:
            self['Date'] = Date
        else:
            self['Date'] = email.utils.formatdate()

        self.set_flags('S')
        self.set_subdir('cur')
        if ((not self.has_key('location')) or
            (self.has_key('location') and not self.location)):
            self['Message-Id'] = email.utils.make_msgid()


    def Save(self,
             Folder='drafts',
             Passphrase=None):
        """
        For drafts and sent
        """
        if self.has_key('location') and self.location:
            SaveTo = self.location['Folder']
            SaveTo[self.location['MK']] = self
        else:
            try:
                SaveTo = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(Folder)
            except:
                create_folder(Folder)
                SaveTo = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(Folder)
            SaveTo.add(self)


    def Send(self, Passphrase=None):
        self.Save(Folder='sent', Passphrase=Passphrase)
        Headers = [
            ('X-Lookingglass-Version', TTS.LOOKINGGLASS_VERSION_STRING),
            ]
        Cmd = subprocess.Popen(['/usr/bin/mutt',
                                '-H', '-',
                                self['To']],
                               stdin=subprocess.PIPE)
        Cmd.communicate(self.as_string())
