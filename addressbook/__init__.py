
import thirtythirty.settings as TTS

import gnupg
GPG = gnupg.GPG(gnupghome=TTS.GPG['root'],
                options=TTS.GPG['options'])
GPG.encoding = TTS.GPG['encoding']

import addressbook.exception
import addressbook.address
import addressbook.covername
import addressbook.gpg
import addressbook.queue
import addressbook.utils
