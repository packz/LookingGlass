
import os
import pprint
import re

from os.path import exists

import thirtythirty.utils
import thirtythirty.exception
import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

def Volumes(unlisted=False, VG=None):
    ret = []
    for C in TTS.LUKS['mounts']:
        if ((C.has_key('unlisted') and C['unlisted']) and (not unlisted)):
            continue
        ret.append(Volume(LV=C['name'], VG=VG))
    return ret


def drives_are_unlocked():
    for V in Volumes():
        if not V.is_mounted():
            return False
    return True


def drives_exist():
    if os.path.exists(TTS.LUKS['shortcut_check_file']):
        logger.debug("drives exist - shortcut exists - bypass check")
        return True
    for V in Volumes():
        if not V.exists():
            logger.warning('%s does NOT exist' % V.Name)
            return False
    fh = file(TTS.LUKS['shortcut_check_file'], 'w')
    fh.write('drives exist - skip checks during this reboot cycle')
    fh.close()
    return True


class HDD(object):
    def __init__(self,
                 device=TTS.LUKS['device'],
                 volume_group=None,
                 ):
        self.size = 0
        self.dev = device
        self.VG = volume_group
        if not self.VG:
            self.VG = TTS.LUKS['vg_name']
        self.partitions = self.__partition_table()


    def __repr__(self):
        pp = pprint.PrettyPrinter()
        return pp.pformat(self.partitions)


    def __partition_table(self):
        """
        gives results in cylinders
        """
        Out, Err = thirtythirty.utils.popen_wrapper(
            ['/sbin/parted', '--script', self.dev,
             '--machine',
             'unit', 'cyl', 'print'])
        Raw = Out.split(';\n')
        Raw.pop()
        self.size = int(Raw[2].split(':')[0])
        ret = {}
        for LineNo in range(3, len(Raw)):
            Current = Raw[LineNo].split(':')
            ret[int(Current[0])] = {
                'start':int(Current[1][:-3]),
                'end':int(Current[2][:-3]),
                'size':int(Current[3][:-3]),
                }
            if Current[-1] != '':
                ret[int(Current[0])]['flags'] = Current[-1]
        return ret


    def has_partition(self):
        for N, V in self.partitions.iteritems():
            if V.has_key('flags') and V['flags'] == 'lvm':
                return N
        return False


    def has_vg(self, partition=None):
        if not partition:
            partition = self.has_partition()
        if not partition: return False
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/pvdisplay'])
        if not StdOut: return False
        for Line in StdOut.split('\n'):
            Col = Line.split(':')
            if Col[1] == TTS.LUKS['vg_name']:
                return True
        return False


    def create(self):
        if not self.has_vg():
            self.vg_setup()
        return self.VG


    def vg_setup(self, partition=None):
        """
        in: raw partition
        out: VG ready for LV creation

        no partition:
        scan this device for partitions flagged as LVM
        """
        if not partition:
            for P in self.partitions.keys():
                if self.partitions[P].has_key('flags') and self.partitions[P]['flags'] == 'lvm':
                    partition = P
                    break
        if not partition:
            return False
        Device = '%s%s' % (self.dev, partition)
        thirtythirty.utils.popen_wrapper(['/sbin/vgcreate', self.VG, Device])
        return self.VG




class Volume(object):
    def __init__(self,
                 device=TTS.LUKS['device'],
                 VG=None,
                 LV=None,
                 key_file=None):
        self.Device = device
        self.VG = VG
        if not self.VG:
            self.VG = TTS.LUKS['vg_name']
        self.key_file = key_file
        if not self.key_file:
            self.key_file = TTS.LUKS['key_file']
        self.HDD = None
        self.Name = LV
        self.Info = self.__mount_from_name(self.Name)
        self.Description = self.Info['description']


    def __mount_from_name(self, name):
        """
        LUKS['mounts'] is a list we need to scour...
        """
        return (Mount for Mount in TTS.LUKS['mounts'] \
                if Mount['name'] == name).next()


    def __repr__(self):
        ret = """[%s]
Description: %s
Exists: %s
Encrypted: %s
Mounted: %s
""" % ( self.Name,
        self.Description,
        self.exists(),
        self.encrypted(),
        self.is_mounted(),
        )
        return ret


    def csv(self):
        ret = '%s,%s,%s,%s,%s' % ( self.Name,
                                   self.Description,
                                   self.exists(),
                                   self.encrypted(),
                                   self.is_mounted(),
                                   )
        return ret


    def __create_keyfile(self, key=None, keyfile=None):
        if not keyfile:
            keyfile = self.key_file
        if key:
            fh = file(keyfile, 'w')
            fh.write(key)
            fh.close()


    def vg_exists(self):
        """
        used during create() sequence
        just looking for /dev/VG_NAME doesn't cut it if there are no active LVs
        """
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/vgdisplay', '--colon'])
        if StdErr != '':
            logger.warning('vg_exists: %s' % StdErr)
            return False
        for Line in StdOut.split('\n'):
            Col = Line.split(':')
            if Col[0].strip() == TTS.LUKS['vg_name']:
                return True
        return False
    

    def exists(self):
        """
        after we quick check if the LVs exist, what we really want to know is:
        have we updated the keyslot to non-default keys?
        """
        if exists('/dev/%s/%s' % (self.VG, self.Name)):
            logger.debug('%s exists' % self.Name)
            StdOut, StdErr = thirtythirty.utils.popen_wrapper(
                ['/sbin/cryptsetup',
                 'luksDump',
                 '/dev/%s/%s' % (self.VG,
                                 self.Name)],
                debug=False)
            if re.search(r'(?m)^Key Slot 1: ENABLED$', StdOut):
                return True
            elif re.search(r'(?m)^Key Slot 0: ENABLED$', StdOut):
                logger.debug('%s has default passphrase' % self.Name)
        return False


    def encrypted(self):
        if exists('/dev/mapper/%s' % (self.Name)): return True
        else: return False


    def is_mounted(self):
        SO, SE = thirtythirty.utils.popen_wrapper(['/bin/mount'],
                                     sudo=False,
                                     debug=False) # was really noisy...
        if re.search(r'%s on %s' % (self.Name,
                                    self.Info['mountpoint']), SO):
            return True
        else:
            return False


    def create(self, key=None):
        """
        we need to drill down in reverse order
        doing the drive partitioning /last/
        recurses back to itself to do least amount of drive fracking
        """
        if self.is_mounted():
            return True
        if self.exists():
            self.unlock(key)
            return True
        if self.vg_exists():
            self.init_lv(key=key)
            return self.create(key)
        if not self.HDD:
            self.HDD = HDD(self.Device)
        self.VG = self.HDD.create()
        return self.create(key)
    

    def init_lv(self, key=None):
        """
        we use the keyfile here because cryptdisks_start knows about it.
        """
        if key: self.__create_keyfile(key)
        if not exists(self.key_file):
            raise(thirtythirty.exception.No_Keyfile("OMG NO KEY FILE in lv_create()"))
        if exists('/dev/%s/%s' % (self.VG, self.Name)):
            raise(thirtythirty.exception.LVExists("Logical volume already exists - will not lv_create()"))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/lvcreate',
                                              self.VG,
                                              '-L', self.Info['size'],
                                              '-n', self.Name])
        if not re.search('created', StdOut):
            raise(thirtythirty.exception.CannotCreateLV('create() failed: %s' % StdErr))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptsetup',
                                              'luksFormat',
                                              '--batch-mode',
                                              '--key-file', self.key_file,
                                              '/dev/%s/%s' % (self.VG,
                                                              self.Name)])
        if StdErr:
            raise(thirtythirty.exception.CannotFormat('lv_create() failed: %s' % StdErr))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptdisks_start',
                                              self.Name])
        if not re.search('%s \(started\)...done' % self.Name, StdOut):
            raise(thirtythirty.exception.CannotStartLuks('lv_create(%s) failed: %s' % (self.Name,
                                                                          StdErr)))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/mkfs.%s' % TTS.LUKS['fs'],
                                              '/dev/mapper/%s' % self.Name])
        if not re.search('done\n\n$', StdOut):
            raise(thirtythirty.exception.CannotMKFS('lv_create(%s) failed: %s' % (self.Name,
                                                                     StdOut)))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/bin/mount',
                                              self.Info['mountpoint']])
        if (StdOut, StdErr) != ('', ''):
            raise(thirtythirty.exception.CannotMount('lv_create(%s) failed: %s' % (self.Name,
                                                                      StdErr)))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/bin/chown', self.Info['owner'],
                                              self.Info['mountpoint']])
        if (StdOut, StdErr) != ('', ''):
            logger.error(StdOut)
            logger.error(StdErr)
            raise(thirtythirty.exception.CannotOwn('lv_create(%s) failed' % self.Name))
        for Location, Octal in self.Info['permissions']:
            StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/bin/chmod', Octal, Location])
            if (StdOut, StdErr) != ('', ''):
                logger.debug('chmod %s failed: %s' % (Location, StdErr))
        if self.Info.has_key('post-init'):
            for S in self.Info['post-init']:
                thirtythirty.utils.popen_wrapper(S)
        if self.Info.has_key('post-up'):
            for S in self.Info['post-up']:
                thirtythirty.utils.popen_wrapper(S)


    def unlock(self, key=None):
        if key: self.__create_keyfile(key)
        if not exists(self.key_file):
            raise(thirtythirty.exception.No_Keyfile("OMG NO KEY FILE"))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptdisks_start',
                                              self.Name])
        if re.search('failed', StdOut):
            raise(thirtythirty.exception.CannotStartLuks('unlock() failed: %s' % StdOut))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/bin/mount',
                                              self.Info['mountpoint']])
        if (StdOut, StdErr) != ('', ''):
            if not re.search('already mounted', StdErr):
                raise(thirtythirty.exception.CannotMount('unlock() failed'))
        if self.Info.has_key('post-up'):
            for S in self.Info['post-up']:
                thirtythirty.utils.popen_wrapper(S)


    def lock(self, purge_key_file=True):
        if self.Info.has_key('pre-down'):
            for S in self.Info['pre-down']:
                thirtythirty.utils.popen_wrapper(S)
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/bin/umount',
                                              self.Info['mountpoint']])
        if (StdOut, StdErr) != ('', '')  and not \
               re.search('not mounted', StdErr):
            raise(thirtythirty.exception.CannotUmount('lock() failed: %s' % StdErr))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptdisks_stop',
                                              self.Name])
        if not re.search('\(stopp(ed|ing)\)...done', StdOut):
            raise(thirtythirty.exception.CannotStopLuks('lock() failed: %s' % StdOut))
        if purge_key_file:
            try:
                os.remove(self.key_file)
            except OSError as e:
                logger.warning(e)


    def resize(self, New_Size='+1G'):
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/lvresize',
                                              '-L', New_Size,
                                              '/dev/%s/%s' % (self.VG,
                                                              self.Name)])
        if not re.search('successfully', StdOut):
            raise(thirtythirty.exception.LVResizeFailed('resize() failed at logical_volume'))
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptsetup',
                                              'resize',
                                              '/dev/mapper/%s' % self.Name])
        if (StdOut, StdErr) != ('', ''):
            raise(thirtythirty.exception.CryptResizeFailed('resize() failed at cryptsetup'))
        # FIXME: only works if FS is ext3|4
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/resize2fs',
                                              '/dev/mapper/%s' % self.Name])
        if not re.search('is now.*blocks long', StdOut):
            raise(thirtythirty.exception.FSResizeFailed('resize() failed at the filesystem'))
        

    def remove(self):
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/lvremove',
                                              '--force',
                                              '/dev/%s/%s' % (self.VG,
                                                              self.Name)])
        if not re.search('successfully removed', StdOut):
            raise(thirtythirty.exception.LVRemoveFailed('remove() failed at logical manager %s' % StdErr))


    def change_passphrase(self, old=None, new=None, hose_old=True):
        if ((old is None) or (new is None)):
            raise(thirtythirty.exception.No_Keyfile('Missing key in change_passphrase()'))
        old_keyfile = '%s.old' % self.key_file
        if old: self.__create_keyfile(old, old_keyfile)
        if not exists(old_keyfile):
            raise(thirtythirty.exception.No_Keyfile("OMG NO KEY FILE"))
        # add the new key
        StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptsetup',
                                              'luksAddKey',
                                              '--batch-mode',
                                              '--key-slot', '1',
                                              '--key-file', old_keyfile,
                                              '/dev/%s/%s' % (self.VG,
                                                              self.Name)],
                                             new)
        if (StdOut, StdErr) != ('', ''):
            raise(thirtythirty.exception.NoKeychange('change_passphrase() addkey: %s/%s' % (StdOut,
                                                                               StdErr)))
        os.unlink(old_keyfile)
        # delete the old
        if hose_old:
            StdOut, StdErr = thirtythirty.utils.popen_wrapper(['/sbin/cryptsetup',
                                                  'luksKillSlot',
                                                  '--batch-mode',
                                                  '/dev/%s/%s' % (self.VG,
                                                                  self.Name),
                                                  '0'],
                                                 new)
            if (StdOut, StdErr) != ('', ''):
                raise(thirtythirty.exception.NoKeychange('change_passphrase() killslot: %s/%s' % (StdOut,
                                                                                     StdErr)))
