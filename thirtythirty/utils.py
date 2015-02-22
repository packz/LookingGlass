
import re
import subprocess
import os.path
import tempfile

import addressbook
import thirtythirty.settings as TTS

from electrum import SimpleConfig, wallet

import logging
logger = logging.getLogger(__name__)

def Vitals(request=None):
    Electrum_Data = '/home/%s/.electrum/wallets/default_wallet' % TTS.USERNAME
    
    ret = {
        'covername':'REX DART',
        'email':'rex.dart',
        'ircname':'rex_dart',
        'onion':'tns7i5gucaaussz4.onion',
        'server_addr':'127.0.0.1',
        'tor_fp':'NOT SURE',
        'gpg_fp':addressbook.utils.my_address().fingerprint,
        'btc_mpk':'NOT SURE',
        }

    if request:
        ret['server_addr'] = request.get_host()

    Me = addressbook.utils.my_address()
    ret['covername'] = Me.covername
    ret['ircname'] = re.sub(' ', '_', Me.covername)
    ret['email'] = Me.email
    ret['onion'] = re.sub('^[^@]+', '', Me.email)

    try:
        ret['tor_fp'] = re.sub('^[^\W]+ ', '',
                               subprocess.check_output(['sudo', '-u', 'root',
                                                        '/bin/cat',
                                                        '/var/lib/tor/fingerprint'])).rstrip()
    except: pass

    if os.path.exists(Electrum_Data):
        Config = SimpleConfig()
        ret['btc_mpk'] = wallet.WalletStorage(Config).get('master_public_key')
    return ret


def IP_Info(in_particular=None, interface='eth0'):
    """
    if we need a specific entry, return just that entry
    otherwise, return everything we found about the interface
    """
    ret = {}
    for Line in subprocess.check_output(['route', '-n']).split('\n'):
        GW_Finder = re.search('^0.0.0.0\W+(?P<Gateway>[\.0-9]+)\W+', Line)
        if GW_Finder:
            for X, Y in GW_Finder.groupdict().items():
                ret[X] = Y
    for Line in subprocess.check_output(['ifconfig', interface]).split('\n'):
        IP_Scan = re.search('inet addr:(?P<Address>[\.0-9]+).*Mask:(?P<Netmask>[\.0-9]+)', Line)
        if IP_Scan:
            for X, Y in IP_Scan.groupdict().items():
                ret[X] = Y
    if in_particular and ret.has_key(in_particular):
        return ret[in_particular]
    elif in_particular:
        return None
    return ret


def HS_Name():
    """
    because we're going through sudo, we can't use os.path.exists...
    """
    try:
        name = subprocess.check_output(['/usr/bin/sudo', '-u', 'root',
                                        '/bin/cat', '/var/lib/tor/hidden_service/hostname'])
        return name[:-1].upper()
    except:
        return False


def query_daemon_states(specifically=None):
    ret = TTS.DAEMONS
    for X in ret:
        if specifically and X['name'] != specifically: continue
        X['running'] = False
        try:
            subprocess.check_call(X['check'])
            X['running'] = True
            if specifically: return True
        except: pass
    if specifically: return False
    return ret


def popen_wrapper(arglist=None, stdin=None,
                  sudo=True,
                  debug=True):
    """
    http://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/

    Can't use StringIO here, /usr/bin/make will often crap out a bunch of stuff.
    """
    if not arglist: arglist = []
    SO = tempfile.NamedTemporaryFile()
    SE = tempfile.NamedTemporaryFile()
#    if debug:
#        logger.debug('tempfiles: %s, %s' % (SO.name, SE.name))
    if sudo:
        Cmd = ['/usr/bin/sudo', '-u', 'root']
        Cmd.extend(arglist)
    else:
        Cmd = arglist
    if debug:
        logger.debug(Cmd)
    if stdin:
        Current = subprocess.Popen(Cmd,
                                   stderr=SE,
                                   stdout=SO,
                                   stdin=subprocess.PIPE)
        Current.communicate(stdin)
        SO.seek(0)
        SE.seek(0)
        return (SO.read(), SE.read())
    else:
        Current = subprocess.Popen(Cmd,
                                   stderr=SE,
                                   stdout=SO)
        Current.communicate(None)
        SO.seek(0)
        SE.seek(0)
        return (SO.read(), SE.read())
