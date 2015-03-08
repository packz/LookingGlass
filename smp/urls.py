
from django.conf.urls import patterns, url

from smp import views

urlpatterns = patterns('',
     url(r'^ajax/pending$', views.pending, name='smp.pending'),
                       )
