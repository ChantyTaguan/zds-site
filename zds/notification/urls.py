# coding: utf-8

from django.conf.urls import patterns, url
from zds.forum.models import Forum, Topic
from zds.notification.models import NewTopicSubscription, TopicAnswerSubscription
from zds.notification.views import NotificationListView, NotificationFollowEdit
from zds.utils.models import Tag

urlpatterns = patterns('',
                       url(r'^$', NotificationListView.as_view(), name='notification-list'),
                       url(r'^follow/forum/editer/$',
                           NotificationFollowEdit.as_view(subscription=NewTopicSubscription, type=Forum, param='forum'),
                           name='follow-forum-edit'),
                       url(r'^follow/tag/editer/$',
                           NotificationFollowEdit.as_view(subscription=NewTopicSubscription, type=Tag, param='tag'),
                           name='follow-tag-edit'),
                       url(r'^follow/sujet/editer/$',
                           NotificationFollowEdit.as_view(
                               subscription=TopicAnswerSubscription, type=Topic, param='topic'
                           ), name='follow-topic-edit'),
                       )
