
smtpd_banner = HOSTNAME ESMTP (secret)
biff = no
append_dot_mydomain = no
readme_directory = no

# realistic retry intervals
maximal_queue_lifetime = 4d
maximal_backoff_time   = 15m
minimal_backoff_time   = 5m
queue_run_delay        = 3m

# sometimes it takes a bit to fire up an HS connection
smtp_connect_timeout   = 5m
smtp_helo_timeout      = 5m

# if we get a bounce msg, let us know right away
bounce_queue_lifetime  = 0

# friendly up the bounce msgs - http://www.postfix.org/bounce.5.html
#bounce_template_file = /etc/postfix/bounce.cf

# TLS parameters
smtpd_tls_cert_file=/etc/ssl/certs/LookingGlass.crt.pem
smtpd_tls_key_file=/etc/ssl/private/LookingGlass.pem
smtpd_use_tls=yes
smtpd_tls_session_cache_database = btree:${data_directory}/smtpd_scache
smtp_tls_session_cache_database = btree:${data_directory}/smtp_scache

ifelse(WITH_HASHCASH, 1, `
# hashcash
milter_content_timeout = 600
smtpd_milters = unix:/hashcash-milter/hashcash.sock
non_smtpd_milters = unix:/hashcash-milter/hashcash.sock
milter_default_action = tempfail
local_recipient_maps = hash:/etc/postfix/local_recipients
')

# .onion
ignore_mx_lookup_error = yes
mime_header_checks = regexp:/etc/postfix/header_checks
header_checks = regexp:/etc/postfix/header_checks
inet_interfaces = 127.0.0.1,LOOPBACK
inet_protocols = ipv4

# we may turn this on in the future for mixmastery
#relay_domains = HOSTNAME
#relayhost =
#relay_recipient_maps = hash:/etc/postfix/relay_recipient_maps

myhostname = HOSTNAME
mydomain = HOSTNAME
myorigin = HOSTNAME
alias_maps = hash:/etc/postfix/aliases
alias_database = hash:/etc/postfix/aliases
mynetworks = 127.0.0.1
mailbox_size_limit = 0
recipient_delimiter = +
home_mailbox = Maildir/

mailbox_command = /usr/bin/procmail -a "$EXTENSION" DEFAULT=$HOME/Maildir/ MAILDIR=$HOME/Maildir
