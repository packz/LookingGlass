
from django.db import models
from django.contrib.auth.models import User

import hashcash
import uuid

class preferences(models.Model):
    """
    user preferences
    """
    ooser = models.OneToOneField(User)
    show_advanced = models.BooleanField(default=False)

    # this is crontab(5) format
    # minute / hour / dom / month / dow
    HHOUR  = '0,30 * * * *'
    HOURLY = '@hourly'
    HOUR3  = '0 */3 * * *'
    HOUR12 = '0,12 * * * *'
    DAILY  = '@daily'
    passphrase_cache_timeouts = (
        (HHOUR, 'Every half hour'),
        (HOURLY, 'On the hour'),
        (HOUR3, 'Every 3 hours'),
        (HOUR12, 'At noon and midnight'),
        (DAILY, 'At midnight'),
        )
    passphrase_cache = models.BooleanField(default=True)
    passphrase_cache_time = models.CharField(max_length=20,
                                             default=HHOUR,
                                             choices=passphrase_cache_timeouts)

    # making your mail client more client-y
    tx_symmetric_copy = models.BooleanField(default=False)
    rx_symmetric_copy = models.BooleanField(default=False)

    # oh, yeah.  IP ranges...
    DYNAMIC_IP = 'DHCP'
    STATIC_IP  = 'Static'
    ip_types = (
        (DYNAMIC_IP, 'DHCP'),
        (STATIC_IP, 'Static IP'),
        )
    ip_address_type = models.CharField(max_length=7,
                                       default=DYNAMIC_IP,
                                       choices=ip_types)

    ip_addr = models.GenericIPAddressField(protocol='IPv4', default='0.0.0.0')
    netmask = models.GenericIPAddressField(protocol='IPv4', default='0.0.0.0')
    gateway = models.GenericIPAddressField(protocol='IPv4', default='0.0.0.0')


    def set_ip(self, IP=None, NM=None, GW=None):
        """
        FIXME: Sanity check the addrs here
        """
        if IP: self.ip_addr = IP
        if NM: self.netmask = NM
        if GW: self.gateway = GW
        self.save()


class LRLManager(models.Manager):
    def token(self):
        T = str(uuid.uuid4())[-8:]
        LRL = self.create(challenge=T)
        return LRL
        

class LoginRateLimiter(models.Model):
    challenge = models.CharField(max_length=8, null=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    redeemed = models.BooleanField(default=False)

    objects = LRLManager()

    def verify(self, stamp=None, bits=10):
        if self.redeemed:
            return False
        HCC = hashcash.check(stamp,
                             resource=self.challenge,
                             check_expiration=hashcash.DAYS * 3,
                             bits=bits)
        if HCC is True:
            self.redeemed = True
            self.save()
            return True
        return False
