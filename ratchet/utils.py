
from os import urandom
from random import randrange
from re import compile as REC, search
from types import DictType, UnicodeType

import binascii
import json

from ratchet.exception import Broken_Format

import thirtythirty.settings as TTS

def human_readable(crazy_binary_data=None,
                   drop_octets=False):
        """
        Chunkulate for human consumption
        """
        if not crazy_binary_data:
                return 'I SEE NOTHING'
        raw = binascii.hexlify(crazy_binary_data)
        if search('^[a-fA-F0-9]+$', crazy_binary_data):
                # is hex already
                raw = crazy_binary_data
        cooked = ''
        if drop_octets:
                for i in range(0, len(raw), 4):
                        cooked += raw[i:i+2] + ':'
        else:
                for i in range(0, len(raw), 4):
                        cooked += raw[i:i+4] + ':'
        return cooked[:-1]


def hulk_smash_unicode(string_of_death=None):
	if type(string_of_death) is not UnicodeType:
		return string_of_death
	return string_of_death.encode('ascii', errors='xmlcharrefreplace')


class b64Formatter(object):
    def __init__(self,
                 str_format='%s%s',
                 re_format='(?<Payload>.*)',
                 repr_show=None,
                 ):
        """
        repr_show list is attributes that get coughed out on print
        """
	if not repr_show: repr_show = []
        self.__str_format = str_format
        self.__re_format = REC(re_format)
        self.__repr_show = repr_show


    def __fold_to_width(self, fold='',
                        width=64):
        return '\n'.join(
            [ fold[i:i+width] for i in xrange(0, len(fold), width) ]
            )


    def __repr__(self):
        """
        preface fields in the repr_show list
        with 'NOHEX_' to get the raw value
        rather than the hexlified value
        """
        ret = u'[%s]\n' % type(self).__name__
        for K in self.__repr_show:
            if not hasattr(self, K): continue
            if K[:6] == 'NOHEX_' and getattr(self, K[6:]) is not None:
                ret += '%s: %s\n' % (K[6:], getattr(self, K[6:]))
            elif getattr(self, K) is not None:
                ret += '%s: %s\n' % (K, binascii.hexlify(getattr(self, K)))
        return ret


    def deserialize(self, msg=''):
        """
        Message() format:
          b2a/json -> [header|payload]/b2a -> encryption -> json/b2a

        EncryptedHandshake() format:
          b2a -> encryption -> json/b2a
        """
        ParseMe = msg
        Format = self.__re_format.search(msg)
        if Format: ParseMe = Format.group('Payload')
        try: return json.loads(
                binascii.a2b_base64(
                        ParseMe))
        except ValueError:  pass
        except binascii.Error: pass
        try: return json.loads(
            ParseMe)
        except ValueError: pass
        try: return binascii.a2b_base64(
            ParseMe)
        except:
            raise(Broken_Format(
                    'For the life of me, I cannot parse this %s' % type(self).__name__))


    def serialize(self,
                  Payload=None,
                  b64=True,
                  Format=True,):
        """
        Message()s may be pyaxo-compatible
        but there isn't a Handshake() spec for pyaxo
        so again, pushing actual dumps() to subclass
        """
	if not Payload: Payload = {}
        sPayload = Payload
        if type(Payload) is DictType:
            sPayload = json.dumps(Payload)
        if not b64: return sPayload
        bPayload = binascii.b2a_base64(sPayload)
        if not Format: return bPayload
        else:
            fPayload = self.__fold_to_width(bPayload)
            return self.__str_format % (TTS.LOOKINGGLASS_VERSION_STRING, fPayload) 


    def to_b64(self, Payload=None):
        """
        fields in the payload prefaced with 'b64_'
        are b64 encoded

        special key 'nonce' is filled with random bytes
        up to the amount specified in the 'nonce' field

        everything else goes straight through
        """
	if not Payload: Payload = {}
        bPayload = {}
        for Key, Value in Payload.items():
	    if Key[:4] == 'b64_':
	        bPayload[Key] = binascii.b2a_base64(
			hulk_smash_unicode(Value)
			).strip()
            elif Key == 'nonce':
                bPayload[Key] = binascii.b2a_base64(
                    urandom(randrange(Value))).strip()
            else:
                bPayload[Key] = hulk_smash_unicode(Value)
        return bPayload


    def from_b64(self, bPayload=None):
        """
        drops nonce values
        
        decodes fields prefaced by 'b64_' and
        strips that identifier
        """
        if type(bPayload) is not DictType:
                return None
        Payload = {}
        for Key, Value in bPayload.items():
            if Key[:4] == 'b64_':
                Payload[Key[4:]] = binascii.a2b_base64(Value)
            elif Key == 'nonce':
                continue
            else:
                Payload[Key] = Value
        return Payload
