#! /bin/bash

PPC='/run/shm/passphrase_cache'

if [[ -e ${PPC} ]]; then
    read NewPW < ${PPC}
    echo "pi:${NewPW}" | chpasswd
else
    echo "${PPC} does not exist."
fi
