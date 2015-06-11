
from django.core.management.base import BaseCommand

from optparse import make_option

import re

import thirtythirty.settings as TTS
import thirtythirty.utils as TTU

import logging
logger = logging.getLogger(__name__)

Raw = """
[node]
nickname = {HOSTNAME}
tub.port = {PORT}
tub.location = {FQDN}:{PORT}
web.port = tcp:3456:interface=0.0.0.0

[client]
helper.furl = {HELPER_FURL}
introducer.furl = {INTRODUCER_FURL}
mutable.format = mdmf
shares.needed = {NEEDED}
shares.happy = {HAPPY}
shares.total = {TOTAL}

[storage]
enabled = true
reserved_space = {SPACE}
expire.enabled = true
expire.mode = age
expire.override_lease_duration = 14 days

#[drop_upload]
#enabled = {DROP_UPLOAD}
#local.directory = {UPLOAD}
"""

class Command(BaseCommand):
    args = '<NONE>'
    help = 'TAHOE-LAFS interface'

    option_list = BaseCommand.option_list + (
        make_option('--print',
                    action='store_true',
                    dest='print',
                    default=False,
                    help='Output to stdout rather than write file',
                    ),
        )

    def handle(self, *args, **settings):
        FQDN = TTU.HS_Name()
        HOSTNAME = re.sub('\.onion$', '', FQDN)
        Cooked = Raw.format(**{
            'HOSTNAME':HOSTNAME,
            'PORT':TTS.UPSTREAM['tahoe']['my_port'],
            'FQDN':FQDN,
            'HELPER_FURL':TTS.UPSTREAM['tahoe']['helper_furl'],
            'INTRODUCER_FURL':TTS.UPSTREAM['tahoe']['introducer_furl'],
            'NEEDED':TTS.UPSTREAM['tahoe']['shares']['needed'],
            'HAPPY':TTS.UPSTREAM['tahoe']['shares']['happy'],
            'TOTAL':TTS.UPSTREAM['tahoe']['shares']['total'],
            'SPACE':'2G',
            'DROP_UPLOAD':True,
            'UPLOAD':'/home/pi/UPLOAD',
            })
        if settings['print']:
            print Cooked
        else:
            FH = file('%s/tahoe.cfg' % TTS.UPSTREAM['tahoe']['directory'], 'w')
            FH.write(Cooked)
            FH.close()
