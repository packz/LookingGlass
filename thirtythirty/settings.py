
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# used to differentiate message formats - don't change idly
VERSION_FILE = os.path.join(BASE_DIR, 'VERSION')
try:
    LOOKINGGLASS_VERSION = eval(file(VERSION_FILE, 'r').read().strip()) # yup, i did it
except:
    LOOKINGGLASS_VERSION = (0, 0, 0)
LOOKINGGLASS_VERSION_STRING = 'LookingGlass V%02d.%02d.%02d' % LOOKINGGLASS_VERSION

# makes authentication a bit faster, at the expense of ZOMG security
PASSPHRASE_CACHE = '/run/shm/passphrase_cache'

# Things I need to know to talk to the outside world
UPSTREAM = {
    'bug_report_email':'last.box@sdtrssmsbmw7eqm4.onion',
    'keyserver':       'sdtrssmsbmw7eqm4.onion:58008',
    'update_log':'/tmp/update.log',
    'update_cache':'/tmp/cache',
    'updates':[{'type':'RSYNC',
                'uri':'rsync://sdtrssmsbmw7eqm4.onion:51239',
                },
               ],
    'trusted_prints':[
        # these need to be system_use, not imported by the user
        'A4D0785226C649011F01F5EE2E08B316D5BE3439',
        '9D78B8A6E3F607D0D705DEB8EF12B2899AE46EB7',
        ],
    }

# i tried using getuser() here, but supervisord kept feeding my script 'root' before it dropped privs...
USERNAME = 'pi'

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
    'thirtythirty',
    'gunicorn',
    'setup',
    'emailclient',
    'addressbook',
    'ratchet',
    'smp',
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
        'NAME': '/run/shm/smp.sqlite3',
        'LOCKED': '/home/%s/.gnupg/smp.gpg' % USERNAME,
        'BACKUP': '/home/%s/.gnupg/smp.gpg~' % USERNAME,
        },
    'ratchet': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/run/shm/ratchet.sqlite3',
        'LOCKED': '/home/%s/.gnupg/ratchet.gpg' % USERNAME,
        'BACKUP': '/home/%s/.gnupg/ratchet.gpg~' % USERNAME,
        },
}

DATABASE_ROUTERS = ['thirtythirty.cryptorouter.AddressRouter',
                    'thirtythirty.cryptorouter.RatchetRouter',
                    'thirtythirty.cryptorouter.SmpRouter',
                    'thirtythirty.cryptorouter.DefaultRouter',]


SESSION_ENGINE = 'django.contrib.sessions.backends.file'

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
            'propagate':True,
            'level':'WARNING',
            },
        # UGH
        'addressbook': {
            'handlers': ['file'],
            'level': 'DEBUG',
            },
        'emailclient': {
            'handlers': ['file'],
            'level': 'DEBUG',
            },
        'ratchet': {
            'handlers': ['file'],
            'level': 'DEBUG',
            },
        'setup': {
            'handlers': ['file'],
            'level': 'DEBUG',
            },
        'smp': {
            'handlers': ['file'],
            'level': 'DEBUG',
            },
        'thirtythirty': {
            'handlers': ['file'],
            'level': 'DEBUG',
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
    {'name':'qwebirc',
     'description':'Chat gateway',
     'check':['pgrep', '-u', 'qwebirc', 'python'],
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
    'shortcut_check_file':'/run/shm/drives_exist',
    'key_file':'/run/shm/luks.key',  # do not change this without updating /etc/crypttab !
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
                ['/usr/bin/supervisorctl', 'start', 'qwebirc'],
                ],
            'pre-down':[
                ['/usr/local/bin/LookingGlass/emergency_tor_crash.sh'],
                ['/usr/bin/supervisorctl', 'stop', 'qwebirc'],
                ],
            },
        {
            'name':'pi_gpg',
            'description':'Address Book',
            'size':'10M',
            'mountpoint':'/home/%s/.gnupg' % USERNAME,
            'owner':'pi:',
            'permissions':[
                ('/home/%s/.gnupg' % USERNAME, '700'),
                ],
            },
        {
            'name':'pi_mail',
            'description':'Saved Email',
            'size':'01G',
            'mountpoint':'/home/%s/Maildir' % USERNAME,
            'owner':'pi:',
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
            'name':'pi_electrum',
            'description':'Wallet',
            'size':'10M',
            'mountpoint':'/home/%s/.electrum' % USERNAME,
            'owner':'pi:',
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

GPG = {
    'encoding':'utf-8',
    'export':'/srv/docs/public_key.asc',
    'options':[
        '--keyid-format=LONG',
        '--throw-keyids',
        '--personal-digest-preferences=sha256',
        '--s2k-digest-algo=sha256',
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
