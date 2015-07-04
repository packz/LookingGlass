
from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.template import RequestContext, loader

from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse

from os.path import exists
from random import choice
import datetime
import json
import subprocess
import os

import django_rq

import addressbook
import emailclient
import thirtythirty
import queue
import ratchet
import smp

import thirtythirty.settings as TTS
from thirtythirty.gpgauth import session_pwd_wrapper, set_up_single_user
from thirtythirty.updater import Available, Validate, Unpack, Cleanup, ChangeLog

import logging
logger = logging.getLogger(__name__)

def too_many_logins():
    Minutes = 10
    Logins  = 10

    Time_Lock = datetime.datetime.now() - \
                datetime.timedelta(minutes=Minutes)

    thirtythirty.models.LoginRateLimiter.objects.filter(
        issued_at__lte=Time_Lock
        ).delete()

    if thirtythirty.models.LoginRateLimiter.objects.filter(
        issued_at__lte=datetime.datetime.now()
        ).filter(
        issued_at__gte=Time_Lock
        ).filter(
        redeemed = False
        ).count() > Logins:
        return True
    else:
        return False


def password_prompt(request, warno=None, Next=None):    
    if not thirtythirty.hdd.drives_exist():
        return redirect('setup.index')
    
    if too_many_logins():
        do_lockdown(request)
        return HttpResponse("""
        You are doing that too much.  Now you must wait.
        """)
    
    C = thirtythirty.models.LoginRateLimiter.objects.token()
    ret = {
        'title':'Unlock drive',
        'bg_image':'vault.jpg',
        'bits':TTS.HASHCASH['BITS']['WEBUI'],
        'challenge':C.challenge,
        'submit_to':reverse('drive_unlock'),
        'next':Next,
        'placeholder':'Drive passphrase',
        'warning_text':warno,
        }

    if thirtythirty.hdd.drives_are_unlocked():
        ret['title'] = 'Log in'
        ret['bg_image'] = 'yard.jpg'
        ret['submit_to'] = reverse('session_unlock')
        ret['placeholder'] = 'Email passphrase'
    
    context = RequestContext(request, ret)
    template = loader.get_template('login.dtl')
    return HttpResponse(template.render(context))


def are_drives_unlocked(request):
    """
    examines the queued unlocker job
    """            
    Unlock_Job_ID = request.session['unlock_job']    
    Queue = django_rq.get_queue()
    Unlock_Job = Queue.fetch_job(Unlock_Job_ID)
    logger.debug('Got unlocker job: %s' % Unlock_Job.id)
    
    Percent = 0
    Why_yes_they_are = 'NO'
    if Unlock_Job.result:
        Why_yes_they_are = 'YES'
        Percent = 100
    elif Unlock_Job.result is None:
        Why_yes_they_are = 'RUNNING'
        for V in thirtythirty.hdd.Volumes():
            if V.is_mounted():
                Percent += (100.00 / len(TTS.LUKS['mounts']))
    return HttpResponse(json.dumps({'ok':Why_yes_they_are,
                                    'percent':Percent}),
                        content_type='application/json')


def drive_unlock(request):
    if too_many_logins():
        do_lockdown(request)
        return HttpResponse("""
        You are doing that too much.  Now you must wait.
        """)

    if thirtythirty.hdd.drives_are_unlocked():
        return redirect('accounts.login')
    
    HCM = request.POST.get('HCM', None)
    if not HCM:
        return redirect('accounts.login')
    Challenge = HCM.split(':')[3]
    try:
        LRM = thirtythirty.models.LoginRateLimiter.objects.get(
            challenge=Challenge)
    except thirtythirty.models.LoginRateLimiter.DoesNotExist:
        return password_prompt(request,
                               warno='Waited too long - please try again')
    if not LRM.verify(stamp=HCM, bits=TTS.HASHCASH['BITS']['WEBUI']):
        return password_prompt(request,
                               warno='Wrong response - please try again')

    logger.debug("Hashcash checks out - let's try to fire the drives up")
    
    # we'll be inspecting the job state dynamically
    Pwd = request.POST.get('password', None)
    Unlocker = queue.hdd.Unlock.delay(Pwd)
    request.session['unlock_job'] = Unlocker.id
    
    return HttpResponse(json.dumps({'ok':True}),
                        content_type='application/json')
    

def session_unlock(request):
    if too_many_logins():
        do_lockdown(request)
        return HttpResponse("""
        You are doing that too much.  Now you must wait.
        """)

    HCM = request.POST.get('HCM', None)
    Challenge = HCM.split(':')[3]
    try:
        LRM = thirtythirty.models.LoginRateLimiter.objects.get(
            challenge=Challenge)
    except thirtythirty.models.LoginRateLimiter.DoesNotExist:
        return password_prompt(request,
                               warno='Waited too long - please try again')
    if not LRM.verify(stamp=HCM, bits=TTS.HASHCASH['BITS']['WEBUI']):
        return password_prompt(request,
                               warno='Wrong response - please try again')

    logger.debug('Hashcash verifies, now checking passphrase')
    
    P = request.POST.get('password')

    ooser = authenticate(password=P)
    if ooser:
        request.session['passphrase'] = P
        login(request, ooser)
        logger.debug('little insurgent, little insurgent, let me in!')
        return redirect('emailclient.inbox')
    
    return password_prompt(request,
                           warno='Wrong passphrase')


def index(request, Next=None):
    if not thirtythirty.hdd.drives_exist():
        return redirect('setup.index')
    elif request.session.get('passphrase', None):
        return redirect('emailclient.inbox')
    else:
        return redirect('accounts.login')


@session_pwd_wrapper
def settings(request, advanced=False):
    Vitals = thirtythirty.utils.Vitals(request)
    Update_Version = '[No update available]'
    Update_Warn = ''
    Availed = Available()
    if Availed and Validate(Availed['filename'], Debug=False):
        Update_Version = 'Version %s now available!' % Availed['version']
        Update_Warn = 'Back up your settings before update!'
    Preferences = set_up_single_user()
    if Preferences.show_advanced: advanced = True
    
    Info_Panel = [
        {'desc':'Version',
         'name':'LGVersion',
         'value':TTS.LOOKINGGLASS_VERSION_STRING},
        {'desc':'Covername',
         'name':'covername',
         'value':Vitals['covername'],
         },
        {'desc':'Email address',
         'name':'email',
         'value':'%s' % Vitals['email'],
         },
        {'desc':'GPG Fingerprint',
         'name':'gpg',
         'value':Vitals['gpg_fp'],
         'help':'Back-up authentication method for out-of-band use.',
         },
        {'desc':'Bitcoin master public key',
         'name':'btc_mpk',
         'value':Vitals['btc_mpk'],
         'help':'Not yet implemented.',
         },
        {'desc':'WebUI SSL certificate',
         'name':'SSLCert',
         'value':'Download <a href="https://%s/docs/ca.cert.pem">here</a>.' % Vitals['server_addr'],
         },
        ]
    
    Settings = [
        {'title':'Passphrase reset',
         'id':'PassphraseR',
         'advanced':True,
         'desc':"You can change one, or both.",
         'controls':[
             {'desc':'Old drive passphrase',
              'type':'password', 'id':'prev-dpassphrase',
              'width':8,
              },
             {'desc':'New drive passphrase',
              'type':'password', 'id':'new-dpassphrase-1',
              'width':8,
              },
             {'desc':'Confirm drive passphrase',
              'type':'password', 'id':'new-dpassphrase-2',
              'width':8,
              },
             {'desc':'Old email passphrase',
              'type':'password', 'id':'prev-epassphrase',
              'width':8,
              },
             {'desc':'New email passphrase',
              'type':'password', 'id':'new-epassphrase-1',
              'width':8,
              },
             {'desc':'Confirm email passphrase',
              'type':'password', 'id':'new-epassphrase-2',
              'width':8,
              },
             ]},

        {'title':'IP Address settings',
         'id':'IP',
         'advanced':True,
         'controls':[
             {'desc':'Dynamic vs Static IP',
              'type':'select', 'id':'ip-address-mode',
              'choices':Preferences.ip_types,
              'option_checked':Preferences.ip_address_type,
              },
             {'desc':'Static IP address',
              'type':'text', 'id':'static-ip',
              'value':thirtythirty.utils.IP_Info('Address'),
              'disabled':Preferences.ip_address_type == Preferences.DYNAMIC_IP,
              },
             {'desc':'Netmask',
              'type':'text', 'id':'netmask',
              'value':thirtythirty.utils.IP_Info('Netmask'),
              'disabled':Preferences.ip_address_type == Preferences.DYNAMIC_IP,
              },
             {'desc':'Gateway IP address',
              'type':'text', 'id':'gateway-ip',
              'value':thirtythirty.utils.IP_Info('Gateway'),
              'disabled':Preferences.ip_address_type == Preferences.DYNAMIC_IP,
              },
             {'desc':'Accept', 'type':'button',
              'id':'static-ip-send', 'value':'Submit',
              'disabled':Preferences.ip_address_type == Preferences.DYNAMIC_IP,
              },
             ]},

        {'title':'Dead man switch',
         'id':'Dead-man',
         'advanced':True,
         'controls':[
             {'desc':'Dead man switch',
              'disabled':True, 'type':'checkbox',
              'help':'Let interested people know I am alive',
              },
             {'desc':'Timeout', 'id':'dms-timeout',
              'disabled':True, 'type':'text',
              'placeholder':'three days',
              },
             ]},

        {'title':'Radio interface',
         'id':'Radio',
         'advanced':True,
         'controls':[
             {'desc':'Enable mesh radio interface',
              'disabled':True, 'type':'checkbox',
              },
             ]},

        {'title':'Process management',
         'id':'Process',
         'controls':[
             {'desc':'NTP time sync',
              'type':'button',
              'class':'kick',
              'id':'ntp-sync',
              },
             {'desc':'Flush mail queue',
              'type':'button',
              'class':'kick',
              'id':'postqueue-flush',
              },
             {'desc':'Restart mail subsystem',
              'type':'button',
              'class':'kick',
              'id':'postfix-restart',
              },
             {'desc':'Restart Tor',
              'type':'button',
              'class':'kick',
              'id':'tor-restart',
              },
             {'desc':'Restart WebUI',
              'type':'button',
              'class':'kick',
              'id':'django-restart',
              },
             {'desc':'Force queue run',
              'type':'button',
              'class':'kick',
              'id':'qmanage-run',
              },
             {'desc':'Queue kicker',
              'type':'button',
              'class':'kick',
              'id':'rqworker',
              },
             ]},

        {'title':'Updates',
         'id':'Updates',
         'controls':[
             {'desc':'Update',
              'class':'bg-info',
              'type':'button', 'id':'update',
              'disabled':(not Available()),
              'help':Update_Version,
              'warn':Update_Warn,
              },
             {'desc':'Force update',
              'type':'button', 'id':'force-update',
              'warn':'No mercy.  No resistance.  Open up.',
              'advanced':True,
              },
             {'desc':'Drag upgrade file here to upload',
              'type':'file', 'id':'upgrade-file',
              'filetype':'upgrade',
              'action':reverse('settings.file_upload'),
              },
             ]},

        {'title':'Backup / Restore',
         'id':'Backups',
         'controls':[
             {'desc':'Backup',
              'type':'button', 'id':'sysbackup',
              'href':reverse('settings.backup'),
              },
             {'desc':'Restore',
              'type':'button', 'id':'sysrestore',
              'disabled':True,
              },
             {'desc':'Drag restore file here to upload',
              'type':'file', 'id':'restore-file',
              'filetype':'backup',
              'action':reverse('settings.file_upload'),
              },
             {'desc':'Recover database',
              'type':'button', 'id':'database-recover',
              'help':'If a power outage or some other badness occurred, you may need this',
              'warn':"You may lose messages and need to resynchronize with your contacts - don't click this idly",
              },
             ]},

        {'title':'System administration',
         'id':'Sysadmin',
         'controls':[
             {'desc':'Report bug',
              'type':'button', 'href':reverse('bug_report'),
             },
             {'desc':'Respond to status queries',
              'type':'checkbox', 'id':'allow-status',
              'help':'Respond to keyserver poll for system status',
              'checked':False, 'disabled':True,
             },
             {'desc':'Local wizard login',
              'type':'button', 'href':'https://%s:4200' % Vitals['server_addr'],
              'target':'_blank',
              'help':'Emergency login for nearby wizards',
              },
             {'desc':'Reboot',
              'type':'button', 'id':'reboot',
              'help':'Reboots, locks drives',
              },              
             {'desc':'Reset to defaults',
              'type':'button', 'id':'reset-to-defaults',
              'warn':'NUKES EVERYTHING.',
              },
             ]},

        {'title':'Passphrase convenience',
         'id':'PassphraseC',
         'advanced':True,
         'controls':[
             {'desc':'USB key token',
              'type':'checkbox', 'id':'usb-token',
              'help':'Use USB flash drive as encryption key',
              'disabled':True,
              },
             {'desc':'Passphrase cache',
              'type':'checkbox', 'id':'pp-cache-on',
              'help':'Allows authentication tasks to proceed more quickly',
              'warn':'Increaseses your window of vulnerability',
              'checked':Preferences.passphrase_cache,
              },
             {'desc':'Passphrase cache cleared:',
              'type':'select', 'id':'pp-cache-timeout',
              'choices':thirtythirty.models.preferences.passphrase_cache_timeouts,
              'option_checked':Preferences.passphrase_cache_time,
              }
             ]},
        
        {'title':'Blatantly insecure niceties',
         'id':'xBlatantly',
         'advanced':True,
         'controls':[
             {'desc':'Keep a copy of sent messages',
              'type':'checkbox', 'id':'tx-symmetric-on',
              'checked':Preferences.tx_symmetric_copy,
             },
             {'desc':'Keep a copy of read-once messages',
              'type':'checkbox', 'id':'rx-symmetric-on',
              'checked':Preferences.rx_symmetric_copy,
             },
             {'desc':'Local search',
              'type':'checkbox', 'id':'search-on',
              'disabled':True,
              },
             ]},

        {'title':'Darknet mode',
         'id':'Darknet',
         'advanced':True,
         'controls':[
             {'desc':'Darknet mode',
              'type':'checkbox', 'id':'darknet-on',
              'help':'Email whitelisting',
              'disabled':True,
              },
             {'desc':'Darknet key',
              'type':'text', 'id':'darknet-key',
              'placeholder':'Shared secret',
              'disabled':True,
              },
             ]},

        {'title':'Remote access',
         'id':'Remote',
         'advanced':True,
         'controls':[
             {'desc':'Remote user access',
              'type':'checkbox', 'id':'remote-user-on',
              'disabled':True,
              'help':'Provides experimental remote Tor access',
              },
             {'desc':'Allow remote assist',
              'type':'checkbox', 'id':'remote-admin-on',
              'warn':'Allows complete remote control of device',
              'disabled':True,
              },
             ]},

        {'title':'System logs',
         'id':'Logs',
         'viewport':'log-view',
         'view_ro':True,
         'advanced':True,
         'controls':[
             {'desc':'Mail log',
              'type':'link', 'id':'get-mail-log',
             },
             {'desc':'Mail queue',
              'type':'link', 'id':'get-mail-queue',
              },
             {'desc':'Recent login history',
              'type':'link', 'id':'get-user-log',
             },
             {'desc':'Web frontend',
              'type':'link', 'id':'get-web-log',
              },
             ]},

        {'title':'Mail filters',
         'id':'MailFilter',
         'viewport':'mail-filter',
         'view_ro':False,
         'advanced':True,
         'controls':[
             {'desc':'Update',
              'type':'link', 'id':'update-filter',
              },
             ]},

        {'title':'Mailing lists',
         'id':'Mailman',
         'advanced':True,
         'controls':[
             {'desc':'Run encrypted mail list',
              'id':'axo-mailman',
              'type':'checkbox', 'disabled':True,
              }
             ]},

        # https://en.wikipedia.org/wiki/Cypherpunk_anonymous_remailer
        {'title':'Anonymous remailing',
         'id':'AnonymousRemail',
         'advanced':True,
         'controls':[
             {'desc':'Provide remailing services to other users',
              'type':'checkbox', 'id':'cypherpunk-relay-on',
              'disabled':True,
              },
             {'desc':'Use remailing for outbound email',
              'type':'checkbox', 'id':'cypherpunk-outbound-on',
              'disabled':True,
              },
             {'desc':'Enable traffic analysis countermeasures',
              'type':'checkbox', 'id':'ta-counter-on',
              'disabled':True,
              },
             ]},

        {'title':'WooOOOooOOo folders',
         'id':'xAdminFolders',
         'advanced':True,
         'controls':[
             {'desc':'Administrator inbox',
              'type':'link', 'href':reverse('emailclient.folder', kwargs={'name':'admin'}),
              'badge':emailclient.filedb.message_count('admin'),
              },
             {'desc':'Trash',
              'type':'link', 'href':reverse('emailclient.folder', kwargs={'name':'trash'}),
              'badge':emailclient.filedb.message_count('trash'),
              },
             ]},

        {'title':'Double dog advanced',
         'id':'zAdvanced',
         'controls':[
             {'desc':'Barf forth apocalyptica',
              'type':'link', 'href':reverse('advanced_settings'),
              },
             {'desc':'Always show advanced controls',
              'type':'checkbox', 'id':'advanced-always-on',
              'checked':Preferences.show_advanced,
              'advanced':True,
              },
             ]},
        
        ]
    
    context = RequestContext(request, {
        'title':'Settings',
        'nav':'Settings',
        'bg_image':'dash.jpg',
        'vital_summary':Info_Panel,
        'vitals':Vitals,
        'mounts':thirtythirty.hdd.Volumes(),
        'services':thirtythirty.utils.query_daemon_states(),
        'advanced':advanced,
        'setting_list':Settings,
        })
    template = loader.get_template('settings.dtl')
    return HttpResponse(template.render(context))


@session_pwd_wrapper
def kick(request, process=None):
    """
    note the initial slash - due to parsing of RE in url.py
    """
    process = process[1:]
    if process == 'postqueue-flush':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/usr/sbin/postqueue', '-f'])
        return HttpResponse('postqueue')
    elif process == 'postfix-restart':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/usr/bin/make', '--directory', '/etc/postfix', 'reload'])
        return HttpResponse('postfix')
    elif process == 'tor-restart':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/etc/init.d/tor', 'restart'])
        return HttpResponse('tor')
    elif process == 'django-restart':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/bin/systemctl', 'restart', 'gunicorn'])
        return HttpResponse('django')
    elif process == 'qmanage-run':
        QR = addressbook.queue.QRunner()
        QR.Run(passphrase=request.session.get('passphrase', None))
        return HttpResponse('qmanage')
    elif process == 'ntp-sync':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/lib/systemd/ntp-bootstrap'])
        return HttpResponse('ntp-bootstrap')
    elif process == 'rqworker':
        subprocess.call(['/usr/bin/sudo', '-u', 'root',
                         '/bin/systemctl', 'restart', 'rqworker'])
        return HttpResponse('ntp-bootstrap')
    else:
        return HttpResponse('no')

@session_pwd_wrapper
def backup(request):
    """
    Wrap up contact list, hidden service private key, and GPG private key.
    Encrypt symmetrically.
    Dump.
    """
    Passphrase = request.session.get('passphrase', None)
    if ((not Passphrase) or (not addressbook.gpg.verify_symmetric(Passphrase))):
        return HttpResponse('I need a passphrase.  :(')
    Backup = []
    for A in addressbook.address.Address.objects.filter(system_use=False):
        Backup.append({'covername':A.covername,
                       'email':A.email,
                       'fingerprint':A.fingerprint,
                       'nickname':A.nickname,
                       'is_me':A.is_me,
                       'type':'contact',
                       })
    Backup.append({'type':'hs_prv',
                   'key':subprocess.check_output(['/usr/bin/sudo', '-u', 'root',
                                                  '/bin/cat',
                                                  '/var/lib/tor/hidden_service/private_key'])})
    Backup.append({'type':'gpg_prv',
                   'key':subprocess.check_output(['/usr/bin/gpg',
                                                  '--armor',
                                                  '--export-secret-keys'])})
    Zip = addressbook.gpg.symmetric(msg=json.dumps(Backup),
                                    passphrase=Passphrase,
                                    armor=True)
    return HttpResponse(Zip,
                        content_type='plain/text')


@session_pwd_wrapper
def file_upload(request):
    if not request.FILES:
        return HttpResponseBadRequest(json.dumps({'error':'No file uploaded'}),
                                    content_type='application/json')
    if request.POST.get('backup'):
        logger.debug('got a backup file')
    elif request.POST.get('upgrade'):
        logger.debug('got an upgrade file')
    return HttpResponse(json.dumps({'success':'oh boy'}),
                content_type='application/json')


@session_pwd_wrapper
def restore(request):
    Passphrase = request.session.get('passphrase', None)
    if ((not Passphrase) or (not addressbook.gpg.verify_symmetric(Passphrase))):
        return HttpResponse('I need a passphrase.  :(')
    if not request.FILES.has_key('backupfile'):
        return HttpResponse('no file')
    JSON = str(addressbook.gpg.decrypt(msg=request.FILES['backupfile'].read(),
                                       passphrase=Passphrase))
    try:
        Backup = json.loads(JSON)
    except:
        return HttpResponse('bad JSON',
                            content_type='plain/text')
    logger.debug('Decrypt OK, JSON OK, here we go...')
    logger.debug('Flush queue')
    addressbook.queue.Queue.all().delete()
    for Entry in Backup:
        if not Entry.has_key('type'):
            logger.warning('Dropped: %s' % Entry)
            continue
        if Entry['type'] == 'contact':
            if not Entry['is_me']:
                A = addressbook.address.Address.objects.add_by_fingerprint(Entry['fingerprint'])
                for X in ['covername', 'nickname']:
                    if Entry[X]:
                        setattr(A, X, Entry[X])
                A.save()
        elif Entry['type'] == 'hs_prv':
            logger.debug('Restoring tor private key')
            PRVK = '/var/cache/LookingGlass/private_key'
            pkfh = file(PRVK, 'w')
            pkfh.write(Entry['key'])
            pkfh.close()
            subprocess.call(['/usr/bin/sudo', '-u', 'root',
                             '/bin/cp',
                             PRVK,
                             '/var/lib/tor/hidden_service/private_key'])
            os.unlink(PRVK)
            subprocess.call(['/usr/bin/sudo', '-u', 'root',
                             '/etc/init.d/tor',
                             'reload'])
        elif Entry['type'] == 'gpg_prv':
            logger.debug('Delete present GPG private key')
            Old_Boy = addressbook.utils.my_address()
            addressbook.GPG.delete_keys(Old_Boy.fingerprint, True) # secret
            addressbook.GPG.delete_keys(Old_Boy.fingerprint) # public
            Old_Boy.delete()
            logger.debug('Restore GPG private key')
            PRVK = '/var/cache/LookingGlass/secret.gpg'
            pkfh = file(PRVK, 'w')
            pkfh.write(Entry['key'])
            pkfh.close()
            logger.debug(subprocess.check_output(['/usr/bin/gpg',
                                                  '--import',
                                                  PRVK]))
            os.unlink(PRVK)
            addressbook.address.Address.objects.rebuild_addressbook(True)
    return HttpResponse('yes',
                        content_type='plain/text')

@session_pwd_wrapper
def about(request):
    template = loader.get_template('about.dtl')
    Vitals = thirtythirty.utils.Vitals(request)
    CHAT_URL = 'https://%s:16667?nick=%s' % (Vitals['server_addr'], Vitals['ircname'])
    CTD = {
        'title':"What it's about.",
        'nav':'About',
        'bg_image':choice([
            'aldrin.jpg',
            'arcadia_ego.jpg',
            'castle.jpg',
            'fishing.jpg',
            'highway.jpg',
            'island.jpg',
            'lambda.jpg',
            'office.jpg',
            'pier.jpg',
            'squeeze.jpg',
            ]),
        'freedom_image':'logo.png',
        'faq':[
            {'q':'WHAT IS GOING ON?', 'a':"You're looking through LookingGlass, an encrypted mail system."},
            {'q':'What can I do with it?',
             'a':"Send email that will be as compartmentalized and secure as possible."},
            {'q':'Are there any best practices I should be aware of?',
             'a':"<a href='#cBCP' id='show-best-practices'>Yes.</a>"},
            {'q':"Where can I get help?",
             'a':"Please join the <a target='_blank' href='%s'><span class='glyphicon glyphicon-comment text-info'></span><span class='text-primary'> Chat</span></a> for live help.  They'll probably be able to steer you in the right direction." % (CHAT_URL)},
            {'q':'MOAR BUZZWORDS.  MOAR COMPREHENZIF.',
             'a':"You're looking at LookingGlass, an encrypted, forward secure, peer-to-peer, anonymous email system."},
            {'q':'Encrypted?',
             'a':"Yep.  All of it.  LookingGlass doesn't send unencrypted messages.  Additionally, if you pull power (or click <a class='bg-danger' id='whoa-there'><span class='glyphicon glyphicon-fire text-danger'></span> Lockdown</a>) the drive encryption should make sure your information remains secret."},
            {'q':"But I already use encryption - why should I use this?",
             'a':"This probably isn't for you, then - but you may be interested in forward security, or want more of your contacts to get to the same pinnacle of security excellence you're at."},
            {'q':"What does 'forward secure' even mean?",
             'a':"""That once you and your contact have negotiated a key pair, all messages become readable only once."""},
            {'q':"That's ridiculous - I can print these emails out and the sender has no control over that and would never know.",
             'a':"There really isn't much to be done about that.  Used as intended, however, we go to great lengths to keep you and your cabal safe."},
            {'q':"What do you mean by peer-to-peer?",
             'a':"""Every LookingGlass user runs their own mail server, and sends email directly to other users.  There is no single point of failure or compromise.  Well, besides yourself."""},
            {'q':'How can this be anonymous if I am running a server?',
             'a':"""Because you are running what is called a <a href='https://en.wikipedia.org/wiki/Tor_%28anonymity_network%29#Hidden_services'>hidden service</a> on the Tor anonymity network.  <a href='https://www.torproject.org/docs/hidden-services.html.en'>Here's</a> an excellent, if technical, graphic.  Some people refer to this as a 'darknet.'"""},
            {'q':"What's with all the disabled links?",
             'a':"Those are proposed future features that haven't been coded yet.  If they excite you, speaking up or donating would be tubular."},
            {'q':"Why are my email subjects saying <span class='bg-info'>[SYMMETRIC]</span> now?",
             'a':"Because you selected to <a href='%s#cGape'>keep a local copy of read-once messages</a>, which re-encrypts them.  This is <span class='bg-danger'>NOT SECURE OR RECOMMENDED</span>." % reverse('advanced_settings')},
            {'q':'Does LookingGlass make my web browsing anonymous?',
             'a':'Presently, no - but that is a possible future feature.'},
            {'q':'Can I view the source?',
             'a':'Sure - you can be a wizard and log into the box, or you could go look at more out-of-sync code at <a href="https://github.com/last-box/LookingGlass">GitHub</a>.'},
            {'q':'How do I report a bug?',
             'a':"Oh boy, already?  There is a <a href='%s'>form</a>." % reverse('bug_report')},
            ],

        
        'best':[
            "Use your browser in <i>incognito</i> or <i>private browsing</i> mode.  This keeps incriminating residual data on your computer to a minimum.",
            "Authenticate your contacts with a <a href='%s'>shared secret</a> only the two of you would know." % reverse('addressbook'),
            "Try not to have the times that your LookingGlass server is connected to the Internet correlate too much with the times you actually use it.  This will make you a bit more difficult to identify.  LookingGlass is designed to be online all the time, and that is recommended.",
            "Do not exchange your <b>covername</b> over an insecure channel.  This undermines the traffic analysis features of LookingGlass.",
            ],

        
        'thanks':[
            {'indx':'a', 'c':"<a target='_blank' href='https://github.com/rxcomm/pyaxo'>David Andersen</a>"},
            {'indx':'g', 'c':"<a target='_blank' href='https://otr.cypherpunks.ca/news.php'>Ian Goldberg</a>"},
            {'indx':'h', 'c':'H00dat'},
            {'indx':'n', 'c':"<a target='_blank' href='https://bitcoin.org/bitcoin.pdf'>Satoshi Nakamoto</a>"},
            {'indx':'p', 'c':"<a target='_blank' href='https://github.com/trevp/axolotl/wiki/newversion'>Trevor Perrin</a>"},
            {'indx':'r', 'c':'Roakyd'},
            {'indx':'r', 'c':'Roid'},
            {'indx':'t', 'c':"<a target='_blank' href='https://shanetully.com/2013/08/mitm-protection-via-the-socialist-millionaire-protocol-otr-style/'>Shane Tully</a>",},
            {'indx':'v', 'c':'Vladimir'},
            {'indx':'x', 'c':'Xmz'},
            {'indx':'z', 'c':'Zh'},
            ],
        'vitals':thirtythirty.utils.Vitals(request),
        }
    context = RequestContext(request, CTD)
    return HttpResponse(template.render(context))


def lockdown(request):
    do_lockdown(request)
    template = loader.get_template('lockdown.dtl')
    context = RequestContext(request, {
        'bg_image':'eject.jpg',
        'title':'You know what to do',
        })
    return HttpResponse(template.render(context))


def do_lockdown(request):
    """
    fluck y'all, i'm heading to tahiti.
    
    called during password bruting overfailure as well

    if we have access to the passphrase, use it to encrypt the DB states
    """
    request.session.flush()
    subprocess.call("/usr/bin/shred -fu /dev/shm/sessions/session*",
                    shell=True)
    LD = queue.system.LOCKDOWN.delay()
    django_rq.enqueue(queue.hdd.Lock, depends_on=LD)
    logger.debug('do_lockdown complete')


@session_pwd_wrapper
def reboot(request):
    queue.system.REBOOT.delay()
    return HttpResponse('Reboot in progress - wait one')


@session_pwd_wrapper
def reset_to_defaults(request):
    """
    CAREFUL, MANHANDLER.
    """
    passphrase = request.session.get('passphrase', None)
    if ((not Passphrase) or (not addressbook.gpg.verify_symmetric(Passphrase))):
        return HttpResponse('No.')
    subprocess.check_output(['/usr/bin/sudo', '-u', 'root', 
                             '/usr/local/bin/LookingGlass/cleanup_startup.sh'])
    for V in thirtythirty.hdd.Volumes(unlisted=False):
        V.lock()
        try: V.remove()
        except: pass
    try: os.unlink(TTS.GPG['export'])
    except: pass
    subprocess.check_output(['/usr/bin/sudo', '-u', 'root', '/sbin/shutdown', '-r', 'now'])
    return HttpResponse('I am become Time, the destroyer...')


@session_pwd_wrapper
def set_advanced(request):
    Preferences = set_up_single_user()
    if request.POST.get('engaged') == 'true':
        Preferences.show_advanced = True
    else:
        Preferences.show_advanced = False
    Preferences.save()
    return HttpResponse(json.dumps({'engaged':Preferences.show_advanced}),
                        content_type='application/json')

@session_pwd_wrapper
def db_disaster(request):
    ratchet.conversation.Conversation.objects.init_for('ratchet')
    ratchet.conversation.Conversation.objects.recover_database()
    smp.models.SMP.objects.init_for('smp')
    smp.models.SMP.objects.recover_database()
    return HttpResponse(json.dumps({'ok':'it is done.'}),
                        content_type='application/json')

@session_pwd_wrapper
def passphrase_cache(request):
    Preferences = set_up_single_user()
    Preferences.passphrase_cache_time = request.POST.get('cache_time',
                                                         thirtythirty.models.preferences.HOURLY)
    if request.POST.get('engaged') == 'true':
        Preferences.passphrase_cache = True
        logger.debug('PP cache enabled: %s' % Preferences.passphrase_cache_time)
    else:
        Preferences.passphrase_cache = False
        logger.debug('PP cache disabled')
    Preferences.save()
    return HttpResponse(json.dumps({'cache_time':Preferences.passphrase_cache_time,
                                    'engaged':Preferences.passphrase_cache,
                                    }),
                        content_type='application/json')


@session_pwd_wrapper
def ip_address(request):
    Preferences = set_up_single_user()
    Preferences.ip_address_type = request.POST.get('ip-address-mode',
                                                   thirtythirty.models.preferences.DYNAMIC_IP)
    Preferences.set_ip(IP = request.POST.get('static-ip', '0.0.0.0'),
                       NM = request.POST.get('netmask', '0.0.0.0'),
                       GW = request.POST.get('gateway-ip', '0.0.0.0')
                       )
    Preferences.save()
    return HttpResponse(json.dumps({'engaged':True,
                                    'ip-address-mode':Preferences.ip_address_type}),
                        content_type='application/json')

@session_pwd_wrapper
def symmetric_copy(request):
    Preferences = set_up_single_user()
    if request.POST.get('tx_engaged') == 'true':
        Preferences.tx_symmetric_copy = True
    else:
        Preferences.tx_symmetric_copy = False
    if request.POST.get('rx_engaged') == 'true':
        Preferences.rx_symmetric_copy = True
    else:
        Preferences.rx_symmetric_copy = False        
    Preferences.save()
    return HttpResponse(json.dumps({'tx_engaged':Preferences.tx_symmetric_copy,
                                    'rx_engaged':Preferences.rx_symmetric_copy,
                                    }),
                        content_type='application/json')


@session_pwd_wrapper
def mount_states(request):
    ret = []
    for V in thirtythirty.hdd.Volumes():
        ret.append({'name':V.Name, 'Mount':V.is_mounted()})
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def server_states(request):
    return HttpResponse(json.dumps(thirtythirty.utils.query_daemon_states()),
                        content_type='application/json')


@session_pwd_wrapper
def mail_log(request):
    return HttpResponse(json.dumps(
        subprocess.check_output(['/usr/bin/sudo', '-u', 'root',
                                 '/usr/bin/tail',
                                 '-n', '25',
                                 '/var/log/mail.log'])
        ), content_type='application/json')


@session_pwd_wrapper
def mail_queue(request):
    return HttpResponse(json.dumps(
        subprocess.check_output(['/usr/sbin/postqueue',
                                 '-p'])
        ), content_type='application/json')


@session_pwd_wrapper
def last(request):
    ret = '%s\n%s' % (
        str(subprocess.check_output(['/usr/bin/uptime'])),
        str(subprocess.check_output(['/usr/bin/last', '-i'])),
        )
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def thirtythirty_logs(request):
    ret = '%s\n%s' % (
        str(subprocess.check_output(['/usr/bin/tail', '/tmp/thirtythirty.log'])),
        str(subprocess.check_output(['/usr/bin/tail', '/tmp/thirtythirty.err'])),
        )
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def update(request):    
    ret = {'ok':False,
           'extra':Available(),
           }
    ret['valid'] = Validate(ret['extra']['filename'])
    if ret['extra'] and ret['valid']:
        try:
            Unpack()
            Cleanup()
            ret['ok'] = True
        except thirtythirty.exception.UpgradeException as e:
            logger.critical(e)
            return HttpResponse(json.dumps({'ok':False,
                                            'extra':'ERROR'}),
                                content_type='application/json')
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')


@session_pwd_wrapper
def force_update(request):
    ret = {'ok':False}
    Filename = request.POST.get('filename', None)
    Location = '%s/%s' % (TTS.UPSTREAM['update_cache'], Filename)
    if Filename and os.path.exists(Location):
        ret['location'] = Location
        try:
            Unpack(Location)
            Cleanup()
            ret['ok'] = True
        except thirtythirty.exception.UpgradeException as e:
            ret['error'] = e
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')
        

@session_pwd_wrapper
def update_upload(request):
    ret = {'ok':False}
    if request.FILES.has_key('updatefile'):
        Filename = request.FILES['updatefile'].name
        ret['filename'] = Filename
        if 'tar.bz2' in Filename:
            Location = '%s/%s' % (TTS.UPSTREAM['update_cache'], Filename)
            with file(Location, 'wb') as destination:
                for chunk in request.FILES['updatefile'].chunks():
                    destination.write(chunk)
            ret['changelog'] = ChangeLog(Location)
            if ret['changelog']:
                ret['ok'] = True
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')
