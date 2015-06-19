
from django.conf.urls import patterns, url, include

from rest_framework import routers, serializers, viewsets
from rest_framework.response import Response

import addressbook

class AddressSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = addressbook.address.Address
        fields = ('covername',
                  'fingerprint',
                  'is_me',
                  'nickname',
                  'smp_failures',
                  'system_use',
                  'user_state',
                  )

class AddressViewSet(viewsets.ModelViewSet):
    queryset = addressbook.address.Address.objects.all()
    serializer_class = AddressSerializer

    def get_object(self):
        return addressbook.address.Address.objects.filter(
            fingerprint=self.kwargs['fp']
        )


router = routers.DefaultRouter(trailing_slash=False)
router.register(r'address', AddressViewSet)

    
urlpatterns = patterns('',
    url(r'^$', addressbook.views.home, name='addressbook'),
    url(r'^advanced$', addressbook.views.home, {'advanced':True}, name='addressbook.advanced'),
    url(r'^(?P<Index>[_A-Za-z0-9])$', addressbook.views.home, name='addressbook.filter'),

    url(r'^dossier$', addressbook.views.dossier, name='addressbook.dossier'), # gah
    url(r'^dossier/(?P<Fingerprint>[-A-Fa-f0-9]{36})(?P<advanced>/advanced)?$', addressbook.views.dossier, name='addressbook.dossier'),
    url(r'^dossier/(?P<Fingerprint>[-A-Fa-f0-9]{40})(?P<advanced>/advanced)?$', addressbook.views.dossier, name='addressbook.dossier'),

    url(r'^rest/', include(router.urls)),

    url(r'^ajax/add$', addressbook.views.add_contact, name='addressbook.add'),
    url(r'^ajax/delete$', addressbook.views.delete, name='addressbook.delete'),
    url(r'^ajax/import$', addressbook.views.key_import, name='addressbook.key_import'),
    url(r'^ajax/nickname$', addressbook.views.nickname, name='addressbook.nickname'),
    url(r'^ajax/qpush$', addressbook.views.push_to_queue, name='addressbook.push_to_queue'),
    url(r'^ajax/reset$', addressbook.views.reset_contact, name='addressbook.reset_contact'),
                       
    url(r'^ajax/search$', addressbook.views.search, name='addressbook.search'),
    url(r'^ajax/search/(?P<Q>.*)$', addressbook.views.search, name='addressbook.search'),
)
