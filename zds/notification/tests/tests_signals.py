from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import transaction
from django.test import TestCase
from zds.forum.factories import CategoryFactory, ForumFactory, TopicFactory, PostFactory
from zds.forum.models import Topic
from zds.member.factories import ProfileFactory
from zds.notification.models import Subscription, Notification, AnswerSubscription
from zds.utils import slugify


class NotificationForumTest(TestCase):

    def setUp(self):
        self.profile1 = ProfileFactory()
        self.profile2 = ProfileFactory()

        self.category1 = CategoryFactory(position=1)
        self.forum11 = ForumFactory(
            category=self.category1,
            position_in_category=1)
        self.forum12 = ForumFactory(
            category=self.category1,
            position_in_category=2)

        log = self.client.login(
            username=self.profile1.user.username,
            password='hostel77')
        self.assertEqual(log, True)

    def test_creation_topic(self):
        result = self.client.post(
            reverse('zds.forum.views.new') + '?forum={0}'
            .format(self.forum12.pk),
            {
                'title': u'Super sujet',
                'subtitle': u'Pour tester les notifs',
                'text': u'En tout cas l\'un abonnement'
            },
            follow=False)
        self.assertEqual(result.status_code, 302)

        topic = Topic.objects.filter(title=u'Super sujet').first()
        content_type = ContentType.objects.get_for_model(topic)

        subscription = AnswerSubscription.objects.get(object_id=topic.pk,
                                                      content_type__pk=content_type.pk,
                                                      profile=self.profile1)
        self.assertEqual(subscription.active, True)

    def test_answer_topic(self):
        topic1 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        post1 = PostFactory(topic=topic1, author=self.profile2.user, position=1)

        result = self.client.post(
            reverse('zds.forum.views.answer') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        # check that topic creator has been notified
        notification = Notification.objects.get(subscription__profile=self.profile2)
        subscription_content_type = ContentType.objects.get_for_model(topic1)

        self.assertEqual(notification.is_read, False)
        self.assertEqual(notification.subscription.content_type, subscription_content_type)
        self.assertEqual(notification.subscription.object_id, topic1.pk)

        # check that answerer has subscribed to the topic
        subscription = AnswerSubscription.objects.get(object_id=topic1.pk,
                                                content_type__pk=subscription_content_type.pk,
                                                profile=self.profile1)
        self.assertEqual(subscription.active, True)

    def test_topic_read(self):

        topic1 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        post1 = PostFactory(topic=topic1, author=self.profile2.user, position=1)

        result = self.client.post(
            reverse('zds.forum.views.answer') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        notification = Notification.objects.get(subscription__profile=self.profile2)
        self.assertEqual(notification.is_read, False)

        self.client.logout()
        log = self.client.login(
            username=self.profile2.user.username,
            password='hostel77')
        self.assertEqual(log, True)

        result = self.client.post(
            reverse(
                'zds.forum.views.topic',
                args=[
                    topic1.pk,
                    slugify(topic1.title)]),
            follow=True)

        self.assertEqual(result.status_code, 200)

        notification = Notification.objects.get(subscription__profile=self.profile2)
        self.assertEqual(notification.is_read, True)

    def test_post_unread(self):
        topic1 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        post1 = PostFactory(topic=topic1, author=self.profile2.user, position=1)
        post2 = PostFactory(topic=topic1, author=self.profile1.user, position=2)
        post3 = PostFactory(topic=topic1, author=self.profile2.user, position=3)

        self.client.logout()
        log = self.client.login(
            username=self.profile1.user.username,
            password='hostel77')
        self.assertEqual(log, True)
        notification = Notification.objects.get(subscription__profile=self.profile2)
        self.assertEqual(notification.is_read, False)
        notification.is_read = True
        notification.save()

        result = self.client.get(
                reverse('zds.forum.views.unread_post') +
                '?message={}'.format(post1.pk),
                follow=False)

        self.assertEqual(result.status_code, 302)

        notification = Notification.objects.get(subscription__profile=self.profile1, is_read=False)
        self.assertEqual(notification.object_id, post1.pk)
        self.assertEqual(notification.subscription.object_id, topic1.pk)




