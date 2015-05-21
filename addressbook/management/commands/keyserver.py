
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
        make_option('--push',
                    action='store_true',
                    default=False,
                    dest='push',
                    help='Push user key to keyserver pool'),
        make_option('--pull',
                    action='store',
                    default=False,
                    dest='pull',
                    help='Pull user key from keyserver pool'),
        )

    
    def handle(self, *args, **settings):
        if settings['push']:
            addressbook.gpg.push_to_keyserver()

        elif settings['pull']:
            addressbook.gpg.pull_from_keyserver(settings['pull'])
