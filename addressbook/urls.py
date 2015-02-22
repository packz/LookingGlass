
from django.conf.urls import patterns, url

from addressbook import views

urlpatterns = patterns('',
    url(r'^$', views.home, name='addressbook'),
    url(r'^advanced$', views.home, {'advanced':True}, name='addressbook.advanced'),
    url(r'^(?P<Index>[_A-Za-z0-9])$', views.home, name='addressbook.filter'),

    url(r'^dossier$', views.dossier, name='addressbook.dossier'), # gah
    url(r'^dossier/(?P<Fingerprint>[-A-Fa-f0-9]{36})(?P<advanced>/advanced)?$', views.dossier, name='addressbook.dossier'),
    url(r'^dossier/(?P<Fingerprint>[-A-Fa-f0-9]{40})(?P<advanced>/advanced)?$', views.dossier, name='addressbook.dossier'),

    url(r'^ajax/add$', views.add_contact, name='addressbook.add'),
    url(r'^ajax/delete$', views.delete, name='addressbook.delete'),
    url(r'^ajax/import$', views.key_import, name='addressbook.key_import'),
    url(r'^ajax/nickname$', views.nickname, name='addressbook.nickname'),
    url(r'^ajax/qpush$', views.push_to_queue, name='addressbook.push_to_queue'),
                       
    url(r'^ajax/search$', views.search, name='addressbook.search'),
    url(r'^ajax/search/(?P<Q>.*)$', views.search, name='addressbook.search'),
)
