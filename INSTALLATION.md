# Install base packages

    # apt-get install python-qt4 python-pip parted cryptsetup parted tor postfix randomize-lines

# Install python dependencies

    $ virtualenv --no-site-packages .v
    $ source .v/bin/activate
    (.v) $ pip install -r requirements.txt
    (.v) $ pip install https://download.electrum.org/Electrum-2.4.4.tar.gz

# Create LVM disk partition

```
root@debian-jessie:/home/vagrant# fdisk -l /dev/sda

Disk /dev/sda: 500 GiB, 536870912000 bytes, 1048576000 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
root@debian-jessie:/home/vagrant# fdisk /dev/sda

Welcome to fdisk (util-linux 2.25.2).
Changes will remain in memory only, until you decide to write them.
Be careful before using the write command.

Device does not contain a recognized partition table.
Created a new DOS disklabel with disk identifier 0x034b6534.

Command (m for help): n
Partition type
   p   primary (0 primary, 0 extended, 4 free)
   e   extended (container for logical partitions)
Select (default p): 

Using default response p.
Partition number (1-4, default 1): 
First sector (2048-1048575999, default 2048): 
Last sector, +sectors or +size{K,M,G,T,P} (2048-1048575999, default 1048575999): 

Created a new partition 1 of type 'Linux' and of size 500 GiB.

Command (m for help): t
Selected partition 1
Hex code (type L to list all codes): 8e
Changed type of partition 'Linux' to 'Linux LVM'.

Command (m for help): w
The partition table has been altered.
Calling ioctl() to re-read partition table.
Syncing disks.
```

# Configure LUKS

    $ manage.py hdd --create-all --passphrase 1234
    $ manage.py migrate --database smp
    $ manage.py migrate --database ratcher

In order to check the filesystem status use ``lsblk --fs``

```
root@debian-jessie:/vagrant# lsblk --fs
NAME                         FSTYPE      LABEL UUID                                   MOUNTPOINT
sda
└─sda1                       LVM2_member       AuVE7K-sY0i-w0DR-LClg-30lH-HU77-jrUx8P
  ├─LookingGlass-tor_var     crypto_LUKS       1ecba0f2-3444-4040-8f05-bf29aa86aa9b
  │ └─tor_var                ext4              32991f16-df8a-4308-8009-038abf2b1f08   /var/lib/tor
  ├─LookingGlass-pi_electrum crypto_LUKS       3ff38677-08e7-474d-b445-88f55d7ad5c0
  │ └─pi_electrum            ext4              9962ccca-2b84-4e39-b380-b839c5b09e36   /home/vagrant/.electrum
  ├─LookingGlass-pi_gpg      crypto_LUKS       8e637e21-3fba-40eb-b746-53026e7ba58c
  │ └─pi_gpg                 ext4              1b758100-c678-4de5-8546-0698803c59eb   /home/vagrant/.gnupg
  ├─LookingGlass-pi_mail     crypto_LUKS       141bfd54-abe7-42f5-9a40-cb9244ac0d5b
  │ └─pi_mail                ext4              47fdc2f6-1ebc-4dba-b474-41a9518d2cc0   /home/vagrant/Maildir
  └─LookingGlass-postfix_etc crypto_LUKS       c3e3490a-efaf-4f24-b0bf-8a92a97113fe
    └─postfix_etc            ext4              44f49deb-4ec7-455b-9497-5737e5c818be   /etc/postfix
```

# Configure tor

https://www.thecthulhu.com/setting-up-a-hidden-service-with-nginx/

# GPG

After installed tor and cheched that the hostname is generate in ``/var/lib/tor/hidden_service/hostname``

    $ python manage.py migrate --database addressbook
    $ python manage.py gpginit --genkey --passphrase 1234 --covername EMPTYUID --hostname `sudo /bin/cat /var/lib/tor/hidden_service/hostname`
    ... wait several minutes (like 20 minutes using vagrant) ...