# coding: utf-8

from django.conf.urls import patterns, url
from zds.notification.views import NotificationListView


urlpatterns = patterns('',
                       url(r'^$', NotificationListView.as_view(), name='notification-list'),
                       )
