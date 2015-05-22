
from django.db.models import Q

import email
import mailbox
import os.path
import subprocess

import addressbook
import emailclient

from thirtythirty.settings import USERNAME
MAIL_ROOT = '/home/%s/Maildir/' % USERNAME

import logging
logger = logging.getLogger('emailclient')

def __count_new_mail(aMbx=None):
    count = 0
    for MK in aMbx.keys():
        if 'S' not in aMbx.get(MK).get_flags():
            count += 1
    return count


def new_mail_in_inbox():
    Inbox = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder('')
    CNM = __count_new_mail(Inbox)
    if CNM == 0: return ''
    else: return CNM


def list_folders(sanitize=False):
    Root = mailbox.Maildir(MAIL_ROOT, factory=False).list_folders()
    Root.insert(0, '')
    ret = []
    for F in Root:
        if ((sanitize) and (F in ['admin', 'trash'])): continue
        Mbx = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(F)
        pretty = F.split('.')[-1]
        if pretty == '': pretty = 'inbox'
        ret.append({
            'pretty_name':pretty,
            'real_name':F,
            'new_mail':__count_new_mail(Mbx),
            'mbx':Mbx,
            })
    return ret


def folder_from_msg_key(aKey=None):
    """
    an otherwise one-way mapping, ugh.
    """
    for M in list_folders():
        if aKey in M['mbx'].keys():
            return M
    return None


def fast_folder_find(aKey=None):
    """
    only the mbx portion of folder_from_msg_key()
    flagging messages was taking WAAAAY too long
    """
#    logger.debug('searching for %s' % aKey)
    Folder = subprocess.check_output(['/usr/bin/find',
                                      MAIL_ROOT,
                                      '-type', 'f',
                                      # flags go @ the ass-end of msg names on-disk
                                      '-name', '%s*' % aKey]).strip()
    if '/' not in Folder: return None
#    logger.debug('located in %s' % Folder)
    Folder_Name = Folder.split('/')[4]
    if Folder_Name == 'cur': Folder_Name = ''
    # remove the leading period...
    Folder_Name = Folder_Name[1:]
    return mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(Folder_Name)


def msg_key_from_msg(aMsg=None):
    """
    AGAIN
    we use rfc 2111 to save our ass
    used by hyphens

    rather than iterate over the entire message tree,
    which was causing the pi to smoke with larger mailboxes,
    we caveman this shit.

    note: if someone includes entire UNENCRYPTED headers in a msg reply
          we choose the youngest file by file date, and pray.
    """
    try:
        patientZero = subprocess.check_output(['/bin/grep',
                                               '--files-with-matches',
                                               '--recursive',
                                               '^Message-I[dD]: %s$' % aMsg['Message-Id'],
                                               MAIL_ROOT,
                                               ]).strip().split('\n')
    except: return None
    # hehehe - we depend on filename for sort order
    patientZero = sorted(patientZero)[0]
    chopchop = patientZero.split('/')[-1].split(':2,')
    return chopchop[0]


def message_count(folderName=None):
    Mbx = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(folderName)
    if Mbx: return len(Mbx)
    else: return 0
    

def sorted_messages_in_folder(folder=None, folderName=None, messageKey=None, debug=False):
    """
    FIXME: this fails pretty hard once the # of msgs in a folder gets >20 - need to move over to something like https://github.com/coddingtonbear/django-mailbox
    """
    if folder:
        if debug:
            logger.debug('Traced request for folder w/ contents `%s`' % (folder.keys()))
        Sort = sorted(folder.keys(),
                      key=lambda msg: email.utils.parsedate(folder.get(msg)['date']))
        Sort.reverse()
        return [ folder.get(X) for X in Sort ]
    elif folderName is not None:
        if debug:
            logger.debug('Traced request for folderName `%s`' % (folderName))
        # may get passed empty string for inbox - be ware
        try:
            Mbx = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(folderName)
        except:
            return []
        if Mbx:
            return sorted_messages_in_folder(folder=Mbx)
    elif messageKey:
        if debug:
            logger.debug('Traced request for messageKey `%s`' % (messageKey))
        Folder = folder_from_msg_key(messageKey)
        if Folder:
            return sorted_messages_in_folder(folder=Folder['mbx'])
    # road to nowhere
    return []


def discard(aKey=None):
    F = folder_from_msg_key(aKey)
    if not F: return False
    F['mbx'].discard(aKey)
    return True


def flag(aKey=None, addFlag=None, remFlag=None):
    F = fast_folder_find(aKey)
    if not F: return {'ok':False}
    Msg = F.get(aKey)
    Msg.set_subdir('cur')
    if addFlag:
        Msg.add_flag(addFlag)
        F[aKey] = Msg
    if remFlag:
        Msg.remove_flag(remFlag)
        F[aKey] = Msg
    return {'ok':True, 'extra':Msg.get_flags(), 'MK':aKey}
    

def create_folder(folderName=None):
    if not folderName: return {'ok':False, 'folderName':'not provided'}
    from re import sub
    sanitized = sub('[^-_a-zA-Z0-9]+', '_', folderName)
    mailbox.Maildir(MAIL_ROOT, factory=False).add_folder(sanitized)
    return {'ok':True, 'folderName':sanitized}


def delete_folder(folderName=None):
    if not folderName: return {'ok':False, 'folderName':'not provided'}
    try: F = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(folderName)
    except: {'ok':False, 'folderName':'does not exist'}
    trashed = []
    for MK in F.keys():
        flag(MK, addFlag='T')
        move(MK, folderName='trash')
        logger.debug('trashing message %s' % MK)
        trashed.append(MK)
    mailbox.Maildir(MAIL_ROOT, factory=False).remove_folder(folderName)
    return {'ok':True, 'folderName':folderName, 'trashed':trashed}


def move(MK=None,
         folderName=None):
    if folderName is None:
        return False
    logger.debug('moving message %s to %s' % (MK, folderName))
    try:
        Destination = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(folderName)
    except:
        create_folder(folderName)
        Destination = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(folderName)

    FH = folder_from_msg_key(MK)
    if not FH:
        return False
    Source = FH['mbx']
    Msg = Source.get(MK)

    New_Key = Destination.add(Msg)
    discard(MK)

    if folderName != 'trash':
        flag(New_Key, remFlag='T')
    
    return New_Key


def format_email(to=None,
                 ffrom=None,
                 date=None,
                 subject=None,
                 body=None,
                 msgObject=None):
    """
    contains maildir-specific extensions...
    """
    if not msgObject:
        msgObject = mailbox.MaildirMessage()
        msgObject['Message-Id'] = email.utils.make_msgid()
    msgObject.set_payload(body)
    for X in ['Subject', 'To', 'From', 'Date']:
        # otherwise we'll add multiple values
        del msgObject[X]
    msgObject['Subject'] = subject
    msgObject['To'] = to
    if ffrom:
        msgObject['From'] = ffrom
    else:
        msgObject['From'] = addressbook.utils.my_address().email
    if date:
        msgObject['Date'] = date
    else:
        msgObject['Date'] = email.utils.formatdate()
    msgObject.set_flags('S')
    msgObject.set_subdir('cur')
    return msgObject


def save_local(to=None,
               ffrom=None,
               date=None,
               subject=None,
               body=None,
               passphrase=None,
               Folder='drafts',
               MK=None):
    """
    MK may be None when the message was Axolotl and disappeared after decrypt
    """
    if not addressbook.gpg.verify_symmetric(passphrase):
        return {'ok':False,
                'extra':'wrong passphrase'}

    try:
        Drafts = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(Folder)
    except:
        create_folder(Folder)
        Drafts = mailbox.Maildir(MAIL_ROOT, factory=False).get_folder(Folder)

    Payload = str(addressbook.gpg.symmetric(passphrase=passphrase, msg=body))
    Msg = None
    if ((MK is None) or (folder_from_msg_key(aKey=MK) is None)):
        Msg = format_email(to=to,
                           ffrom=ffrom,
                           date=date,
                           subject=subject,
                           body=Payload)
    else:
        Drafts = folder_from_msg_key(aKey=MK)['mbx']
        Msg = format_email(to=to,
                           ffrom=ffrom,
                           subject=subject,
                           body=Payload,
                           msgObject=Drafts.get(MK))

    Xtra = None
    if ((MK is None) or (folder_from_msg_key(aKey=MK) is None)):
        Xtra = Drafts.add(Msg)
    else:
        Drafts[MK] = Msg
        Xtra = MK

    return {'ok':True,
            'extra':Xtra}


def send(to=None,
         fp=None,
         subject=None,
         body=None,
         passphrase=None,
         MK=None):

    if not addressbook.gpg.verify_symmetric(passphrase):
        return {'ok':False,
                'extra':'wrong passphrase'}

    To = addressbook.address.Address.objects.filter(
        Q(covername__icontains=to) |\
        Q(nickname__icontains=to) |\
        Q(email__icontains=to) |\
        Q(fingerprint__iexact=fp)
        )
    if len(To) != 1:
        return {'ok':False,
                'extra':"can't figure out who this is to..."}
    To = To[0]

    save_local(to=To.email,
               subject=subject,
               body=body,
               Folder='sent',
               passphrase=passphrase)

    Payload = str(To.asymmetric(msg=body, passphrase=passphrase))
    
    emailclient.utils.submit_to_smtpd(Destination=To.email,
                                      Payload=Payload,
                                      Subject=subject)

    return {'ok':True,
            'extra':'submitted to local smtpd'}
