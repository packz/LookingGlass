#! /bin/bash

# run this after a `manage.py hdd --decimate` to set things back to defaults.

rm -f /run/shm/*
rm -f /tmp/*.lock
rm -f /srv/docs/public_key.asc
rm -f /run/shm/drives_exist
rm -f /etc/mailname
rm -f /etc/nginx/sites-available/default
rm -f /etc/ssl/private/LookingGlass.pem
rm -f /etc/ssl/certs/LookingGlass.crt.pem
