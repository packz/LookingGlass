
from thirtythirty.settings import LOOKINGGLASS_VERSION_STRING

import email
import subprocess
import re

import addressbook

import logging
logger = logging.getLogger(__name__)

def text_payload(Msg=None):
    if Msg.is_multipart():
        for Part in Msg.get_payload():
            if re.search('text/plain', Part['Content-Type']):
                return Part.get_payload()
    else:
        return Msg.get_payload()


def submit_to_smtpd(Payload=None,
                    Attachments=None,
                    Destination=None,
                    Headers=None,
                    Subject=None,
                    From=None,
                    ):
    """
    we spool this with mutt instead of using smtplib and waiting for server OK
    mutt allows us to specify X-Headers, which we need for hashcash
    hashcash causes the wait to be pretty harsh
    """
    if not Attachments: Attachments = []
    if not Headers: Headers = []
    Headers.extend([
        ('X-Lookingglass-Version', LOOKINGGLASS_VERSION_STRING),
        ])
    if From is None:
        From = addressbook.utils.my_address().email
    Msg = email.mime.text.MIMEText(Payload)
    Msg.set_unixfrom(From)
    for Item in Headers:
        Msg[Item[0]] = Item[1]
    Msg['Subject'] = Subject
    Msg['To'] = Destination
    Msg['From'] = From
    Msg['Reply-To'] = From
    Msg['Date'] = email.utils.formatdate()
    Msg['Message-Id'] = email.utils.make_msgid()
    if len(Attachments) == 0:
        S = subprocess.Popen(['/usr/bin/mutt',
                              '-H', '-',
                              Destination],
                             stdin=subprocess.PIPE)
    else:
        Cmd = ['/usr/bin/mutt',
               '-H', '-',
               '-a']
        Cmd.extend(Attachments)
        Cmd.extend(['--', Destination])
        S = subprocess.Popen(Cmd,
                             stdin=subprocess.PIPE)
    S.communicate(Msg.as_string())
