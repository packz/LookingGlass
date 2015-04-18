
import os
import re
import subprocess
import tempfile

from emailclient.utils import submit_to_smtpd

import thirtythirty.exception as TTE
import thirtythirty.utils as TTU
import thirtythirty.settings as TTS
import addressbook

import logging
logger = logging.getLogger('thirtythirty')

def Scan(Server=None):
    """
    rsync scan the update server
    return highest patch > current, with checksum
    """
    Biggest = "%02d%02d%02d" % TTS.LOOKINGGLASS_VERSION
    Current = "%02d%02d%02d" % TTS.LOOKINGGLASS_VERSION
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

        if ((Version == Biggest) and (Biggest != Current)):
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


def Update_Cache(Data_URI=None,
                 Checksum_URI=None,
                 Cache=None,
                 ):
    """
    rsync tarball and checksum to cache directory
    return filename of data file

    FIXME: this should be made file agnostic, and just process a list - bug #90652295
    """
    if not Data_URI:
        return False
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
    if ((D) and (Version(D) > "%02d.%02d.%02d" % TTS.LOOKINGGLASS_VERSION)):
        return {
            'version':Version(D),
            'filename':D,
            }
    else:
        return None
    

def Validate(Data_File=None,
             Checksum_File=None,
             Debug=True):
    """
    Verify that Checksum is the same, and that signature comes from a system_use key

    First do all the parsing of the 'remote' checksum, including GPG validate
    Then, based on the checksum algo, execute local checksum and compare
    """
    if not Data_File:
        Data_File = __data_file()
    if not Checksum_File:
        Checksum_File = __checksum_file()
    if not Data_File or not os.path.exists(Data_File):
        logger.warning("Data file %s doesn't exist" % Data_File)
        return False
    if not Checksum_File or not os.path.exists(Checksum_File):
        logger.warning("Checksum file %s doesn't exist" % Checksum_File)
        return False

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
    if Debug:
        logger.debug('Package signed by %s' % A[0].email)
    Clearsign_Sum = re.search(
        '(?m)^(?P<Checksum>[a-f0-9]+)\W+LookingGlass_',
        Clearsign)
    if not Clearsign_Sum:
        raise TTE.ChecksumException("Can't parse checksum: %s" % Clearsign)
    Clearsign_Sum = Clearsign_Sum.group('Checksum')

    # pick checksum used
    Checksum_Algo = None
    if len(Clearsign_Sum) == 64:
        Checksum_Algo = 'sha256sum'
    elif len(Clearsign_Sum) == 128:
        Checksum_Algo = 'sha512sum'
    else:
        raise TTE.ChecksumException("I don't know what manner of checksum this is: %s" % Clearsign_Sum)
    if Debug:
        logger.debug('Detected %s checksum' % Checksum_Algo)

    # do local checksum
    SO, SE = TTU.popen_wrapper([Checksum_Algo,
                                Data_File],
                               sudo=False,
                               debug=False)
    Local_Sum = re.search(
        '(?m)^(?P<Checksum>[a-f0-9]+)\W+/var/cache/LookingGlass/LookingGlass',
        SO)
    if not Local_Sum:
        raise TTE.ChecksumException("Can't parse checksum: %s/%s" % (SO, SE))
    Local_Sum = Local_Sum.group('Checksum')

    # now, finally, compare them
    if Local_Sum == Clearsign_Sum:
        return Local_Sum
    else:
        return False


def __open_control(DF=None):
    """
    unpack control.tar files into update_script_dir
    """
    File_List, Errors = TTU.tar_pipeline(
        arglist1=['/bin/tar',
                  '-xvOf', DF, # O to stdout
                  'control.tar'],
        arglist2=['/bin/tar',
                  '--directory', TTS.UPSTREAM['update_script_dir'],
                  '-xvf', '-'],
        )
    for F in File_List.split('\n'):
        logger.debug(F)
    if Errors and not re.search('Removing\ leading', Errors):
        raise TTE.PreInstException('control.tar unpacking problem: %s' % Errors)


def __run_control(path=None):
    """
    run the control files in path directory

    needed exit status, so not using popen_wrapper.
    """
    if os.path.exists(path):
        logger.debug('Running %s' % path)
        SO = tempfile.NamedTemporaryFile()
        SE = tempfile.NamedTemporaryFile()
        Current = subprocess.Popen(['/usr/bin/sudo', '-u', 'root',
                                    '/bin/run-parts',
                                    '--exit-on-error',
                                    '--report',
                                    path,
                                    ],
                                   stderr=SE,
                                   stdout=SO)
        Current.communicate()
        SO.seek(0)
        SE.seek(0)
        if Current.returncode != 0:
            logger.warning('%s | %s' % (SO.read(), SE.read()))
            raise TTE.PostInstException('trouble in %s' % (path))
        elif ((os.fstat(SO.fileno()).st_size != 0) or
              (os.fstat(SE.fileno()).st_size != 0)):
            logger.debug('%s | %s' % (SO.read(), SE.read()))
        else:
            logger.debug('No output')


def Unpack(Data_File=None):
    Preinst  = '%s/%s' % (TTS.UPSTREAM['update_script_dir'], 'preinst')
    Postinst = '%s/%s' % (TTS.UPSTREAM['update_script_dir'], 'postinst')

    if not Data_File:
        Data_File = __data_file()
    if not Data_File or not os.path.exists(Data_File):
        raise TTE.UnpackException("Can't find Data_File %s" % Data_File)

    # check for control.tar section
    Control_Files = False
    File_List, Errors = TTU.popen_wrapper(['/bin/tar', '-tf', Data_File],
                                          sudo=False)
    if re.search('(?m)^control.tar', File_List):
        Control_Files = True

    if Control_Files:
        __open_control(Data_File)
        __run_control(Preinst)

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

    if Control_Files:
        __run_control(Postinst)

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
                       
