
SHELL = /bin/bash

DB = /etc/postfix/local_recipients.db /etc/postfix/header_checks.db

Aliases = /etc/postfix/aliases.db

Addressbook = /home/pi/.gnupg/addressbook.sqlite3
Covername = /etc/postfix/covername
Hostname = /var/lib/tor/hidden_service/hostname
Loopback = 192.168.100.1

HC_Bin=/usr/local/bin/LookingGlass/hashcash-milter.py
HC_Dir=/var/spool/postfix/hashcash-milter/
HC_Sock=$(HC_Dir)/hashcash.sock
HC_User=hashcash-milter

Src_Dir=/usr/share/LookingGlass/postfix

Local_Username=pi
Enable_Hashcash=1

.PHONY:	all up clean start stop reload watch debug /etc/postfix

all:	up start

up:	$(Src_Dir)
	/usr/bin/rsync -rupE $(Src_Dir)/ /etc/postfix

stop:
	-/etc/init.d/postfix stop &
	-ps aux | awk '/(python|su).*hashcash-milter.py$$/ {print $$2}' | xargs kill
	-rm -f $(HC_Sock)
	-/bin/false ;\
	while [[ $$? -ne 0 ]]; do \
	sleep 5 ;\
	ps aux |\
	grep -q `cat /var/spool/postfix/pid/master.pid | sed -re 's|[^0-9]+||g'` ;\
	done

start:	/etc/postfix /etc/postfix/main.cf $(DB) $(Aliases) $(HC_Sock)
	@if [[ -e $(HC_Sock) ]] && (ps aux | grep -q '[h]ashcash-milter'); then \
	rm -vf $(HC_Sock) && make $(HC_Sock) ;\
	fi
	/etc/init.d/postfix start &

reload:	stop start

watch debug:
	tail -f /var/log/mail.log /var/log/mail.err /var/log/mail.info /var/log/mail.warn /tmp/milter.log

/etc/postfix/local_recipients:	/etc/postfix/local_recipients.m4 $(Hostname) $(Covername)
	m4 -DHOSTNAME=`cat $(Hostname)` -DCOVERNAME=`cat $(Covername)` $< > $@

/etc/postfix/main.cf:	/etc/postfix/main.cf.m4 $(Hostname)
	m4 -DWITH_HASHCASH=$(Enable_Hashcash) -DHOSTNAME=`cat $(Hostname)` -DLOOPBACK=$(Loopback) $< > $@

$(DB):	%.db:	%
	-postmap $<

/etc/postfix/aliases:	$(Covername)
	echo -e "root:\t${Local_Username}" > $@
	cat $(Covername) >> $@
	echo -e ":\t${Local_Username}" >> $@

$(Aliases):	/etc/postfix/aliases
	-postalias $<

$(Covername):	$(Addressbook)
	sqlite3 $< 'select covername from addressbook_address where is_me = 1;' | sed -e 's| |.|g;' | tr -d '\n' > $@

$(HC_Dir):
	mkdir -p $(HC_Dir)

$(HC_Sock):	$(HC_Dir)
	mkdir -p $(HC_Dir)
	chown hashcash-milter:postfix -R $(HC_Dir)
	su $(HC_User) -c "$(HC_Bin)" &
	while [[ ! -e $(HC_Sock) ]]; do sleep 3; done ;\
	chmod 775 $(HC_Sock) ;\
	chmod 775 $(HC_Dir) ;\
	chown hashcash-milter:postfix -R $(HC_Dir) &

clean:	stop
	-rm -f /etc/postfix/main.cf /etc/postfix/aliases /etc/postfix/local_recipients $(DB) $(Covername)
