
from django.core.management.base import BaseCommand

from optparse import make_option

import re
import subprocess
import thirtythirty.utils

Output = '/etc/nginx/sites-available/default'

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

    def first_ip(self):
        face = subprocess.check_output(['/sbin/ifconfig'])
        Int = None
        for Line in face.split('\n'):
            I = re.search('^(?P<Int>(eth|lo|wlan).)', Line)
            if I:
                Int = I.group('Int')
            A = re.search('addr:(?P<IP>[\.0-9]+)\ ', Line)
            if A and 'lo' not in Int:
                return A.group('IP')
        return None
    
    def handle(self, *args, **settings):
        HS_Hostname = thirtythirty.utils.HS_Name()
        if not HS_Hostname:
            print "We're not configured yet - waiting on tor"
            exit(-1)
        
        # Note: All curly braces escaped by doubling
        Raw = """
upstream gunicorn {{
	server localhost:8000;
}}

server {{
       # serves certs maybe to tor (future use)
       listen 8080;
       autoindex on;
       root /srv/docs;
       }}

server {{
        listen 80;
	listen 443 ssl;
        client_max_body_size 0;
	ssl_certificate		/etc/ssl/certs/LookingGlass.crt.pem;
	ssl_certificate_key	/etc/ssl/private/LookingGlass.pem;
	keepalive_timeout	70;

	root /home/pi;

	index index.html index.htm;

	server_name {Onion} {IP};

	try_files $uri @gunicorn;

        error_page 502 /502.html;

	location @gunicorn {{
		proxy_pass http://gunicorn;
		proxy_redirect off;
		proxy_read_timeout 5m;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Protocol $scheme;
	}}

        location /502.html {{
           alias /srv/error/502.html;
        }}

        location /favicon.ico {{
                alias /srv/img/favicon.ico;
        }}

	location /css {{
		alias /srv/css;
		disable_symlinks off;
	}}

        location /docs {{
                alias /srv/docs;
                disable_symlinks off;
        }}

	location /fonts {{
                alias /srv/fonts;
                disable_symlinks off;
	}}

	location /img {{
                alias /srv/img;
                disable_symlinks off;
        }}

	location /js {{
		alias /srv/js;
		disable_symlinks off;
	}}

}}
""".format(**{
              'IP':self.first_ip(),
              'Onion':HS_Hostname,
})
        if settings['print']:
            print Raw
        elif self.first_ip():
            FH = file(Output, 'w')
            FH.write(Raw)
            FH.close()
