from django.conf.urls import patterns, url

from emailclient import views

urlpatterns = patterns('',
    url(r'^$', views.folder, name='emailclient.inbox'),
    url(r'^\.(?P<name>.*)$', views.folder, name='emailclient.folder'),
                       
    url(r'^compose$', views.compose, name='emailclient.compose'),
    url(r'^compose/(?P<FP>[-A-Fa-f0-9]+)$', views.compose, name='emailclient.compose'),
    url(r'^compose/(?P<Name>[A-Za-z]+\ [A-Za-z]+)$', views.compose, name='emailclient.compose'),

    url(r'^edit/(?P<Key>[^\/]+)((?P<advanced>/advanced))?$', views.edit, name='emailclient.edit'),

    url(r'^view/(?P<Key>[^\/]+)((?P<advanced>/advanced))?$', views.view, name='emailclient.view'),

    url(r'^ajax/mailbox/new$', views.new_mail, name='emailclient.new_mail'),

    url(r'^ajax/msg/receive/(?P<Key>.*)$', views.receive, name='emailclient.receive'),
    url(r'^ajax/msg/save$', views.save, name='emailclient.save'),
    url(r'^ajax/msg/send$', views.send, name='emailclient.send'),

    url(r'^ajax/msg/create_folder$', views.create_folder, name='emailclient.create_folder'),
    url(r'^ajax/msg/delete_folder$', views.delete_folder, name='emailclient.delete_folder'),
                       
    url(r'^ajax/msg/discard$', views.discard, name='emailclient.discard'),
    url(r'^ajax/msg/flag$', views.flag, name='emailclient.flag'),
    url(r'^ajax/msg/move$', views.move, name='emailclient.move'),
)
