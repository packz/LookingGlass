
from django.core.exceptions import MultipleObjectsReturned

import re
from types import StringType

import address
import exception

def msg_type(msg=None):
    """
    Returns False on 'no data'
    None on IDKWTF this is BBQ
    """
    import re
    if type(msg) is not StringType: return False
    if re.search('BEGIN PGP MESSAGE', msg):
        return 'PGP-MSG'
    elif re.search('BEGIN PGP SIGNED MESSAGE', msg):
        return 'PGP-CLEARSIGN'
    elif re.search('BEGIN AXOLOTL HANDSHAKE', msg):
        return 'AXO-HS'
    elif re.search('BEGIN AXOLOTL MESSAGE', msg):
        return 'AXO-MSG'
    else:
        return None
    

def my_address():
    try:
        return address.Address.objects.get(is_me=True)
    except MultipleObjectsReturned:
        raise(exception.Multiple_Private_Keys('You appear to have multiple private keys.  I am too hastily coded to handle that properly.'))
