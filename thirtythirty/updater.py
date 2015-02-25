
import os
import re
import subprocess

from emailclient.utils import submit_to_smtpd

import thirtythirty.exception as TTE
import thirtythirty.utils as TTU
import thirtythirty.settings as TTS
import addressbook

import logging
logger = logging.getLogger(__name__)        

def Scan(Server=None):
    """
    rsync scan the update server
    return highest patch > current, with checksum
    """
    Biggest = "%02d%02d%02d" % TTS.LOOKINGGLASS_VERSION
    Checksum = True
    Tarball = True
    Exact = None
    
    FNRE = re.compile(
        'LookingGlass_(?P<Major>[0-9]+)\.(?P<Minor>[0-9]+)\.(?P<Patch>[0-9]+)_(?P<Target>rpi|all).(?P<Type>sum.asc|tar.bz2|deb)$')
    if Server:
        SO, SE = TTU.popen_wrapper(['/usr/bin/rsync',
                                    '%s/Upgrade' % Server],
                                   sudo=False)
    if re.search('closed', SE):
        raise TTE.ScanException('Cannot connect to %s' % Server)
    
    for Line in sorted(SO.split('\n')):
        Z = FNRE.search(Line)
        if not Z: continue
        Version = "%02d%02d%02d" % (
            int(Z.group('Major')),
            int(Z.group('Minor')),
            int(Z.group('Patch')),
            )
        if Version > Biggest:
            Biggest = Version
            Checksum = False
            Tarball = False

        if Version == Biggest:
            if Z.group('Type') == 'sum.asc':
                Checksum = True
            elif Z.group('Type') == 'tar.bz2':
                Tarball = True
                Filename = re.sub('^.*LookingGlass_',
                                  'LookingGlass_',
                                  Line)
                Exact = '%s/Upgrade/%s' % (Server,
                                           Filename)

    if Exact and Checksum and Tarball:
        return Exact
    else:
        return None


def Cache(Data_URI=None,
          Checksum_URI=None,
          Cache=None,
          ):
    """
    rsync tarball and checksum to cache directory
    return filename of data file
    """
    if not Cache:
        Cache = TTS.UPSTREAM['update_cache']
    if not Checksum_URI:
        Checksum_URI = re.sub('\.tar\.bz2$', '.sum.asc', Data_URI)
    if not os.path.exists(Cache):
        TTU.popen_wrapper(['/bin/mkdir',
                           '--parents',
                           Cache],
                          sudo=True)
    for GetFile in [Data_URI, Checksum_URI]:
        SO, SE = TTU.popen_wrapper(['/usr/bin/rsync',
                                    '--times',
                                    GetFile,
                                    Cache],
                                   sudo=False)
        if (SO, SE) != ('', ''):
            raise TTE.DownloadException(SE)
    return '%s/%s' % (Cache, re.sub('^.*LookingGlass_', 'LookingGlass_', Data_URI))


def ChangeLog(Filename=None):
    if not Filename:
        Filename = __data_file()
    ChangeLog, STE = TTU.popen_wrapper(['/bin/tar',
                                        '-xOf', Filename, # O to stdout
                                        'ChangeLog'],
                                       sudo=False)
    if ((ChangeLog == '') or (STE != '')):
        logger.info('No ChangeLog')
        return False
    else:
        return ChangeLog


def Version(Filename=None):
    if not Filename:
        Filename = __data_file()
    V = re.search('_(?P<version>[.0-9]+)_', Filename)
    if V:
        return V.group('version')
    return None


def __data_file():
    for File in sorted(os.listdir(TTS.UPSTREAM['update_cache']), reverse=True):
        if re.search('\.tar\.bz2$', File):
            return '%s/%s' % (TTS.UPSTREAM['update_cache'], File)
    return None


def __checksum_file():
    for File in sorted(os.listdir(TTS.UPSTREAM['update_cache']), reverse=True):
        if re.search('\.sum\.asc$', File):
            return '%s/%s' % (TTS.UPSTREAM['update_cache'], File)
    return None


def Available():
    """
    this could probably be a whole lot smarter
    """
    D = __data_file()
    if D:
        return Version(D)
    else:
        return None
    

def Validate(Data_File=None,
             Checksum_File=None):
    """
    Verify that SHA512 are the same, and that signature comes from a system_use key
    """
    if not Data_File:
        Data_File = __data_file()
    if not Checksum_File:
        Checksum_File = __checksum_file()
    if not Data_File or not os.path.exists(Data_File):
        raise TTE.ChecksumException("Data file %s doesn't exist" % Data_File)
    if not Checksum_File or not os.path.exists(Checksum_File):
        raise TTE.ChecksumException("Checksum file %s doesn't exist" % Checksum_File)
    
    SO, SE = TTU.popen_wrapper(['sha512sum',
                                Data_File],
                               sudo=False,
                               debug=False)
    Local_Sum = re.search(
        '(?m)^(?P<SHA512>[a-f0-9]{128})\W+',
        SO)
    if not Local_Sum:
        raise TTE.ChecksumException("Can't parse checksum: %s/%s" % (SO, SE))
    Local_Sum = Local_Sum.group('SHA512')

    # signed checksums shouldn't be much bigger than 1000 bytes
    Clearsign = file(Checksum_File, 'r').read(1000)
    Signer_FP = addressbook.gpg.verify_clearsign(Clearsign)
    if not Signer_FP:
        raise TTE.SignatureException('Bogus or enormous fingerprint')
    Signer_FP = Signer_FP.pubkey_fingerprint
    A = addressbook.address.Address.objects.filter(fingerprint=Signer_FP,
                                                   system_use=True
                                                   )
    if A.count() != 1:
        raise TTE.SignatureException("Package signed by unknown FP: %s" % Signer_FP)
    logger.debug('Package signed by %s' % A[0].email)
    Clearsign_Sum = re.search(
        '(?m)^(?P<SHA512>[a-f0-9]{128})\W+',
        Clearsign)
    if not Clearsign_Sum:
        raise TTE.ChecksumException("Can't parse checksum: %s" % Clearsign)
    Clearsign_Sum = Clearsign_Sum.group('SHA512')

    if Local_Sum == Clearsign_Sum:
        return Local_Sum
    else:
        return False


def Unpack(Data_File=None):
    Preinst  = '%s/%s' % (TTS.UPSTREAM['update_script_dir'], 'preinst')
    Postinst = '%s/%s' % (TTS.UPSTREAM['update_script_dir'], 'postinst')

    if not Data_File:
        Data_File = __data_file()
    if not Data_File or not os.path.exists(Data_File):
        raise TTE.UnpackException("Can't find Data_File %s" % Data_File)

    # unpack the control.tar preinst
    File_List, Errors = TTU.tar_pipeline(
        arglist1=['/bin/tar',
                  '-xvOf', Data_File, # O to stdout
                  'control.tar'],
        arglist2=['/bin/tar',
                  '--directory', TTS.UPSTREAM['update_script_dir'],
                  '-xvf', '-'],
        )
    for F in File_List.split('\n'):
        logger.debug(F)
    if Errors != '':
        raise TTE.PreInstException('control.tar unpacking problem: %s' % Errors)

    # run-parts the preinst
    if os.path.exists(Preinst):
        STO, STE = TTU.popen_wrapper(
            ['/bin/run-parts',
             '--exit-on-error',
             '--report',
             Preinst,
             ])
        if (STO, STE) != ('', ''):
            raise TTE.PreInstException('trouble in the preinst: %s' % STE)

    # unpack the data.tar into root
    File_List, Errors = TTU.tar_pipeline(
        arglist1=['/bin/tar',
                  '--directory', '/tmp',
                  '-xvOf', Data_File, # O to stdout
                  'data.tar'],
        arglist2=['/usr/bin/sudo', '-u', 'root', # well, this is like handing the user a gun...
                  '/bin/tar',
                  '--directory', '/',
                  '--no-overwrite-dir', # so we don't accidentally hose up directory perms
                  '-xvf', '-'],
        )
    submit_to_smtpd(
        Destination='root@localhost',
        Payload=File_List,
        Subject='Installed files from update to %s' % Version(Data_File),
        From='Sysop <root>',
        )
    # FIXME: email the file list to the admin?
    if Errors and not re.search('Removing\ leading', Errors):
        raise TTE.UnpackException('data.tar unpacking problem: %s' % Errors)

    # run-parts the control.tar postinst
    if os.path.exists(Postinst):
        STO, STE = TTU.popen_wrapper(
            ['/bin/run-parts',
             '--exit-on-error',
             '--report',
             Postinst,
             ])
        if (STO, STE) != ('', ''):
            raise TTE.PostInstException('trouble in the postinst: %s' % STE)

    return True

    
def Cleanup():
    logger.debug('cache cleanup')
    TTU.popen_wrapper(['/bin/rm', '-rf',
                       TTS.UPSTREAM['update_cache']
                       ], sudo=False, debug=False)
    TTU.popen_wrapper(['/bin/rm', '-rf',
                       '%s/postinst' % TTS.UPSTREAM['update_script_dir']
                       ], sudo=False, debug=False)
    TTU.popen_wrapper(['/bin/rm', '-rf',
                       '%s/preinst' % TTS.UPSTREAM['update_script_dir']
                       ], sudo=False, debug=False)
                       
