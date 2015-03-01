
from django.shortcuts import redirect
from django.http import HttpResponse
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse

from django.contrib.auth import authenticate, login

import json
import re
import os
from stat import S_IRUSR, S_IWUSR
import os.path
import shutil
from uuid import uuid4

import addressbook
import setup

import thirtythirty.hdd as TTH
import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)

def gen_passphrase(request, words=4):
        return HttpResponse(json.dumps(setup.passphrase.generate(words)),
                            content_type='application/json')


def gen_covername(request):
        return HttpResponse(json.dumps(addressbook.covername.generate()),
                            content_type='application/json')

def please_wait(request, caption):
        """
        This is used between stages when we do heavy lifting
        """
        template = loader.get_template('please_wait.dtl')
        context = RequestContext(request, {
                'title':'Crunching numbers',
                'bg_image':'wait-one.jpg',
                'caption':caption,
                })
        return HttpResponse(template.render(context))


def luks(request, clobber=False):
        PDB = setup.ipc_db.FileDB(clobber)
        PDB.update(request.POST)
        if TTH.drives_exist():
                return redirect('emailclient.inbox')
        if PDB['drive.key'] is not None:
                return redirect('setup.covername')
        template = loader.get_template('setup.dtl')
        url = reverse('setup.covername')
        context = RequestContext(request, {
                'title':'LUKS Setup',
                'next':url,
                'input_name':'drive.key',
                'help_url':'https://www.schneier.com/blog/archives/2014/03/choosing_secure_1.html',
                'explanation':"""
                <p>Let's begin by setting a passphrase to encrypt all your sensitive data.</p>
                <p>You will use this passphrase to unlock the device every time you reboot it.</p>
                <p>The login screen will be a vault door when this passphrase is required.</p>
                """,
                })
        return HttpResponse(template.render(context))


def covername(request):
        PDB = setup.ipc_db.FileDB()
        PDB.update(request.POST)
        if PDB['drive.key'] is None:
                return redirect('setup.luks')
        if PDB['covername'] is not None:
                return redirect('setup.gpg')
        if not TTU.query_daemon_states('tor'):
                return please_wait(request, caption='drive encryption')
        template = loader.get_template('setup.dtl')
        context = RequestContext(request, {
                'title':'Covername selection',
                'input_name':'covername',
                'help_url':'https://en.wikipedia.org/wiki/Pseudonym#Computer_users',
                'covername':True,
                'explanation':"""
                <p>Now, we need to choose a cover name.</p>
                <p>This is a unique name people use to find you.</p>
                """,
                'word_list':sorted(PDB['drive.key'].split(' ')),
                })
        return HttpResponse(template.render(context))


def gpg(request):
        PDB = setup.ipc_db.FileDB()
        PDB.update(request.POST)
        if PDB['covername'] is None:
                return redirect('setup.luks')
        if PDB['gpg.key'] is not None:
                return redirect('setup.finished')
        template = loader.get_template('setup.dtl')
        url = reverse('setup.finished')
        WL = []
        WL.append(PDB['drive.key'])
        WL.append(PDB['covername'].lower())
        WL.extend(PDB['drive.key'].split(' '))
        WL.extend(PDB['covername'].lower().split(' '))
        context = RequestContext(request, {
                'title':'GPG Setup',
                'next':url,
                'input_name':'gpg.key',
                'help_url':'https://www.schneier.com/blog/archives/2014/03/choosing_secure_1.html',
                'explanation':"""
                <p>The second line of defense for your emails is to put a passphrase on them.</p>
                <p>You will use this passphrase when you are interacting with your mail.</p>
                <p>This will be your most commonly used, day to day passphrase.</p>
                """,
                'word_list':sorted(WL),
                })
        return HttpResponse(template.render(context))


def finished(request):
        PDB = setup.ipc_db.FileDB()
        PDB.update(request.POST)
        
        for X in PDB.keys():
                if PDB[X] is None:
                        return redirect('setup.luks')
        if ((not os.path.exists(TTS.GPG['secring_location'])) or
            (os.stat(TTS.GPG['secring_location']).st_size == 0)):
                # waiting on gpg creating keypair
                return please_wait(request, caption='key creation')

        if not addressbook.gpg.create_symmetric(passphrase=PDB['gpg.key'], clobber=True):
                # dun rong!
                logger.debug('Cookie error - wtf')
                return HttpResponse(json.dumps({'comment':'cookie error',
                                                'status':False}),
				    content_type='application/json')
        else:
                logger.debug('Created secret cookie')
        
        # log in so they don't have to do it again
        ooser = authenticate(password=PDB['gpg.key'])
        if ooser:
                request.session['passphrase'] = PDB['gpg.key']
                login(request, ooser)
                logger.debug('User logged in')
        
        template = loader.get_template('finished.dtl')
        context = RequestContext(request, {
                'title':'Finished!',
                'show_navbar':False,
                'your_info':"""
                Your covername: %s
                Your drive passphrase: %s
                Your mail passphrase: %s
                """ % (
                        PDB['covername'],
                        PDB['drive.key'],
                        PDB['gpg.key'],
                        ),
                })
        return HttpResponse(template.render(context))


def create_user(request):
        """
        This is the user finalizing their choices.
        Order is important!
        """
        PDB = setup.ipc_db.FileDB()

        for X in PDB.keys():
                if PDB[X] is None:
                        return 'Not so fast, turbo.'

        Me = addressbook.utils.my_address()

        # so we can get the cronjob running
        fh = file(TTS.PASSPHRASE_CACHE, 'w')
        os.chmod(TTS.PASSPHRASE_CACHE, S_IRUSR | S_IWUSR)
        fh.write(PDB['gpg.key'])
        fh.close()
        logger.debug('Created passphrase cache')

        # update user passwd
        TTU.popen_wrapper(['/usr/local/bin/LookingGlass/passwd_update.sh'])
        logger.debug('Updated pi user passwd')

        Me.comment = 'accepted LUKS passphrase'
        Me.save()
        shutil.copyfile('%s/drive.key' % PDB.file_loc, TTS.LUKS['key_file'])
        logger.debug('Signal for LUKS passphrase update, squirrel away copy of LUKS passwd')

        Me.covername = PDB['covername']
        Domain = re.sub('.*@', '', Me.email)
        Me.email = '%s@%s' % (PDB['covername'].replace(' ', '.').upper(),
                              Domain.upper())
        Me.save()
        logger.debug('Updated user info in addressbook: %s' % Me)

        addressbook.queue.Queue.objects.create(address=Me,
                                               direction=addressbook.queue.Queue.TX,
                                               body='%s|%s' % (Me.covername, Me.email),
					       messageid=str(uuid4()),
                                               message_type=addressbook.queue.Queue.GPG_PK_PUSH)
        logger.debug('Queued PK push for %s' % Me.covername)

        R = addressbook.gpg.change_passphrase(old='1234', new=PDB['gpg.key'])
        logger.debug('Changed default password: %s' % R)
                
        R = addressbook.gpg.change_uid(passwd=PDB['gpg.key'])
        logger.debug('Update GPG DB to correct UID info: %s' % R)

        PDB.burn_notice()
        logger.debug('Removed on-disk temporary database')

        return HttpResponse(json.dumps({'comment':'awww yisss',
                                        'status':True}),
                            content_type='application/json')


def updates_complete(request):
        return HttpResponse(json.dumps(TTH.drives_exist()),
                            content_type='application/json')

