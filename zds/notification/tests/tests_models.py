# coding: utf-8

from django.test import TestCase
from zds.forum.factories import TopicFactory, CategoryFactory, ForumFactory, PostFactory

from zds.member.factories import ProfileFactory
from zds.notification.models import TopicAnswerSubscription


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
        self.subscription = TopicAnswerSubscription(profile=self.profile1, content_object=self.topic1)
        title = u'<Abonnement du membre "{0}" aux réponses au sujet #{1}>'.format(
            self.profile1,
            self.topic1.pk)
        self.assertEqual(title, self.subscription.__unicode__())
