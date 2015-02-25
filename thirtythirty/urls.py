
from django.conf.urls import patterns, include, url

from thirtythirty import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^accounts/login$', views.password_prompt, name='accounts.login'),
    url(r'^accounts/login.afu=1$', views.password_prompt, {'warno':'Bad Passphrase'}, name='accounts.login.failed'),

    url(r'^login/ajax/drive_unlockp$', views.are_drives_unlocked, name='r_u_unlockt'),
    url(r'^drive_unlock', views.drive_unlock, name='drive_unlock'),
    url(r'^session_unlock', views.session_unlock, name='session_unlock'),

    url(r'^about', views.about, name='about'),

    url(r'^bug-?report', views.bug_report, name='bug_report'),
    url(r'^submit-?bug', views.submit_bug, name='submit_bug'),
                       
    url(r'LOCKDOWN', views.lockdown, name='lockdown'),
    url(r'REBOOT', views.reboot, name='reboot'),
    url(r'RESET', views.reset_to_defaults, name='system-reset'),

    url(r'^settings$', views.settings, name='settings'),
    url(r'^settings/advanced$', views.settings, {'advanced':True}, name='advanced_settings'),

    url(r'^contacts/', include('addressbook.urls')),
    url(r'^email/', include('emailclient.urls')),
    url(r'^setup/', include('setup.urls')),

    url(r'^settings/ajax/backup$', views.backup, name='settings.backup'),
    url(r'^settings/ajax/db_disaster$', views.db_disaster, name='settings.db_disaster'),
    url(r'^settings/ajax/ip_address$', views.ip_address, name='settings.ip_address'),
    url(r'^settings/ajax/last$', views.last, name='settings.last'),
    url(r'^settings/ajax/log_dump$', views.log_dump, name='settings.log_dump'),
    url(r'^settings/ajax/mounts$', views.mount_states, name='settings.mounts'),
    url(r'^settings/ajax/passcache$', views.passphrase_cache, name='settings.passphrase_cache'),
    url(r'^settings/ajax/restore$', views.restore, name='settings.restore'),
    url(r'^settings/ajax/servers$', views.server_states, name='settings.servers'),
    url(r'^settings/ajax/set-advanced$', views.set_advanced, name='settings.set-advanced'),
    url(r'^settings/ajax/symmetricopy$', views.symmetric_copy, name='settings.symmetric_copy'),
    url(r'^settings/ajax/thirtythirty$', views.thirtythirty_logs, name='settings.thirtythirty_logs'),
    url(r'^settings/ajax/update', views.update, name='settings.update'),
                       
    url(r'^settings/kick(?P<process>/.*)?$', views.kick, name='settings.kick'),
)
