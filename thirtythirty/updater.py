
import os
import re

import thirtythirty.utils
import thirtythirty.settings as TTS
import addressbook

import logging
logger = logging.getLogger(__name__)

class Updater(object):
    def __init__(self, Server=None, Cache=None):
        sServer = self._first_server()
        if Server:
            sServer = Server
        self.Cache = TTS.UPSTREAM['update_cache']
        if Cache:
            self.Cache = Cache
        if not os.path.exists(self.Cache):
            SO, SE = thirtythirty.utils.popen_wrapper(['/bin/mkdir', '--parents', self.Cache],
                                         sudo=False)            
        self.ReqMajor = TTS.LOOKINGGLASS_VERSION[0]
        self.ReqMinor = TTS.LOOKINGGLASS_VERSION[1]
        self.PatchLevel = TTS.LOOKINGGLASS_VERSION[2]
        self.moreRecentExists = False
        self.Available = self.Scan(sServer)


    def _first_server(self, Type='RSYNC'):
        for S in TTS.UPSTREAM['updates']:
            if ((S['type'] == Type) and (S.has_key('uri'))):
                return S['uri']
        return None


    def __repr__(self):
        CurrentMaj, CurrentMin, CurrentPatch = TTS.LOOKINGGLASS_VERSION
        if ((self.ReqMajor > CurrentMaj) or # major rev
            (self.ReqMajor == CurrentMaj) and # same major, bigger minor
            (self.ReqMinor > CurrentMin)):
            return """Running, %02d.%02d , Available, %02d.%02d""" % (
                CurrentMaj, CurrentMin,
                self.ReqMajor, self.ReqMinor)
        return '# Up to date.'


    def GetVersion(self, Major=None, Minor=None, Patch=None):
        ret = {}
        if not (Major or Minor or Patch):
            return None
        for S in self.Available:
            if ((S.has_key('Major') and (int(S['Major']) == int(Major))) and
                (S.has_key('Minor') and (int(S['Minor']) == int(Minor))) and
                (S.has_key('Patch') and (int(S['Patch']) == int(Patch)))):
                ret[S['Type']] = S
        if ret.has_key('sum') and ret.has_key('deb'):
            return ret
        elif ret.has_key('sum') and ret.has_key('tar.bz2'):
            return ret
        else:
            return None


    def GetMostRecent(self, asString=False):
        Major = self.ReqMajor
        Minor = self.ReqMinor
        Patch = self.PatchLevel
        GV = self.GetVersion(Major, Minor, Patch)
        if not asString:
            return GV
        elif GV is None:
            # FIXME: this is a lie
            return TTS.LOOKINGGLASS_VERSION_STRING
        elif GV.has_key('deb'):
            return 'LookingGlass V%02d.%02d.%02d' % (int(GV['deb']['Major']), int(GV['deb']['Minor']), int(GV['deb']['Patch']))
        elif GV.has_key('tar.bz2'):
            return 'LookingGlass V%02d.%02d.%02d' % (int(GV['tar.bz2']['Major']), int(GV['tar.bz2']['Minor']), int(GV['tar.bz2']['Patch']))


    def MoreRecentAvailable(self):
        return self.moreRecentExists

    
    def Scan(self, Server=None):
        """
        Return possible new versions via rsync

        Updates self.ReqMajor, self.ReqMinor to latest versions.
        """
        ret = []
        FNRE = re.compile(
            'LookingGlass_(?P<Major>[0-9]+)\.(?P<Minor>[0-9]+)\.(?P<Patch>[0-9]+)_(?P<Target>rpi|all).(?P<Type>sum|tar.bz2|deb)$')
        if Server:
            SO, SE = thirtythirty.utils.popen_wrapper(['/usr/bin/rsync', '--times', '%s/Upgrade' % Server],
                                         sudo=False)
            if re.search('closed', SE):
                return False
            for Line in SO.split('\n'):
                Z = FNRE.search(Line)
                if Z:
                    Q = {'Type':Z.group('Type'),
                         'Target':Z.group('Target')}
                    for X in ['Major', 'Minor', 'Patch']:
                        Q[X] = int(Z.groupdict()[X])
                    Q['Server'] = Server
                    Filename = re.sub('^.*LookingGlass_',
                                      'LookingGlass_',
                                      Line)
                    Q['Filename'] = Filename
                    Q['Exact'] = '%s/Upgrade/%s' % (Server,
                                                    Filename)
                    ret.append(Q)
                    if Q['Major'] > self.ReqMajor: self.moreRecentExists = True
                    elif ((Q['Major'] == self.ReqMajor) and
                        (Q['Minor'] > self.ReqMinor)): self.moreRecentExists = True
                    elif ((Q['Major'] == self.ReqMajor) and
                          (Q['Minor'] == self.ReqMinor) and
                          (Q['Patch'] > self.PatchLevel)): self.moreRecentExists = True
                    if self.moreRecentExists and Q['Type'] != 'sum':
                        self.ReqMajor = Q['Major']
                        self.ReqMinor = Q['Minor']
                        self.PatchLevel = Q['Patch']
                        logger.debug('found a more recent version: %02d.%02d.%02d' % (
                            Q['Major'], Q['Minor'], Q['Patch']))
            return ret
        else:
            return ret
            
        
    def Download(self, Major=None, Minor=None, Patch=None, Cache=None):
        if not (Major or Minor):
            Version_Info = self.GetMostRecent()
            Major = Version_Info['sum']['Major']
            Minor = Version_Info['sum']['Minor']
            Patch = Version_Info['sum']['Patch']
        else:
            Version_Info = self.GetVersion(Major=Major,
                                           Minor=Minor,
                                           Patch=Patch)
        cCache = self.Cache
        if Cache: cCache = Cache
        if Version_Info and cCache:
            for XT in ['deb', 'sum', 'tar.bz2']:
                if not Version_Info.has_key(XT): continue
                SO, SE = thirtythirty.utils.popen_wrapper(['/usr/bin/rsync',
                                              '--partial',
                                              '--times',
                                              Version_Info[XT]['Exact'],
                                              cCache],
                                             sudo=False)
                if re.search('closed', SE):
                    logger.error(SO, SE)
                    return False            
                if (SO, SE) != ('', ''):
                    logger.error(SO, SE)
                    return False
        return (Major, Minor, Patch)

            
    def ClearsignedBy(self):
        """
        Load the GPG key you're trying to verify into GPG before this...
        """
        Version_Info = self.GetVersion(Major=self.ReqMajor,
                                       Minor=self.ReqMinor,
                                       Patch=self.PatchLevel)
        Clearsign = file('%s/%s' % (self.Cache, Version_Info['sum']['Filename']), 'r').read()
        Verf = addressbook.gpg.verify_clearsign(Clearsign)
        if not Verf:
            return False
        logger.debug('GPG verified fingerprint %s' % Verf.pubkey_fingerprint)
        Type = 'deb'
        Sum = None
        for T in ['deb', 'tar.bz2']:
            if not Version_Info.has_key(T): continue
            Sum = re.search(
                '(?m)^(?P<SHA512>[a-f0-9]+)  %s$' % Version_Info[T]['Filename'],
                Clearsign)
            if Sum:
                Type = T
                break
        if not Sum:
            return False
        SO, SE = thirtythirty.utils.popen_wrapper(['sha512sum',
                                      '%s/%s' % (self.Cache,
                                                 Version_Info[Type]['Filename'])],
                                     sudo=False, debug=False)
        if SE != '':
            return False
        Sum_on_disk = re.search(
            '(?m)^(?P<SHA512>[a-f0-9]+)  %s$' % Version_Info[Type]['Filename'],
            Clearsign)
        if Sum.group(1) != Sum_on_disk.group(1):
            return False
        else:
            return Verf.pubkey_fingerprint


    def Validate(self, Fingerprint=None):
        """
        put the fingerprint/addressbook interaction here for arbitrary reasons - made more sense than the management script

        FIXME: if we get some wacky addr, we need to handle that exception...
        """
        A = addressbook.address.Address.objects.get(fingerprint=Fingerprint)
        if not A.system_use:
            logger.warning("%s comes off as a not-legit signer of this package..." % A.email)
        return A


    def Unpack(self, mode='tar'):        
        if mode == 'tar':
            return self.__tar_unpack()
        # elif mode == 'dpkg':
        #     return self.__dpkg_unpack()
        else:
            logger.critical('wtf mode of unpacking is `%s`?' % mode)
            return []


    def __tar_unpack(self):
        """
        FIXME: CONTROL section goes here
        /control.tar
         preinst
         postinst
        /data.tar
         root directory
        """
        Version_Info = self.GetVersion(Major=self.ReqMajor,
                                       Minor=self.ReqMinor,
                                       Patch=self.PatchLevel)
        File_List, Errors = thirtythirty.utils.popen_wrapper(
            ['/bin/tar',
             '--directory', '/',
             '-xvf',
             '%s/%s' % (self.Cache,
                        Version_Info['tar.bz2']['Filename'])])
        if Errors != '': return None
        return File_List.strip().split('\n')

    # def __dpkg_unpack(self):
    #     Version_Info = self.GetVersion(Major=self.ReqMajor,
    #                                    Minor=self.ReqMinor)
    #     SO, SE = thirtythirty.utils.popen_wrapper(
    #         ['/usr/bin/dpkg',
    #          '--install',
    #          '%s/%s' % (self.Cache,
    #                     Version_Info['deb']['Filename'])])
    #     if SE != '':
    #         logger.warning('dpkg says:', SE)
    #     return SO.split('\n')

    def Cleanup(self):
        logger.debug('cache cleanup')
        thirtythirty.utils.popen_wrapper(['/bin/rm', '-rf', self.Cache], sudo=False, debug=False)
