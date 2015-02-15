
from binascii import hexlify, unhexlify
from os import urandom
from struct import unpack_from
from types import StringType

import addressbook
import ratchet

class Message(ratchet.utils.b64Formatter):
    def __init__(self,
                 HeaderKey = None,
                 MessageKey = None,
                 NumberTx = 0,
                 DHRatchetTx = None,
                 Payload = None,
                 Ciphertext = None):
        self.HeaderKey = None
        self.MessageKey = None
        self.NumberTx = NumberTx
        self.DHRatchetTx = DHRatchetTx
        self.Payload = Payload
        self.Ciphertext = Ciphertext
        self.__gpg_header = unhexlify('8c0d04090308')
        sFormat = """-----BEGIN AXOLOTL MESSAGE-----
Version: %s

%s-----END AXOLOTL MESSAGE-----"""
        rFormat = """(?smx) # dotall, multiline, verbose
^\-\-\-\-\-BEGIN\ AXOLOTL\ MESSAGE\-\-\-\-\-\W
^Version:\ [^\n]+\W+
^\W+
^(?P<Payload>.+)\W+
^\-\-\-\-\-END\ AXOLOTL\ MESSAGE\-\-\-\-\-"""
        Fields = [
            'HeaderKey',
            'MessageKey',
            'NOHEX_NumberTx',
            'DHRatchetTx',
            'NOHEX_Payload',
            'Ciphertext',
            ]
        super(Message, self
              ).__init__(str_format = sFormat,
                         re_format = rFormat,
                         repr_show = Fields)
        self.set_keys(HeaderKey=HeaderKey,
                      MessageKey=MessageKey)


    def set_keys(self,
                 HeaderKey=None,
                 MessageKey=None):
        """
        When we try new keys, automatically attempt loads()
        """
        if HeaderKey: self.HeaderKey = hexlify(HeaderKey)
        if MessageKey: self.MessageKey = hexlify(MessageKey)
        if self.Ciphertext: self.loads()

        
    def loads(self, msg=None):
        """
        Note there are situations that only 1/2 the msg may be decrypted
        ie - just the header
        """
        if not msg: msg = self.Ciphertext
        try: Wrapper = self.deserialize(msg)
        except ratchet.exception.Broken_Format: Wrapper = None # maybe pyaxo mode

        # if we can parse the b64 JSON
        if Wrapper:
            # denestening
            Unwrapped = self.from_b64(Wrapper)
            if self.HeaderKey:
                xHeader = addressbook.gpg.decrypt(Unwrapped['Header'],
                                                  passphrase=self.HeaderKey).data
                try:  # we need to tolerate bruting keys that may not work
                    bHeader = self.deserialize(xHeader)
                    Header = self.from_b64(bHeader)
                    if Header is not None:
                        self.NumberTx = Header['NumberTx']
                        self.DHRatchetTx = Header['DHRatchetTx']
                except ValueError: pass
                except ratchet.exception.Broken_Format: pass
            if self.MessageKey:
                xPayload = addressbook.gpg.decrypt(Unwrapped['Payload'],
                                                   passphrase=self.MessageKey).data
                try:  # we need to tolerate bruting keys that may not work
                    bPayload = self.deserialize(xPayload)
                    Payload = self.from_b64(bPayload)
                    self.Payload = Payload['Payload']
                except ValueError: pass
                except TypeError:
                    # GIBBERISH!
                    pass
                except ratchet.exception.Broken_Format: pass
            
        elif ((type(msg) is StringType) and (len(msg) > 106)): # pyaxo mode?
            pad_length = ord(msg[105:106])
            if self.HeaderKey:
                Header = addressbook.gpg.decrypt(self.__gpg_header +\
                                                 msg[:106 - pad_length],
                                                 passphrase=self.HeaderKey).data
                if Header != '':
                    self.NumberTx = int(Header[:3])
                    self.DHRatchetTx = Header[6:]
            if self.MessageKey:
                self.Payload = addressbook.gpg.decrypt(self.__gpg_header + msg[106:],
                                                       passphrase=self.MessageKey).data
            
            

    def dumps(self, pyaxo_compat=False):
        if not pyaxo_compat:
            # first, we armor the binary data
            bHeader = self.to_b64({
                'NumberTx':self.NumberTx,
                'b64_DHRatchetTx':self.DHRatchetTx,
                'nonce':100,
                })
            bPayload = self.to_b64({
                'b64_Payload':self.Payload,
                'nonce':100,
                })
            # next, we serialize to JSON
            jHeader = self.serialize(Format=False, Payload=bHeader)
            jPayload = self.serialize(Format=False, Payload=bPayload)
            # now we encrypt it
            eHeader = addressbook.gpg.symmetric(jHeader,
                                                passphrase=self.HeaderKey,
                                                armor=False).data
            ePayload = addressbook.gpg.symmetric(jPayload,
                                                 passphrase=self.MessageKey,
                                                 armor=False).data
            # nesting the data so it's easier to pull apart
            Wrapped = self.to_b64({
                'b64_Header':eHeader,
                'b64_Payload':ePayload,
                'nonce':100,
                })
            # one last serialization to JSON
            return self.serialize(Wrapped)
        
        else:  # pyaxo mode
            # cast from buffer (SQLite) to str (pyaxo)
            Unpack = ''.join(unpack_from('c'*32, self.DHRatchetTx))
            UnholyMatrimony = str(self.NumberTx).zfill(3) +\
                              str(0).zfill(3) +\
                              Unpack
            Header = addressbook.gpg.symmetric(UnholyMatrimony,
                                               passphrase=self.HeaderKey,
                                               armor=False).data
            # SIX BYTES
            Trim_Header = Header[6:]
            Body = addressbook.gpg.symmetric(self.Payload,
                                             passphrase=self.MessageKey,
                                             armor=False).data
            # DON'T FORGET THOSE SIX BYTES.
            Trim_Body = Body[6:]
            pad_length = 106 - len(Trim_Header)
            # now add 8x those saved bytes back
            pad = urandom(pad_length - 1) + chr(pad_length)
            return Trim_Header + pad + Trim_Body
