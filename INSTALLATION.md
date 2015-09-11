# Configure LUKS

    $ manage.py hdd --create-all --passphrase 1234
    $ manage.py migrate --database smp
    $ manage.py migrate --database ratcher

# Configure tor

https://www.thecthulhu.com/setting-up-a-hidden-service-with-nginx/

# GPG

After installed tor and cheched that the hostname is generate in ``/var/lib/tor/hidden_service/hostname``

    $ python manage.py migrate --database addressbook
    $ python manage.py gpginit --genkey --passphrase 1234 --covername EMPTYUID --hostname `sudo /bin/cat /var/lib/tor/hidden_service/hostname`
    ... wait several minutes (like 20 minutes using vagrant) ...