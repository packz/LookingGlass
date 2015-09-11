#! /bin/bash

Sudo='/usr/bin/sudo -u root'

Maildir_LV='/dev/LookingGlass/pi_mail'
Maildir_CD='/dev/mapper/pi_mail'

if [[ ! -e ${Maildir_CD} ]]; then
    echo "cryptdisk ${Maildir_CD} needs to be unlocked to run this..."
    exit -1
fi

Maildir_Percent=`df | awk '/pi_mail/ { print $5 }' | sed -e 's|%||g'`

if [[ ${Maildir_Percent} -gt 50 ]]; then
    ${Sudo} /sbin/lvextend -L+1G ${Maildir_LV}
    ${Sudo} /sbin/cryptsetup resize ${Maildir_CD}
    ${Sudo} /sbin/resize2fs ${Maildir_CD}
else
    echo 'Plenty of email space remains.'
fi