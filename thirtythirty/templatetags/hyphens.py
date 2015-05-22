
from django import template

from types import ListType, StringType

import addressbook.address
import addressbook.utils

register = template.Library()

@register.filter
def get_flags(Msg):
    return [ letter for letter in Msg.get_flags() ]


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def nickname(MsgTo):
    try:
        A = addressbook.address.Address.objects.get(email__iexact=MsgTo)
    except addressbook.address.Address.DoesNotExist:
        return MsgTo
    if A.nickname != None: return A.nickname
    if A.covername != None: return A.covername
    return MsgTo


@register.filter
def message_type(aMsg):
    """
    Well, this is hideous.
    """
    Payload = aMsg.get_payload()
    if type(Payload) is ListType:
        Payload = Payload[0]
    if type(Payload) is not StringType:
        Payload = str(Payload)
    return addressbook.utils.msg_type(Payload)


@register.filter
def format_date(msgDate, format='%d%b%yZ%H%M'):
    """
    can handle a datetime tuple, or a email date string
    """
    from email.utils import parsedate
    from time import strftime, gmtime
    if type(msgDate) is tuple:
        return strftime(format, msgDate)
    elif type(msgDate) is str:
        try:
            return strftime(format,
                            parsedate(msgDate))
        except:
            return '0000-00-00'
    else:
        try:
            return strftime(format,
                            parsedate(msgDate['date']))
        except:
            return '0000-00-00'

@register.filter
def message_key(aMsg):
    from emailclient.filedb import msg_key_from_msg
    return msg_key_from_msg(aMsg)
