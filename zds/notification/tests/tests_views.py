# -*- coding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType

from django.core.urlresolvers import reverse
from django.test import TestCase
from zds.forum.factories import CategoryFactory, ForumFactory, TopicFactory, PostFactory
from zds.forum.models import Post
from zds.member.factories import ProfileFactory
from zds.notification.models import Notification


class NotificationListViewTest(TestCase):
    def setUp(self):
        self.profile = ProfileFactory()
        login_check = self.client.login(username=self.profile.user.username, password='hostel77')
        self.assertTrue(login_check)

    def test_success_list_notifications(self):
        """
        Gets list of notifications.
        """
        size = 2
        posts = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list'))

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            post = Notification.objects.get_unread_notifications_of(self.profile).filter(object_id=posts[i].pk)[0]
            self.assertEqual(response.context['object_list'][i].content_object, post.content_object)

    def test_success_list_notifications_sort_by_pubdate_order_in_asc(self):
        """
        Gets list of notifications sorted by pubdate and ordered in asc.
        """
        size = 2
        posts = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?sort=creation&order=asc')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            post = Notification.objects.get_unread_notifications_of(self.profile).filter(object_id=posts[i].pk)[0]
            self.assertEqual(response.context['object_list'][i].content_object, post.content_object)

    def test_success_list_notifications_filter_by_topic(self):
        """
        Gets list of notifications filter by topic.
        """
        size = 1
        posts = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?filter=topic')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            post = Notification.objects.get_unread_notifications_of(self.profile).filter(object_id=posts[i].pk)[0]
            self.assertEqual(response.context['object_list'][i].content_object, post.content_object)

    def test_success_list_notifications_with_filter_sort_and_order(self):
        """
        Gets list of notifications with a filter, a sort and an order.
        """
        size = 2
        posts = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?filter=topic&sort=creation&order=asc')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            post = Notification.objects \
                .get_unread_notifications_of(self.profile) \
                .filter(object_id=posts[i].pk)[0]
            self.assertEqual(response.context['object_list'][i].content_object, post.content_object)


def generate_x_notifications_on_topics(self, profile, size):
    another_profile = ProfileFactory()
    category = CategoryFactory(position=1)
    forum = ForumFactory(category=category, position_in_category=1)
    posts = []
    for i in range(0, size):
        topic = TopicFactory(forum=forum, author=profile.user)
        PostFactory(topic=topic, author=profile.user, position=1)
        # This post create a notification for the author of member.
        post = PostFactory(topic=topic, author=another_profile.user, position=2)
        posts.append(post)
    self.assertEqual(size, len(Notification.objects.get_unread_notifications_of(profile)))
    self.assertEqual(0, len(Notification.objects.get_unread_notifications_of(another_profile)))
    return posts
