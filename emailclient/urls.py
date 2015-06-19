
from django.conf.urls import patterns, url, include

from rest_framework import routers, serializers, viewsets
from rest_framework.response import Response

import emailclient

urlpatterns = patterns('',
    url(r'^$', emailclient.views.folder, name='emailclient.inbox'),
    url(r'^\.(?P<name>.*)$', emailclient.views.folder, name='emailclient.folder'),
                       
    url(r'^compose$', emailclient.views.compose, name='emailclient.compose'),
    url(r'^compose/(?P<FP>[-A-Fa-f0-9]+)$', emailclient.views.compose, name='emailclient.compose'),
    url(r'^compose/(?P<Name>[A-Za-z]+\ [A-Za-z]+)$', emailclient.views.compose, name='emailclient.compose'),

    url(r'^edit/(?P<Key>[^\/]+)((?P<advanced>/advanced))?$', emailclient.views.edit, name='emailclient.edit'),

    url(r'^view/(?P<Key>[^\/]+)((?P<advanced>/advanced))?$', emailclient.views.view, name='emailclient.view'),

    url(r'^ajax/mailbox/new$', emailclient.views.new_mail, name='emailclient.new_mail'),

    url(r'^ajax/msg/attach$', emailclient.views.attach, name='emailclient.attach'),
    url(r'^ajax/msg/detach$', emailclient.views.detach, name='emailclient.detach'),
                       
    url(r'^ajax/msg/receive/(?P<Key>.*)$', emailclient.views.receive, name='emailclient.receive'),
    url(r'^ajax/msg/save$', emailclient.views.save, name='emailclient.save'),
    url(r'^ajax/msg/send$', emailclient.views.send, name='emailclient.send'),

    url(r'^ajax/msg/create_folder$', emailclient.views.create_folder, name='emailclient.create_folder'),
    url(r'^ajax/msg/delete_folder$', emailclient.views.delete_folder, name='emailclient.delete_folder'),
                       
    url(r'^ajax/msg/discard$', emailclient.views.discard, name='emailclient.discard'),
    url(r'^ajax/msg/flag$', emailclient.views.flag, name='emailclient.flag'),
    url(r'^ajax/msg/move$', emailclient.views.move, name='emailclient.move'),
)
