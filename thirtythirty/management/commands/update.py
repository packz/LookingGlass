
from django.core.management.base import BaseCommand

from optparse import make_option

import json
import os
import time

import thirtythirty.updater
import thirtythirty.settings as TTS

class Command(BaseCommand):
    args = '[Server_URI]'
    help = 'System upgrader'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run',
                    action='store_true',
                    dest='dry_run',
                    default=False,
                    help="Don't actually install",
                    ),
        make_option('--no-socket',
                    action='store_true',
                    dest='socket_disable',
                    default=False,
                    help="Don't read from the control socket - download and validate",
                    ),
        make_option('--validate-anything-with-bits', '--no-check', '--megagape',
                    action='store_true',
                    dest='valid_override',
                    default=False,
                    help="I don't give a rip if the signature isn't valid",
                    ),
        )


    def handle(self, *args, **settings):
        Request = {'mode':'unpack'}
        
        if ((not settings['socket_disable']) and
            (os.path.exists(TTS.UPSTREAM['update_socket']))):
            fh = file(TTS.UPSTREAM['update_socket'], 'r')
            try:
                Request = json.loads(fh.read())
            except ValueError:
                print 'JSON horked in request - assuming `download`'
                Request = {'mode':'download'}
            fh.close()

        # NOW you can begin...
        Server = None
        Socket = file(TTS.UPSTREAM['update_socket'], 'w')

        def emit_json(S):
            S['serial'] = '%.2f' % time.time()
            print S
            Socket.write( json.dumps(S) )
            Socket.write('\n')
            Socket.flush()
        
        if len(args) != 0:
            Server = args[0]

        U = thirtythirty.updater.Updater()
        emit_json({'ok':True,
                   'status':'Downloading list of updates'})
        
        GMR = U.GetMostRecent(asString=True)
        UDA = U.MoreRecentAvailable()
        if not UDA:
            status = 'Already up to date'
            emit_json({'current':TTS.LOOKINGGLASS_VERSION_STRING,
                       'scanned':GMR,
                       'ok':False,
                       'updatable':UDA,
                       'status':status})
            exit(-1)

        status = 'Newer version available - %s' % GMR
        emit_json({'current':TTS.LOOKINGGLASS_VERSION_STRING,
                   'scanned':GMR,
                   'ok':True,
                   'updatable':UDA,
                   'status':status})

        if Request['mode'] == 'download':
            DL = U.Download()
            emit_json({'version':DL,
                       'ok':True,
                       'status':'Downloaded version %02d.%02d' % (int(DL[0]), int(DL[1])),
                       'tempdir':U.Cache})

        Fingerprint = U.ClearsignedBy()
        if not Fingerprint:
            emit_json({'ok':False,
                       'status':'Signature hosed'})
            exit(-1)

        ok = False
        if Fingerprint in TTS.UPSTREAM['trusted_prints']:
            ok = True

        A = U.Validate(Fingerprint)
        if not A.system_use and not settings['valid_override']:
            emit_json(
                {'status':"fingerprint for %s isn't marked system_use" % A.covername,
                 'bogus':True,
                 'ok':False})
            exit(-1)

        Status = 'fingerprint %s trusted, verified' % Fingerprint
        if not A.system_use and settings['valid_override']:
            Status = 'fingerprint for %s is bogus -- but check was overrided!' % A.covername
            ok = True
        
        emit_json({'status':Status,
                   'fingerprint':Fingerprint,
                   'mode':Request['mode'],
                   'address':str(A.email),
                   'ok':ok})
            
        if ((not settings['dry_run']) and
            (ok) and
            (Request['mode'] == 'unpack')):
            zrrrp = U.Unpack()
            emit_json({'file_list':zrrrp,
                       'status':'unpacked %s files' % len(zrrrp),
                       'ok':True})

            U.Cleanup()
