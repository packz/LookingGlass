
from django.http import HttpResponse

from django.db.models import Q

import json

import addressbook
import smp
import thirtythirty.exception
from thirtythirty.gpgauth import session_pwd_wrapper

import logging
logger = logging.getLogger(__name__)

SMP_Objects = smp.models.SMP.objects
SMP_Objects.init_for('smp')


@session_pwd_wrapper
def pending(request):
    ret = []
    if 'passphrase' not in request.session:
        return HttpResponse('No passphrase, know peace')
    PP = request.session['passphrase']
    
    try: SMP_Objects.decrypt_database(PP)
    except thirtythirty.exception.Target_Exists: pass

    for A in addressbook.address.Address.objects.filter(
        user_state__gte = addressbook.address.Address.NOT_VETTED,
        user_state__lt = addressbook.address.Address.AUTHED,
        ):
        Count = smp.models.SMP.objects.filter(
            UniqueKey = A.fingerprint
            )
        if ((len(Count) == 0) or
            (Count.filter(
                Q(Question = None) |\
                Q(Shared_Secret = None)
                ).count() > 0)):
            ret.append(A.fingerprint)
    return HttpResponse(json.dumps(ret),
                        content_type='application/json')
