
import os.path
import subprocess

# http://stackoverflow.com/questions/8869816/django-test-returning-wrapped-view-as-view-name-instead-of-proper-view-name
from functools import wraps
from django.utils.decorators import available_attrs

import django_rq
from django_rq import job

import thirtythirty.settings as TTS

import logging
logger = logging.getLogger(__name__)

@job
def Passphrase_disappeared():
    logging.critical('passphrase cache is gone - stopping worker')
    subprocess.call(['/usr/bin/sudo', '-u', 'root',
                     'systemctl', 'stop', 'rqworker-secure'])


def Passphrase_or_requeue(calling_job=None):
    """
    Add the cached passphrase to kwargs
    if not available
    let the default worker know there's a problem
    then requeue thyself
    """
    @wraps(calling_job, assigned=available_attrs(calling_job))
    def inner(*args, **kwargs):
        if os.path.exists(TTS.PASSPHRASE_CACHE):
            kwargs['Passphrase'] = file(TTS.PASSPHRASE_CACHE).read()
            return calling_job(*args, **kwargs)
        else:
            Passphrase_disappeared.delay()
            Q = django_rq.get_queue('needs_passphrase')
            Q.enqueue(calling_job, *args, **kwargs)
    return inner
