
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

from getpass import getuser

# used to differentiate message formats - don't change idly
VERSION_FILE = os.path.join(BASE_DIR, 'VERSION')
try:
    LOOKINGGLASS_VERSION = eval(file(VERSION_FILE, 'r').read().strip()) # yup, i did it
except:
    LOOKINGGLASS_VERSION = (0, 0, 0)
LOOKINGGLASS_VERSION_STRING = 'LookingGlass V%02d.%02d.%02d' % LOOKINGGLASS_VERSION

# makes authentication a bit faster, at the expense of ZOMG security
PASSPHRASE_CACHE = '/dev/shm/passphrase_cache'

# Things I need to know to talk to the outside world
UPSTREAM = {
    'bug_report_email':'last.box@sdtrssmsbmw7eqm4.onion',
    'keyserver':       'sdtrssmsbmw7eqm4.onion:58008',
    'update_log':'/tmp/update.log',
    'update_lock':'/var/cache/LookingGlass/alert.lock',
    'update_cache':'/var/cache/LookingGlass',              # update the preinst script if you change this
    'update_script_dir':'/var/cache/LookingGlass',         # update the preinst script if you change this
    'updates':[{'type':'RSYNC',
                'uri':'rsync://sdtrssmsbmw7eqm4.onion:51239',
                },
               ],
    'trusted_prints':[
        # these get flagged as system_use
        'A4D0785226C649011F01F5EE2E08B316D5BE3439',
        '9D78B8A6E3F607D0D705DEB8EF12B2899AE46EB7',
        ],
    'tahoe':{
        'my_port':58008,
        'shares':{
            'needed':1,
            'happy':1,
            'total':1,
            },
        'directory':'/var/lib/tahoe-lafs/LookingGlass', # keep this in sync with postinst.2 and firstboot
        'introducer_furl': str('pb://'
                               'x4lipzre6dwzrrb62q7kgjmket5b6kvs@'
                               'tylwl7kqpo2e4qvq.onion'
                               ':60179/'
                               '4jg6uu25pkz5nirvovglpsoysyu66xk5'),
        'helper_furl':'',  # future use
        },
    }

USERNAME = getuser()

# it's hideous to run code in here, but it seemed cleaner than doing this in a shell script
SECRET_FILE = os.path.join(BASE_DIR, 'secret.txt')
try:
    SECRET_KEY = file(SECRET_FILE, 'r').read().strip()
except IOError:
    import string
    from random import SystemRandom
    Choice = "{}{}{}".format(string.ascii_letters, string.digits, string.punctuation)
    SECRET_KEY = ''.join([SystemRandom().choice(Choice) for i in range(50)])
    try:
        secret = file(SECRET_FILE, 'w')
        secret.write(SECRET_KEY)
        secret.close()
        os.chmod(SECRET_FILE, 0600)
    except IOError:
        # this gets hit from the milter.  ignore it.
        SECRET_KEY = 'BOGUS'

# nginx hands us this so we know HTTP from HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')

DEBUG = False
TEMPLATE_DEBUG = False

ALLOWED_HOSTS = ['*'] # FIXME: bolt this down to just local segment in future?

# Application definition

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django_rq',
    'rest_framework',
    'gunicorn',
    'addressbook',
    'emailclient',
    'queue',
    'ratchet',
    'setup',
    'smp',
    'thirtythirty',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'thirtythirty.urls'

WSGI_APPLICATION = 'thirtythirty.wsgi.application'


# multiple databases - some (de|en)crypted on demand

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    },
    'addressbook': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/home/%s/.gnupg/addressbook.sqlite3' % USERNAME,
        },
    # these DBs are manually encrypted/decrypted
    'smp': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/dev/shm/smp.sqlite3',
        'LOCKED': '/home/%s/.gnupg/smp.gpg' % USERNAME,
        'BACKUP': '/home/%s/.gnupg/smp.gpg~' % USERNAME,
        },
    'ratchet': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/dev/shm/ratchet.sqlite3',
        'LOCKED': '/home/%s/.gnupg/ratchet.gpg' % USERNAME,
        'BACKUP': '/home/%s/.gnupg/ratchet.gpg~' % USERNAME,
        },
}

DATABASE_ROUTERS = ['thirtythirty.cryptorouter.AddressRouter',
                    'thirtythirty.cryptorouter.RatchetRouter',
                    'thirtythirty.cryptorouter.SmpRouter',
                    'thirtythirty.cryptorouter.DefaultRouter',]

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = '/dev/shm/sessions' # created by lookingglass-fixup.service

# using gpg for our session password
AUTHENTICATION_BACKENDS = ( 'thirtythirty.gpgauth.gpgAuth', )

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = False

TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]

# precompiled covernames
COVERNAME_DB = {
    'directory':'/usr/share/LookingGlass',
    'first':'dist.first.precomp',
    'last':'dist.last.precomp',
    }

# then i ran into needing this, for the queue engine
LOGGING = {
    'version':1,
    'disable_existing_loggers': False,
    'formatters':{
        'verbose': {
            'format' : "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt' : "%d/%b/%Y %H:%M:%S"
            },
        'simple': {
            'format': '%(levelname)s %(message)s'
            },
        },
    'handlers': {
        'stream':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter':'verbose',
            },
        'file':{
            'level':'DEBUG',
            'class':'logging.FileHandler',
            'formatter':'verbose',
            'filename':'/tmp/thirtythirty.log',
            },
        },
    'loggers':{
        'django':{
            'handlers':['stream'],
            'level':'WARNING',
            'propagate':True,
            },
        # UGH
        'addressbook': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'emailclient': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'queue': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'ratchet': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'setup': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'smp': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'thirtythirty': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate':True,
            },
        'rq.worker': {
            'handlers': ['file'],
            'level': 'WARNING',  # rq is chatty
            'propagate':True,
            },
        },
    }


# Daemons and how to find them

DAEMONS = [
    {'name':'tor',
     'description':'TOR',
     'check':['ps', '-C', 'tor'],
     },
    {'name':'postfix',
     'description':'Mail server',
     'check':['ps', '-C', 'master'],
     },
    {'name':'hashcash',
     'description':'DDOS protection',
     'check':['ps', '-C', 'hashcash-milter'],
     },
    {'name':'weechat',
     'description':'Chat relay',
     'check':['pgrep', '-u', '%s' % USERNAME, 'weechat'],
     },
    {'name':'shellinabox',
     'description':'Local wizard login',
     'check':['ps', '-C', 'shellinaboxd'],
     },
    ]


# LUKS is Linux Unified Key Setup - encrypted partitions

LUKS = {
    'device':'/dev/mmcblk0',
    'vg_name':'LookingGlass',
    'fs':'ext4',
    'shortcut_check_file':'/dev/shm/drives_exist',
    'key_file':'/dev/shm/luks.key',  # do not change this without updating /etc/crypttab !
    'mounts':[ # list, so we can (roughly) define boot/shutdown order
        {
            'name':'tor_var',
            'description':'TOR',
            'size':'01G',
            'mountpoint':'/var/lib/tor',
            'owner':'debian-tor:',
            'permissions':[
                ('/var/lib/tor','2700'),
                ],
            'post-up':[
                ['/etc/init.d/tor', 'start'],
                ['/bin/systemctl', 'start', 'weechat'],
                ],
            'pre-down':[
                ['/usr/local/bin/LookingGlass/emergency_tor_crash.sh'],
                ['/bin/systemctl', 'stop', 'weechat'],
                ],
            },
        {
            'name':'pi_electrum',
            'description':'Wallet',
            'size':'10M',
            'mountpoint':'/home/%s/.electrum' % USERNAME,
            'owner':'%s:' % USERNAME,
            'permissions':[
                ('/home/%s/.electrum' % USERNAME, '700'),
                ],
            # 'post-init':[    # FIXME: need to catch the seed - heh
            #     ['/home/%s/.virtualenvs/thirtythirty/bin/electrum' % USERNAME,
            #      '--offline',
            #      '--gui', 'stdio',
            #      '--password', file(PASSPHRASE_CACHE, 'r').read(),
            #      'create']
            #     ],
            },
        {
            'name':'pi_gpg',
            'description':'Address Book',
            'size':'10M',
            'mountpoint':'/home/%s/.gnupg' % USERNAME,
            'owner':'%s:' % USERNAME,
            'permissions':[
                ('/home/%s/.gnupg' % USERNAME, '700'),
                ],
            'post-up':[
                ['/usr/sbin/sudo', '-u', 'root', '/bin/systemctl', 'start', 'parcimonie-sh'],
                ],
            'pre-down':[
                ['/usr/sbin/sudo', '-u', 'root', '/bin/systemctl', 'stop', 'parcimonie-sh'],
                ],
            },
        {
            'name':'pi_mail',
            'description':'Saved Email',
            'size':'01G',
            'mountpoint':'/home/%s/Maildir' % USERNAME,
            'owner':'%s:' % USERNAME,
            'permissions':[
                ('/home/%s/Maildir' % USERNAME, '700'),
                ],
            'post-init':[
                ['/bin/mkdir', '/home/%s/Maildir/new' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/cur' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/tmp' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.admin' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.admin/new' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.admin/cur' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.admin/tmp' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.sent' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.sent/new' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.sent/cur' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.sent/tmp' % USERNAME],                
                ['/bin/mkdir', '/home/%s/Maildir/.trash' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.trash/new' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.trash/cur' % USERNAME],
                ['/bin/mkdir', '/home/%s/Maildir/.trash/tmp' % USERNAME],
                ['/bin/chown', '%s:' % USERNAME, '--recursive', '/home/%s/Maildir' % USERNAME],
                ['/bin/cp', '/etc/skel/.procmailrc', '/home/%s' % USERNAME],
                ],
            },
        # {
        #     'name':'testing',
        #     'description':'Test mount',
        #     'size':'10M',
        #     'mountpoint':'/mnt/testing',
        #     'owner':'pi:',
        #     'unlisted':True,
        #     'permissions':[
        #         ('/mnt/testing', '700'),
        #         ],
        #     },
        {
            'name':'postfix_etc',
            'description':'Mail server',
            'size':'01M',
            'mountpoint':'/etc/postfix',
            'owner':'root:',
            'permissions':[
                ('/etc/postfix', '755'),
                ],
            'post-init':[
                ['/bin/cp', '/usr/share/LookingGlass/postfix/Makefile', '/etc/postfix'],
                ],
            'post-up':[
                ['/usr/bin/make', '--directory', '/etc/postfix', 'all'],
                ],
            'pre-down':[
                ['/usr/bin/make', '--directory', '/etc/postfix', 'stop'],
                ],
            },
        ]
    }



# GPG setup - crypto tweaks
GPG_TIMEOUT = 10
GPG = {
    'debug':False,
    'encoding':'utf-8',
    'export':'/srv/docs/public_key.asc',
    'keyserver':[
        'hkp://keys.gnupg.net',
        'hkp://pgp.mit.edu',
        'hkp://pool.sks-keyservers.net',
        ],
    'options':[
        '--keyid-format=LONG',
        '--keyserver-options=no-honor-keyserver-url,timeout=%s' % GPG_TIMEOUT,
        '--personal-digest-preferences=sha256',
        '--s2k-digest-algo=sha256',
        '--throw-keyids',
        ],
    'root':'/home/%s/.gnupg' % USERNAME,
    'symmetric_location':'/home/%s/.gnupg/symmetric.asc' % USERNAME,
    'secring_location':  '/home/%s/.gnupg/secring.gpg'   % USERNAME,
    'symmetric_algo':'AES256',
    'magic_cookie':"""
    They will try again.
    A year from now - ten?
    They'll swing back to the belief that they can make people better - and I do not hold to that.
    So no more runnin.
    I aim to misbehave.
""",
    }



# Hashcash - proof of work for DDOS protection

HASHCASH = {
    'RATE_LIMIT_SECONDS':300,
    'BACKOFF':{
        'QUEUE':'/tmp/queue-backoff.lock',
        'UPSTREAM':'/tmp/upstream-backoff.lock',
        },
    'BITS':{
        'WEBUI':18,
        'MILTER':20,
        'UPSTREAM':20,
        },
    }


# rest framework for new angular.js interface
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        ),
    'DEFAULT_PERMISSION_CLASSES':[
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES':(
        'rest_framework.renderers.JSONRenderer',
    ),
}
    
# redis queue for async job queue
RQ_QUEUES = {
    'default':{
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': None,
        'DEFAULT_TIMEOUT': 360,
        },
    'needs_passphrase':{
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 1,
        },
    }
