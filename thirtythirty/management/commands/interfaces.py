
from django.core.management.base import BaseCommand

from optparse import make_option

import thirtythirty.models as TM

Output = '/etc/network/interfaces'

class Command(BaseCommand):
    args = '<NONE>'
    help = 'Output %s file' % Output

    option_list = BaseCommand.option_list + (
        make_option('--print', '--dump', '-p',
                    action='store_true',
                    dest='print',
                    default=False,
                    help='Output what would be written to file',
                    ),
        )
    
    def handle(self, *args, **settings):
        P = TM.preferences.objects.first()
        Eth0 = 'iface eth0 inet dhcp'
        if P.ip_address_type == TM.preferences.STATIC_IP:
            Eth0 = """iface eth0 inet static
            address %s
            netmask %s
            gateway %s
            """ % (
            P.ip_addr,
            P.netmask,
            P.gateway,
            )
        Raw = """
auto lo lo:1 eth0

iface lo inet loopback

iface lo:1 inet static
	address 192.168.100.1
	netmask 255.255.255.255

%s
""" % ( Eth0 )

        if settings['print']:
            print Raw
        else:
            FH = file(Output, 'w')
            FH.write(Raw)
            FH.close()
