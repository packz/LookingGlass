#! /bin/bash

Hosts='/etc/hosts'

HSName='/var/lib/tor/hidden_service/hostname'

Hostname=`cat ${HSName}`
HostOnly=`cat ${HSName} | sed -e 's|.onion||g'`


if ( grep -q "${HSName}" ${Hosts} ); then
    First_Run=''
else
    First_Run='raspberrypi lookingglass'
fi

/bin/cat <<EOF > ${Hosts}
127.0.0.1	localhost ${First_Run} ${Hostname} ${HostOnly}

::1		localhost ip6-localhost ip6-loopback
fe00::0		ip6-localnet
ff00::0		ip6-mcastprefix
ff02::1		ip6-allnodes
ff02::2		ip6-allrouters
EOF
