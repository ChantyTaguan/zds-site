# coding: utf-8

from django.conf.urls import patterns, url
from zds.notification.views import NotificationList


urlpatterns = patterns('',
                       url(r'^$', NotificationList.as_view(), name='notification-list'),
                       )
