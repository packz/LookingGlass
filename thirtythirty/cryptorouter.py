
class DefaultRouter(object):
    """
    https://docs.djangoproject.com/en/1.6/topics/db/multi-db/
    """
    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True
    
    def allow_syncdb(self, db, model):
        return True

# FIXME: this needs cleaning up - probably just need one of these w/ a bit smarter logic

class AddressRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'addressbook':
            return 'addressbook'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'addressbook':
            return 'addressbook'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if ((obj1._state.db in ['addressbook']) and
            (obj2._state.db in ['addressbook'])):
            return True
        else:
            return None
    
    def allow_syncdb(self, db, model):
        if db == 'addressbook':
            return model._meta.app_label == 'addressbook'
        elif model._meta.app_label == 'addressbook':
            return False
        return None


class RatchetRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'ratchet':
            return 'ratchet'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'ratchet':
            return 'ratchet'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if ((obj1._state.db in ['ratchet']) and
            (obj2._state.db in ['ratchet'])):
            return True
        else:
            return None
    
    def allow_syncdb(self, db, model):
        if db == 'ratchet':
            return model._meta.app_label == 'ratchet'
        elif model._meta.app_label == 'ratchet':
            return False
        return None


class SmpRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'smp':
            return 'smp'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'smp':
            return 'smp'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if ((obj1._state.db in ['smp']) and
            (obj2._state.db in ['smp'])):
            return True
        else:
            return None
    
    def allow_syncdb(self, db, model):
        if db == 'smp':
            return model._meta.app_label == 'smp'
        elif model._meta.app_label == 'smp':
            return False
        return None
