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

    def test_subscription_exists_create_topic(self):
        result = self.client.post(
            reverse('zds.forum.views.new') + '?forum={0}'
            .format(self.forum12.pk),
            {'title': u'Super sujet',
             'subtitle': u'Pour tester les notifs',
             'text': u'En tout cas la création d\'un abonnement'
            },
            follow=False)
        self.assertEqual(result.status_code, 302)

        content_type = ContentType.objects.get(model="topic")
        topic = Topic.objects.filter(title=u'Super sujet').first()

        subscription_list = Subscription.objects.all()
        cpt = 0
        for sub in subscription_list:
            cpt += 1

        subscription = Subscription.objects.filter(object_id=topic.pk, content_type=content_type, profile=self.user.profile).first();
        self.assertEqual(subscription.is_active, True)
