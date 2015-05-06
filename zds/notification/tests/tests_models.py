# coding: utf-8
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

from django.test import TestCase
from zds.forum.factories import TopicFactory, CategoryFactory, ForumFactory, PostFactory
from zds.forum.models import Topic

from zds.member.factories import ProfileFactory
from zds.notification.models import Subscription


class SubscriptionTest(TestCase):

    def setUp(self):
        # scenario - topic1 :
        # post1 - user1 - subscription
        self.category1 = CategoryFactory(position=1)
        self.forum11 = ForumFactory(
            category=self.category1,
            position_in_category=1)
        self.forum12 = ForumFactory(
            category=self.category1,
            position_in_category=2)
        self.profile1 = ProfileFactory()
        self.topic1 = TopicFactory(forum=self.forum11, author=self.profile1.user)
        self.post1 = PostFactory(topic=self.topic1, author=self.profile1.user, position=1)
        self.user = ProfileFactory().user
        self.user2 = ProfileFactory().user
        log = self.client.login(
            username=self.user.username,
            password='hostel77')
        self.assertEqual(log, True)

    def test_unicode(self):
        self.subscription = Subscription(profile=self.profile1, type='NEW_CONTENT', content_object=self.topic1)
        title = u'<Abonnement du membre "{0}" aux notifications de type {1} pour le {3}, #{2}>'.format(
            self.profile1,
            'NEW_CONTENT',
            self.topic1.pk,
            ContentType.objects.get(app_label="forum", model="topic"))
        self.assertEqual(title, self.subscription.__unicode__())