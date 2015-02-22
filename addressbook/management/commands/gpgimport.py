
from django.core.management.base import BaseCommand

import addressbook
from optparse import make_option

class Command(BaseCommand):
    args = '<None>'
    help = 'Import addresses from GPG keyring'

    option_list = BaseCommand.option_list + (
        make_option('--delete',
                    action='store_true',
                    default=False,
                    dest='delete',
                    help='Delete addressbook entries that do not exist in GPG keychain'),
        )

    def handle(self, *args, **settings):
        if settings['delete']:
            print addressbook.address.Address.objects.remove_removed()
        
        for Imported in addressbook.address.Address.objects.rebuild_addressbook():
            print Imported
        
