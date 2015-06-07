# -*- coding: utf-8 -*-

from django.core.urlresolvers import reverse
from django.test import TestCase

from zds.forum.factories import create_category, add_topic_in_a_forum, TagFactory
from zds.member.factories import ProfileFactory
from zds.notification.factories import generate_x_notifications_on_topics
from zds.notification.models import Notification, NewTopicSubscription, TopicAnswerSubscription


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


class NotificationFollowForumEditTest(TestCase):

    def setUp(self):
        self.profile = ProfileFactory()
        login_check = self.client.login(username=self.profile.user.username, password='hostel77')
        self.assertTrue(login_check)

    def test_failure_edit_content_with_client_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('follow-forum-edit'))

        self.assertEqual(302, response.status_code)

    def test_failure_edit_content_with_sanctioned_user(self):
        profile = ProfileFactory()
        profile.can_read = False
        profile.can_write = False
        profile.save()

        self.assertTrue(self.client.login(username=profile.user.username, password='hostel77'))
        response = self.client.post(reverse('follow-forum-edit'))

        self.assertEqual(403, response.status_code)

    def test_failure_edit_content_with_wrong_identifier(self):
        profile = ProfileFactory()

        self.assertTrue(self.client.login(username=profile.user.username, password='hostel77'))
        data = {
            'forum': 'abc',
        }
        response = self.client.post(reverse('follow-forum-edit'), data, follow=False)

        self.assertEqual(404, response.status_code)

    def test_failure_edit_content_with_a_content_not_found(self):
        profile = ProfileFactory()

        self.assertTrue(self.client.login(username=profile.user.username, password='hostel77'))
        data = {
            'forum': 99999,
        }
        response = self.client.post(reverse('follow-forum-edit'), data, follow=False)

        self.assertEqual(404, response.status_code)

    def test_success_edit_follow_of_forum(self):
        category, forum = create_category()

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'forum': forum.pk,
            'follow': '1'
        }
        response = self.client.post(reverse('follow-forum-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = NewTopicSubscription.objects.get_existing(self.profile, forum, is_active=True)
        self.assertIsNotNone(subscription)

    def test_success_edit_follow_email_of_forum(self):
        category, forum = create_category()

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'forum': forum.pk,
            'email': '1'
        }
        response = self.client.post(reverse('follow-forum-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = NewTopicSubscription.objects.get_existing(self.profile, forum, is_active=True)
        self.assertIsNotNone(subscription)
        self.assertTrue(subscription.by_email)

    def test_success_edit_follow_of_tag(self):
        category, forum = create_category()
        topic = add_topic_in_a_forum(forum, self.profile)
        tag = TagFactory()
        topic.add_tags([tag.title])

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'tag': tag.pk,
            'follow': '1'
        }
        response = self.client.post(reverse('follow-tag-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = NewTopicSubscription.objects.get_existing(self.profile, tag, is_active=True)
        self.assertIsNotNone(subscription)

    def test_success_edit_follow_email_of_tag(self):
        category, forum = create_category()
        topic = add_topic_in_a_forum(forum, self.profile)
        tag = TagFactory()
        topic.add_tags([tag.title])

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'tag': tag.pk,
            'email': '1'
        }
        response = self.client.post(reverse('follow-tag-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = NewTopicSubscription.objects.get_existing(self.profile, tag, is_active=True)
        self.assertIsNotNone(subscription)
        self.assertTrue(subscription.by_email)

    def test_success_edit_follow_of_topic(self):
        category, forum = create_category()
        topic = add_topic_in_a_forum(forum, self.profile)

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'topic': topic.pk,
            'follow': '1'
        }
        response = self.client.post(reverse('follow-topic-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = TopicAnswerSubscription.objects.get_existing(self.profile, topic, is_active=True)
        self.assertIsNotNone(subscription)

    def test_success_edit_follow_email_of_topic(self):
        category, forum = create_category()
        topic = add_topic_in_a_forum(forum, self.profile)

        self.assertTrue(self.client.login(username=self.profile.user.username, password='hostel77'))
        data = {
            'topic': topic.pk,
            'email': '1'
        }
        response = self.client.post(reverse('follow-topic-edit'), data, follow=False)

        self.assertEqual(302, response.status_code)
        subscription = TopicAnswerSubscription.objects.get_existing(self.profile, topic, is_active=True)
        self.assertIsNotNone(subscription)
        self.assertTrue(subscription.by_email)
