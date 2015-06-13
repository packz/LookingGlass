
class FileDB:
    """
    File-backed database.
    Stored in ramdisk, which is encrypted by default.
    Loss of power = scrambled.
    """
    def __init__(self,
                 clobber=False,
                 loc='/dev/shm'):
        from os import rename
        from os.path import exists
        self.file_loc = loc
        self.db = {'drive.key':None,
                   'covername':None,
                   'gpg.key':None,
                   }
        if clobber:
            for X in self.db.keys():
                FN = '%s/%s' % (self.file_loc, X)
                if exists(FN): rename(FN, '%s.old' % FN)
        self.db = self.__load()

    def __load(self):
        from os.path import exists
        ret = {}
        for F in self.db.keys():
            FN = '%s/%s' % (self.file_loc, F)
            if not exists(FN):
                ret[F] = None
            else:
                ret[F] = file(FN, 'r').read()
        return ret

    def burn_notice(self):
        from os import remove
        from os.path import exists
        for X in self.db.keys():
            FN = '%s/%s' % (self.file_loc, X)
            oFN = '%s/%s.old' % (self.file_loc, X)
            if exists(FN):
                remove(FN)
            if exists(oFN):
                remove(oFN)

    def save(self):
        from os import chmod
        for X in self.db.keys():
            if self.db[X]:
                Location = '%s/%s' % (self.file_loc, X)
                FN = file(Location, 'w')
                chmod(Location, 0600)
                FN.write(self.db[X])
                FN.close()

    def update(self, post=None):
        for X in self.db.keys():
            if X in post:
                self.db[X] = post[X]
        self.save()
        return self.db

    def keys(self):
        self.__load()
        return self.db.keys()

    def __getitem__(self, which):
        self.__load()
        return self.db[which]

    def __repr__(self):
        self.__load()
        return str(self.db)
