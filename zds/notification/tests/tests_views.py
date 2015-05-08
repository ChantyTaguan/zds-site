# -*- coding: utf-8 -*-

from django.core.urlresolvers import reverse
from django.test import TestCase
from zds.forum.factories import CategoryFactory, ForumFactory, TopicFactory, PostFactory
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
        notifications = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list'))

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            self.assertEqual(response.context['object_list'][i], notifications[i])

    def test_success_list_notifications_sort_by_pubdate_order_in_asc(self):
        """
        Gets list of notifications sorted by pubdate and ordered in asc.
        """
        size = 2
        notifications = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?sort=creation&order=asc')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            self.assertEqual(response.context['object_list'][i], notifications[i])

    def test_success_list_notifications_sort_by_pubdate_order_by_desc(self):
        """
        Gets list of notifications sorted by pubdate and ordered in desc.
        """
        size = 2
        notifications = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?sort=creation&order=desc')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            self.assertEqual(response.context['object_list'][i], notifications[size - 1 - i])

    def test_success_list_notifications_filter_by_topic(self):
        """
        Gets list of notifications filter by topic.
        """
        size = 1
        notifications = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?filter=topic')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            self.assertEqual(response.context['object_list'][i], notifications[i])

    def test_success_list_notifications_with_filter_sort_and_order(self):
        """
        Gets list of notifications with a filter, a sort and an order.
        """
        size = 2
        notifications = generate_x_notifications_on_topics(self, self.profile, size)

        response = self.client.get(reverse('notification-list') + '?filter=topic&sort=creation&order=desc')

        self.assertEqual(200, response.status_code)
        for i in range(0, size):
            self.assertEqual(response.context['object_list'][i], notifications[size - 1 - i])


def generate_x_notifications_on_topics(self, profile, size):
    another_profile = ProfileFactory()
    category = CategoryFactory(position=1)
    forum = ForumFactory(category=category, position_in_category=1)
    for i in range(0, size):
        topic = TopicFactory(forum=forum, author=profile.user)
        PostFactory(topic=topic, author=profile.user, position=1)
        # This post create a notification for the author of member.
        PostFactory(topic=topic, author=another_profile.user, position=2)
    notifications = Notification.objects.get_unread_notifications_of(profile)
    self.assertEqual(size, len(notifications))
    self.assertEqual(0, len(Notification.objects.get_unread_notifications_of(another_profile)))
    return notifications
