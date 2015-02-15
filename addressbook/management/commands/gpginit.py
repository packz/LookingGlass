
from django.core.management.base import BaseCommand

import getpass
from os.path import exists
from optparse import make_option

import addressbook
import thirtythirty.settings as TTS

class Command(BaseCommand):
    args = '<None>'
    help = 'Managing GPG keys and login cookie'

    option_list = BaseCommand.option_list + (
        make_option('-f', '--force',
                    action='store_true',
                    default=False,
                    dest='force',
                    help='Clobber'),
        make_option('--new',
                    action='store',
                    default=False,
                    dest='new',
                    help='Specify a new passphrase for my key'),
        make_option('--rename',
                    action='store_true',
                    default=False,
                    dest='rename',
                    help='Specify a new user id for my key'),
        make_option('-p', '--passphrase',
                    action='store',
                    default=False,
                    dest='passphrase',
                    help='Specify passphrase on commandline (lazy and bad)'),
        make_option('--covername',
                    action='store',
                    default=None,
                    dest='covername',
                    help='Covername to use in key creation'),
        make_option('--hostname',
                    action='store',
                    default=None,
                    dest='hostname',
                    help='Hostname to use in key creation'),
        make_option('--cookie',
                    action='store_true',
                    default=False,
                    dest='cookie',
                    help='Initialize login cookie'),
        make_option('--genkey',
                    action='store_true',
                    default=False,
                    dest='genkey',
                    help='Create GPG private key'),
        )

    def handle(self, *args, **settings):
        if not settings['passphrase']:
            P = getpass.getpass()
            C = getpass.getpass('Confirm:')
            if P != C:
                print "Don't match - wah wah."
                exit(-1)
            settings['passphrase'] = P
            
        if settings['cookie']:
            if exists(TTS.GPG['symmetric_location']) and not settings['force']:
                print 'Already exists.  If you are feeling sporty, you can `--force`'
                exit(-1)
            addressbook.gpg.create_symmetric(
                passphrase=settings['passphrase'],
                clobber=settings['force'])
            
        if settings['genkey']:
            if ((not settings['covername']) or
                (not settings['hostname']) or
                (not settings['passphrase'])):
                print 'You need to specify --covername, --hostname, and --passphrase'
                exit(-1)
            Email = '%s@%s' % (settings['covername'].replace(' ', '.').upper(),
                               settings['hostname'].upper())
            addressbook.gpg.generate_key(passphrase=settings['passphrase'],
                                         covername=settings['covername'],
                                         email=Email)

        if settings['new']:
            print addressbook.gpg.change_passphrase(new=settings['new'],
                                                    old=settings['passphrase'])

        if settings['rename']:
            print addressbook.gpg.change_uid(passwd=settings['passphrase'])
