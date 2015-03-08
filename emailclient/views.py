
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template import RequestContext, loader

from django.db.models import Q

import datetime
import json
import re
from types import StringType, ListType

import addressbook
import emailclient
import ratchet
import thirtythirty

from thirtythirty.gpgauth import session_pwd_wrapper, set_up_single_user

import logging
logger = logging.getLogger(__name__)


@session_pwd_wrapper
def folder(request, name=''):    
    magic_inbox = name
    if magic_inbox == 'inbox':
        magic_inbox = ''
    pretty_name = name.split('.')[-1]
    if pretty_name == '':
        pretty_name = 'inbox'

    # allow folder mgmt
    custom_folder = False
    if name not in ['', 'inbox', 'admin', 'sent', 'trash', 'drafts']:
        custom_folder = True

#    logger.debug('Got request for folder `%s`' % name)

    context = RequestContext(request, {
        'title':pretty_name,
        'nav':'Email',
        'bg_image':'inbox.jpg',
        'vitals':thirtythirty.utils.Vitals(request),
        'sorted':emailclient.filedb.sorted_messages_in_folder(folderName=magic_inbox.lstrip()),
        'srcFolder':name,
        'folder_list':emailclient.filedb.list_folders(sanitize=True),
        'custom_folder':custom_folder,
        })
    template = loader.get_template('folder.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def view(request, Key=None, advanced=False):
    Preferences = set_up_single_user()
    if Preferences.show_advanced: advanced = True
    
    FolderHash = emailclient.filedb.folder_from_msg_key(Key)
    if not FolderHash: return redirect('emailclient.inbox')

    Msg = FolderHash['mbx'].get(Key)

    Fingerprint = addressbook.address.Address.objects.filter(
        Q(email__iexact=Msg['to']) |\
        Q(email__iexact=Msg['from']) |\
        Q(covername__iexact=Msg['to']) |\
        Q(covername__iexact=Msg['from']) |\
        Q(nickname__iexact=Msg['to']) |\
        Q(nickname__iexact=Msg['from'])
        ).filter(
        is_me = False
        ).first()
    if Fingerprint: Fingerprint = Fingerprint.fingerprint
    
    Folder_Keys = emailclient.filedb.sorted_messages_in_folder(messageKey=Key)
    Next = None
    Prev = None
    for X in range(0, len(Folder_Keys)):
        MK = emailclient.filedb.msg_key_from_msg(Folder_Keys[X])
        if MK == Key:
            if X > 0:
                Prev = emailclient.filedb.msg_key_from_msg(Folder_Keys[X-1])
            if X < len(Folder_Keys)-1:
                Next = emailclient.filedb.msg_key_from_msg(Folder_Keys[X+1])
            break

    context = RequestContext(request, {
        'title':FolderHash['pretty_name'],
        'nav':'Email',
        'bg_image':'inbox.jpg',
        'vitals':thirtythirty.utils.Vitals(request),
        'folder_list':emailclient.filedb.list_folders(sanitize=True),
        'fingerprint':Fingerprint,
        'advanced':advanced,
        'symmetric':Preferences.rx_symmetric_copy,
        'Key':Key,
        'Msg':Msg,
        'nextMsg':Next,
        'prevMsg':Prev,
        })
    template = loader.get_template('message.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def compose(request, Name=None, FP=None):
    magic = {}
    for X in ['to', 'subject', 'body', 'MK']:
        if request.POST.get(X):
            magic[X] = re.sub('\\\\n', '\n', request.POST.get(X))
    if FP or request.POST.get('fp', None):
        if request.POST.get('fp', None):
            FP = request.POST.get('fp', None)
        try:
            A = addressbook.address.Address.objects.get(fingerprint=FP)
            magic['to'] = A.nickname
            if not magic['to']: magic['to'] = A.covername
            magic['fp'] = FP
        except:
            # we have run into an email generated locally, perhaps.
            # let this pass to the compose window, so we can save draft, if there has been a mistake
            pass
    # reply is email-style quoted
    if magic.has_key('body'):
        magic['body'] = re.sub('(?m)^', '> ', magic['body'])
    context = RequestContext(request, {
        'title':'Composition',
        'nav':'Email',
        'bg_image':'compose.jpg',
        'vitals':thirtythirty.utils.Vitals(request),
        'folder_list':emailclient.filedb.list_folders(sanitize=True),
        'friends':addressbook.address.Address.objects.filter(is_me=False, system_use=False),
        'magic':magic,
        })
    template = loader.get_template('compose.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def send(request):
    PP = request.session.get('passphrase', None)
    if ((not PP) or (not addressbook.gpg.verify_symmetric(PP))):
        return HttpResponse(json.dumps({'ok':False,
                                        'extra':'Bad passphrase'}))

    To = request.POST.get('to', None)
    Addr = addressbook.address.Address.objects.filter(
        Q(fingerprint__iexact=request.POST.get('fingerprint')) |\
        Q(email__iexact=To) |\
        Q(covername__iexact=To) |\
        Q(nickname__iexact=To)
        )
    logger.debug(Addr)
    if len(Addr) != 1:
        return HttpResponse(json.dumps({'ok':False,
                                        'extra':'Address clown show'}))
    else:
        Addr = Addr[0]
        
    if (request.POST.get('mode') == 'save'):
        return HttpResponse(json.dumps(
            emailclient.filedb.save_local(to=Addr.email,
                              subject=request.POST.get('subject'),
                              body=request.POST.get('body'),
                              passphrase=PP,
                              MK=request.POST.get('MK', None),
                              )), content_type='application/json')

    elif Addr.user_state == addressbook.address.Address.KNOWN:
        # GPG
        Preferences = set_up_single_user()
        if Preferences.tx_symmetric_copy:
            emailclient.filedb.save_local(to=Addr.email,
                              subject=request.POST.get('subject'),
                              body=request.POST.get('body'),
                              passphrase=PP,
                              Folder='sent',
                              )

        emailclient.utils.submit_to_smtpd(
            Payload=Addr.asymmetric(
                msg=request.POST.get('body'),
                passphrase=PP),
            Destination=Addr.email,
            Subject=request.POST.get('subject'))
        logger.debug('GPG Encrypted, queued message to %s' % Addr.email)

        # FIXME: maybe some failure counter to renegotiate Axolotl
        
        return HttpResponse(json.dumps({
            'ok':True,
            'extra':'GPG queued to SMTP',
            }),content_type='application/json')

    elif Addr.user_state > addressbook.address.Address.KNOWN:
        # Axolotl
        Preferences = set_up_single_user()
        if Preferences.tx_symmetric_copy:
            emailclient.filedb.save_local(to=Addr.email,
                              subject=request.POST.get('subject'),
                              body=request.POST.get('body'),
                              passphrase=PP,
                              Folder='sent',
                              )

        ratchet.conversation.Conversation.objects.init_for('ratchet')
        try:
            ratchet.conversation.Conversation.objects.decrypt_database(PP)
            logger.debug('Ratchet database decrypted')
        except thirtythirty.exception.Target_Exists:
            pass
        Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
        logger.debug('Conversation loaded')
        emailclient.utils.submit_to_smtpd(Payload=Convo.encrypt(request.POST.get('body')),
                                          Destination=Addr.email,
                                          Subject=request.POST.get('subject'))
        logger.debug('Axolotl Encrypted, queued message to %s' % Addr.email)
        return HttpResponse(json.dumps({
            'ok':True,
            'extra':'Axolotl queued to SMTP',
            }),content_type='application/json')

    return HttpResponse(json.dumps({'ok':False,
                                    'extra':"I don't have any keys for this user yet!"}))

        

@session_pwd_wrapper
def receive(request, Key=None):
    FolderHash = emailclient.filedb.folder_from_msg_key(Key)
    if not FolderHash:
        return HttpResponse(json.dumps({'ok':False, 'status':'nonesuch'}),
                            content_type='application/json')
    Msg = FolderHash['mbx'].get(Key)
    # mark as 'S'een
    emailclient.filedb.flag(Key, addFlag='S')

    Passphrase = request.session.get('passphrase', None)

    # some dirty-assed multipart hackery.  yeh yeh yeh
    Payload = Msg.get_payload()
    if type(Payload) is ListType:
        Payload = Payload[0]

    MsgType = addressbook.utils.msg_type(Payload)

    if not MsgType: # pass it straight thru
        if type(Payload) is not StringType:
            Payload = Payload.get_payload()
            
        return HttpResponse(
            json.dumps({'ok':False,
                        'folder':FolderHash['pretty_name'],
                        'payload':Payload,
                        'rawdog':Msg.as_string(),
                        'msg_type':None,
                        'status':'',
                        'decrypt':Payload,
                        }), content_type='application/json')

    elif MsgType == 'PGP-MSG':
        Decrypt = addressbook.gpg.decrypt(str(Payload),
                                          passphrase=Passphrase)
        Payload = str(Decrypt)
        if Payload == '':
            Payload = Msg.get_payload()

        SigTime = None
        if Decrypt.sig_timestamp:
            SigTime = datetime.datetime.fromtimestamp(float(Decrypt.sig_timestamp)).isoformat()
    
        return HttpResponse(
            json.dumps({'ok':Decrypt.ok,
                        'folder':FolderHash['pretty_name'],
                        'payload':Payload,
                        'rawdog':Msg.as_string(),
                        'signed_at':SigTime,
                        'msg_type':MsgType,
                        'status':Decrypt.status,
                        'decrypt':Decrypt.data,
                        }), content_type='application/json')
    
    elif MsgType == 'AXO-MSG': # Axolotl

        Payload = None
        Ok = False
        Preferences = set_up_single_user()
        
        if ((request.POST.get('axo-failsafe', False) == 'true') and
            (addressbook.gpg.verify_symmetric(Passphrase))):
            try:
                Addr = addressbook.address.Address.objects.get(email__iexact=Msg['From'])
            except addressbook.address.Address.DoesNotExist:
                Payload = '* Failed to load Address for user %s *' % Msg['From']
                return HttpResponse(
                    json.dumps({'ok':Ok,
                                'msg_type':'FAIL',
                                'payload':Payload}))

            ratchet.conversation.Conversation.objects.init_for('ratchet')
            try:
                ratchet.conversation.Conversation.objects.decrypt_database(Passphrase)
                logger.debug('Ratchet database decrypted')
            except thirtythirty.exception.Target_Exists:
                pass
            
            try:
                Convo = ratchet.conversation.Conversation.objects.get(UniqueKey=Addr.fingerprint)
            except ratchet.conversation.Conversation.DoesNotExist:
                Payload = '* Failed to load Conversation for user %s *' % Addr.magic()
                return HttpResponse(
                    json.dumps({'ok':Ok,
                                'msg_type':'FAIL',
                                'payload':Payload}))
            Ok = True
            try:
                Payload = Convo.decrypt(Msg.as_string())
            except ratchet.exception.RatchetException:
                Payload = '* Decrypt failed: %s *' % Addr.magic()
                emailclient.filedb.discard(Key)
                return HttpResponse(
                    json.dumps({'ok':False,
                                'msg_type':'FAIL',
                                'payload':Payload}))
            emailclient.filedb.discard(Key)

            if Preferences.rx_symmetric_copy:
                M = emailclient.filedb.save_local(to=Msg['to'],
                                      ffrom=Msg['from'],
                                      date=Msg['date'],
                                      subject='[SYMMETRIC] %s' % Msg['subject'],
                                      body=Payload,
                                      passphrase=Passphrase,
                                      Folder='', # inbox
                                      )
                logger.debug('Made a symmetric copy: %s' % (M['extra']))
                                  
        
        return HttpResponse(
            json.dumps({'ok':Ok,
                        'folder':FolderHash['pretty_name'],
                        'payload':Payload,
                        'rawdog':Msg.as_string(),
                        'msg_type':MsgType,
                        'status':'',
                        'decrypt':Payload,
                        }), content_type='application/json')

    elif MsgType == 'AXO-HS':
        return HttpResponse(json.dumps({'ok':True,
                                        'msg_type':MsgType,
                                        'status':'procmail is borked'}),
                            content_type='application/json')

    else:
        return HttpResponse(json.dumps({'ok':False,
                                        'msg_type':MsgType,
                                        'status':"I don't even know what went wrong.  :/"}),
                            content_type='application/json')


@session_pwd_wrapper
def new_mail(request):
    return HttpResponse(
        json.dumps({'inbox':emailclient.filedb.new_mail_in_inbox()}),
        content_type='application/json')
    

@session_pwd_wrapper
def discard(request):
    ret = []
    for MK in request.POST.getlist('MK'):
        if emailclient.filedb.discard(MK):
            ret.append(MK)
    return HttpResponse(
        json.dumps(ret),
        content_type='application/json')


@session_pwd_wrapper
def move(request):
    ret = []
    destFolder = request.POST.get('destFolder')
    srcFolder = request.POST.get('srcFolder')
    returnType = request.POST.get('returnType')
    for MK in request.POST.getlist('MK'):
        if srcFolder == 'trash':
            emailclient.filedb.flag(MK, remFlag='T')
        if destFolder == 'trash':
            emailclient.filedb.flag(MK, addFlag='T')
        NewKey = emailclient.filedb.move(MK, folderName=destFolder)
        if NewKey: ret.append(NewKey)
    if returnType == 'message':
        # redirect rather than just return, so the URL is pretty
        return redirect('emailclient.view', Key=ret[0])
    elif returnType == 'folder':
        return redirect('emailclient.folder', name=srcFolder)
    else:
        return redirect('emailclient.inbox')


@session_pwd_wrapper
def flag(request):
    ret = []
    addFlag = request.POST.get('addFlag')
    remFlag = request.POST.get('remFlag')
    for MK in request.POST.getlist('MK'):
        FM = emailclient.filedb.flag(MK,
                         addFlag=addFlag,
                         remFlag=remFlag)
        if not FM['ok']:
            ret.append({'ok':False, 'MK':MK})
        else:
            if 'T' in addFlag:
                emailclient.filedb.move(MK, folderName='trash')
            ret.append({'ok':True, 'MK':MK, 'extra':FM['extra']})
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def create_folder(request):
    folderName = request.POST.get('destFolder')
    srcFolder = request.POST.get('srcFolder')
    Sanitized = emailclient.filedb.create_folder(folderName)['folderName']
    for MK in request.POST.getlist('MK'):
        emailclient.filedb.move(MK, folderName=Sanitized)
    return redirect('emailclient.folder', name=srcFolder)


@session_pwd_wrapper
def delete_folder(request):
    folderName = request.POST.get('folderName')
    return HttpResponse(json.dumps(emailclient.filedb.delete_folder(folderName)),
                        content_type='application/json')
