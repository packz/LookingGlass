
from django.conf.urls import patterns, url

from setup import views

urlpatterns = patterns('',
    url(r'^$', views.finished, name='setup.index'),

    url(r'^luks$', views.luks, name='setup.luks'),
    url(r'^clobber', views.luks, {'clobber':True}, name='setup.clobber'),
                       
    url(r'^covername$', views.covername, name='setup.covername'),
    url(r'^gpg', views.gpg, name='setup.gpg'),
    url(r'^finished', views.finished, name='setup.finished'),

    url(r'^ajax/create_user', views.create_user, name='setup.create_user'),
    url(r'^ajax/updates_complete', views.updates_complete, name='setup.updates_complete'),
    url(r'^ajax/passphrase(\/(?P<words>1?[0-9]))?',
        views.gen_passphrase, name='setup.gen_pass'),
    url(r'^ajax/covername$',
        views.gen_covername, name='setup.gen_covername'),
)
