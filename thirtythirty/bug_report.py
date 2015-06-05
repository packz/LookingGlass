
from django.http import HttpResponse
from django.template import RequestContext, loader

import json
import os.path

import addressbook
import emailclient
import thirtythirty.settings as TTS

from thirtythirty.gpgauth import session_pwd_wrapper

import logging
logger = logging.getLogger(__name__)


class Bug_Report(object):
    Severity_Choices =  [
        {'id':'WISH', 'desc':"This is cool, but you know what would be REALLY cool...", 'class':'text-muted'},
        {'id':'MINOR', 'desc':"This is harder than it needs to be...", 'class':'text-info'},
        {'id':'MAJOR', 'desc':"I can barely make this work by...", 'class':'text-warning'},
        {'id':'EPIC', 'desc':"So broken I can't work because...", 'class':'text-danger'},
        ]


    def __init__(self, severity='MAJOR',
                 summary='eye durnt no wat to sey!'):
        for X in self.Severity_Choices:
            if severity in X['id']:
                self.Severity = X
        self.Summary = summary


    def send(self, passphrase=None):
        Attach = []
        if not addressbook.gpg.verify_symmetric(passphrase):
            passphrase = None
        if not passphrase:
            Attach = ['/tmp/thirtythirty.err',
                      '/tmp/thirtythirty.log',
                      '/tmp/pip.log',]
        else:
            Encrypt = ['/tmp/thirtythirty.err',
                       '/tmp/thirtythirty.log',
                       '/tmp/pip.log',]
            # encrypt the logs
            BRE = addressbook.address.Address.objects.get(
                email=TTS.UPSTREAM['bug_report_email'].upper())
            for E in Encrypt:
                if os.path.exists(E):
                    BRE.asymmetric(filename=E,
                                   passphrase=passphrase)
                    Attach.append('%s.asc' % E)
        logger.debug('Sending %s bug report' % self.Severity['id'])
        emailclient.utils.submit_to_smtpd(
            Attachments=Attach,
            Destination=TTS.UPSTREAM['bug_report_email'],
            Payload=self.Summary,
            Subject='BUGRPT:%s' % self.Severity['id'],
            )


    def render(self, request):
        template = loader.get_template('bug_report.dtl')
        Passed = {
            'title':'Bug Report',
            'bg_image':'notreallyabug.jpg',
            'severity':self.Severity_Choices,
            'explanation':"""
            Here is some text.
            """,
            }
        context = RequestContext(request, Passed)
        return HttpResponse(template.render(context))


@session_pwd_wrapper
def render(request):
    BR = Bug_Report()
    return BR.render(request)


@session_pwd_wrapper
def submit(request):
    Passphrase = request.session.get('passphrase', None)
    if ((not Passphrase) or (not addressbook.gpg.verify_symmetric(Passphrase))):
        Passphrase = None
    BR = Bug_Report(severity = request.POST.get('severity', None),
                    summary = request.POST.get('summary', None))
    BR.send(Passphrase)
    return HttpResponse(json.dumps({'ok':True}),
                        content_type='application/json')

