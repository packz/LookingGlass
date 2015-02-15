
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template import RequestContext, loader

import re
import json
import datetime

import addressbook
import ratchet
import smp
import thirtythirty

from thirtythirty.gpgauth import session_pwd_wrapper, set_up_single_user

import logging
logger = logging.getLogger(__name__)

KEY_EXPIRATION_WARNING = datetime.date.today() - datetime.timedelta(days=7)

Ratchet_Objects = ratchet.conversation.Conversation.objects
Ratchet_Objects.init_for('ratchet')

SMP_Objects = smp.models.SMP.objects
SMP_Objects.init_for('smp')


@session_pwd_wrapper
def home(request, Index=None, advanced=False):
    Preferences = set_up_single_user()
    if Preferences.show_advanced: advanced = True
    
    Addressbook = addressbook.address.Address.objects.filter(system_use=False)
    if Index:
        Addressbook = addressbook.address.Address.objects.filter(
            Q(nickname__startswith = Index) |\
            Q(covername__startswith = Index) |\
            Q(covername__contains = ' %s' % Index) # filter last name too
            ).filter(system_use=False)
        
    Indices = set([ X.magic()[0] for X in addressbook.address.Address.objects.all() ]) # set() uniques the results
    state_hash = {}
    for K,V in addressbook.address.Address.user_state_choices:
        state_hash[K] = V

    # see if we've had our covername accepted by the headend server...
    Headend_Ok = False
    Me = addressbook.utils.my_address()
    if Me.comment and Me.comment != 'accepted LUKS passphrase':
        Headend_Ok = True
        
    context = RequestContext(request, {'title':'Contacts',
                                       'nav':'Contacts',
                                       'bg_image':'the-stacks.jpg',
                                       'vitals':thirtythirty.utils.Vitals(request),
                                       'indices':sorted(Indices),
                                       'index':Index,
                                       'advanced':advanced,
                                       'friends':Addressbook,
                                       'headend_ok':Headend_Ok,
                                       'state_names':state_hash,
                                       })
    template = loader.get_template('addressbook.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def dossier(request, Fingerprint=None, advanced=False):
    Preferences = set_up_single_user()
    if Preferences.show_advanced: advanced = True    

    Vitalis = thirtythirty.utils.Vitals(request)

    state_hash = {}
    for K,V in addressbook.address.Address.user_state_choices:
        state_hash[K] = V
    try:
        Addr = addressbook.address.Address.objects.get(fingerprint=Fingerprint)
    except:
        return HttpResponse("""
        <script>
        window.location.href = '%s';
        </script>
        """ % reverse('addressbook'))
    req = {'K':Addr,
           'state_names':state_hash,
           'advanced':advanced,
           'key_expiration_warning':KEY_EXPIRATION_WARNING,
           'today':datetime.date.today(),
           'Verbose':{},
           }

    if req['K'].user_state == addressbook.address.Address.NOT_VETTED:
        req['Handshake_Title'] = 'Send Handshake'
    else:
        req['Handshake_Title'] = 'Resend Handshake'

    PP = None
    SMP_Step = 0

    if 'passphrase' in request.session:
        PP = request.session['passphrase']

        try: SMP_Objects.decrypt_database(PP)
        except thirtythirty.exception.Target_Exists: pass
        try: Ratchet_Objects.decrypt_database(PP)
        except thirtythirty.exception.Target_Exists: pass

        MyRatchet = ratchet.conversation.Conversation.objects.filter(UniqueKey=Fingerprint).first()
        if MyRatchet:
            req['my_fingerprint'] = MyRatchet.my_fingerprint()
            req['their_fingerprint'] = MyRatchet.their_fingerprint()
        MySMP = smp.models.SMP.objects.filter(UniqueKey=Fingerprint).first()
        Q = None
        try: Q = addressbook.queue.Queue.objects.filter(address__fingerprint=Fingerprint).latest()
        except: pass
        if Q:
            req['previous_smp_step'] = Q.body
        if MySMP:
            SMP_Step = MySMP.step
            req['Question'] = MySMP.Question

    
    for K,V in addressbook.address.Address.Verbose.iteritems():
        BR = re.sub('BUG_REPORT_URL', reverse('bug_report'), V)
        CU = re.sub('CHAT_URL', 'https://%s:16667?nick=%s' % ( Vitalis['server_addr'], 
                                                               Vitalis['ircname']), BR)
        ADV = re.sub('RELOAD_ADVANCED', '%s#%s' % (
                reverse('addressbook.advanced'),
                Fingerprint,
                ), CU)
        SMP = re.sub('SMP_STEP', str(SMP_Step), ADV)
        req['Verbose'][K] = SMP
        
    context = RequestContext(request, req)
    template = loader.get_template('dossier.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def search(request, Q=None):
    return HttpResponse(json.dumps(addressbook.covername.search(
        cleartext=request.POST.get('clear'),
        encoded=request.POST.get('primary'),
        )),
        content_type='application/json')


@session_pwd_wrapper
def nickname(request):
    """
    SANITIZE and save nick
    """
    FP = request.POST.get('fingerprint')
    Nick = re.sub('^ ', '_', request.POST.get('new-nick').rstrip())
    Nick = re.sub('[^_ a-zA-Z0-9]', '', Nick)
    A = addressbook.address.Address.objects.get(fingerprint=FP)
    A.nickname = Nick
    A.save()
    return HttpResponse(json.dumps({'ok':True,
                                    'fp':A.fingerprint,
                                    'nick':A.nickname,}),
                        content_type='application/json')


@session_pwd_wrapper
def delete(request):
    FP = request.POST.get('FP')
    ret = {'ok':False, 'FP':FP}
    if ((FP) and ('passphrase' in request.session)):
        PP = request.session['passphrase']
        try: SMP_Objects.decrypt_database(PP)
        except thirtythirty.exception.Target_Exists: pass
        try: Ratchet_Objects.decrypt_database(PP)
        except thirtythirty.exception.Target_Exists: pass
        
        try:
            A = addressbook.address.Address.objects.get(
                fingerprint=FP,
                is_me=False,
                )
        except addressbook.address.Address.DoesNotExist:
            return HttpResponse(json.dumps({'ok':False,
                                            'FP':FP}),
                                content_type='application/json')
            
        Addr = addressbook.address.Address.objects.delete_key(fingerprint=FP)
        Axo = ratchet.conversation.Conversation.objects.filter(UniqueKey=FP).delete()
        Smp = smp.models.SMP.objects.filter(UniqueKey=FP).delete()
        logger.debug('user %s deleted' % A)
        ret = {'ok':True,
               'addr':Addr,
               'axo':Axo,
               'smp':Smp,
               'FP':FP}
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def key_import(request):
    PK = request.POST.get('PK')
    ret = {'ok':False, 'PK':[]}
    if PK: 
        for K in addressbook.address.Address.objects.import_key(keydata=PK):
            A = addressbook.address.Address.objects.get(fingerprint=K)
            logger.debug("Let's see if %s speaks Axolotl..." % A.email)
            addressbook.queue.Queue.objects.create(
                address = A,
                direction = addressbook.queue.Queue.TX,
                message_type = addressbook.queue.Queue.AXOLOTL,
                )
            ret['PK'].append(K)
            ret['ok'] = True
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def add_contact(request):
    Covername = request.POST.get('covername')
    ret = {'ok':False}
    if Covername:
        A = addressbook.address.Address.objects.add_by_covername(covername=Covername)
        if A:
            ret = {'ok':True, 'FP':A.fingerprint}
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def push_to_queue(request):
    Fingerprint = request.POST.get('fingerprint', None)
    Question = request.POST.get('question', None)
    Secret = request.POST.get('secret', None)
    ret = {'ok':False, 'fingerprint':Fingerprint}

    if request.POST.get('passphrase', None):
        request.session['passphrase'] = request.POST.get('passphrase')
    if 'passphrase' in request.session:
        PP = request.session['passphrase']
    
    # sanitize and sanity check
    try:
        Who = addressbook.address.Address\
              .objects.get(fingerprint=Fingerprint)
    except:
        ret['reason'] = 'Dunno.'
        return HttpResponse(json.dumps(ret),
                            content_type='application/json')
    if not PP:
        ret['reason'] = 'No passphrase'
        return HttpResponse(json.dumps(ret),
                            content_type='application/json')
    if not addressbook.gpg.verify_symmetric(PP):
        ret['reason'] = 'You got the wrong passphrase, dingus.'
        return HttpResponse(json.dumps(ret),
                            content_type='application/json')
    if Who.user_state > addressbook.address.Address.VETTING:
        ret['reason'] = 'I already know them.'
        return HttpResponse(json.dumps(ret),
                            content_type='application/json')

    try: SMP_Objects.decrypt_database(PP)
    except thirtythirty.exception.Target_Exists: pass
    try: Ratchet_Objects.decrypt_database(PP)
    except thirtythirty.exception.Target_Exists: pass

    logger.debug('Resend request - %s is in state `%s`' % (Who.email, Who.get_user_state_display()))

    # The main functions - initiating Axolotl and SMP protocols
    if Who.user_state == addressbook.address.Address.KNOWN:
        # Axolotl Handshake
        logger.debug('Queuing an Axolotl SYN to %s' % Who.email)
        Entry = addressbook.queue.Queue.objects.create(
            address = Who,
            direction = addressbook.queue.Queue.TX,
            message_type = addressbook.queue.Queue.AXOLOTL,
            )
        
    elif Who.user_state == addressbook.address.Address.NOT_VETTED:
        # SMP authentication
        try:
            Convo = ratchet.conversation.Conversation.objects.get(
                UniqueKey = Who.fingerprint
                )
        except ratchet.conversation.Conversation.DoesNotExist:
            ret['reason'] = "Axolotl failure - demoting %s to pre-Axolotl state" % Who.email
            Who.user_state = addressbook.address.Address.KNOWN
            Who.save()
            return HttpResponse(json.dumps(ret),
                                content_type='application/json')

            
        S = smp.models.SMP.objects.filter(UniqueKey=Who.fingerprint)
        if not (Question and Secret):
            ret['reason'] = 'Missing field.'
            ret['question'] = Question
            ret['secret'] = Secret
            return HttpResponse(json.dumps(ret),
                                content_type='application/json')
        if len(S) == 0:
            S = smp.models.SMP.objects.hash_secret(
                Conversation = Convo,
                passphrase = PP,
                question = Question,
                secret = Secret)
            Who.user_state = addressbook.address.Address.VETTING
            Who.save()
            if S.IAmAlice:
                Body = S.advance_step()
                logger.debug('I am Alice, initiating SMP')
            else:
                # a "please Alice at me" packet...
                Body = smp.models.SMPStep(Question=Question).dumps()
                S.step = 1
                S.save()
                logger.debug('I am Bob, querying Alice for initial step')
            if addressbook.queue.Queue\
                   .objects.filter(address=Who,
                                   direction=addressbook.queue.Queue.TX
                                   ).count() == 0:
                addressbook.queue.Queue.objects.create(
                    address = Who,
                    body = Convo.encrypt(plaintext=Body),
                    direction = addressbook.queue.Queue.TX,
                    message_type = addressbook.queue.Queue.SOCIALISM,
                    )
                logger.debug('Queued SMP step to %s' % Who.email)
            else:
                logger.debug('SMP step already queued to %s' % Who.email)
        elif len(S) == 1:
            S[0].create_secret(secret=Secret)
            Who.user_state = addressbook.address.Address.VETTING
            Who.save()

    elif Who.user_state == addressbook.address.Address.VETTING:
        Resend = addressbook.queue.Queue.objects.filter(
            address=Who,
            direction=addressbook.queue.Queue.SMP_Replay).order_by('-modified').first()
        if Resend:
            logger.debug('Found a saved state - resendering')
            Resend.direction = addressbook.queue.Queue.TX
            Resend.save()
        else:
            logger.critical('I have no saved state for %s and so suck and fail' % Who.email)
            Who.smp_failures = models.F('smp_failures') + 1
            Who.save()
            Queue.objects.filter(address=Who,
                                 direction=addressbook.queue.Queue.SMP_Replay,
                                 ).delete()
            S.delete()

    # initiate the beginnening
    ret['ok'] = True
    QR = addressbook.queue.QRunner()
    QR.Run(passphrase=PP)
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')
