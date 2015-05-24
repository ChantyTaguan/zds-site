from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from zds.article.factories import ArticleFactory, ReactionFactory
from zds.article.models import Validation
from zds.forum.factories import CategoryFactory, ForumFactory, TopicFactory, PostFactory, TagFactory
from zds.forum.models import Topic
from zds.member.factories import ProfileFactory, StaffProfileFactory
from zds.notification.models import Notification, TopicAnswerSubscription, NewTopicSubscription, \
    UpdateArticleSubscription, ArticleAnswerSubscription
from zds.tutorial.factories import LicenceFactory
from zds.utils import slugify


class NotificationForumTest(TestCase):

    def setUp(self):
        settings.EMAIL_BACKEND = \
            'django.core.mail.backends.locmem.EmailBackend'
        self.profile1 = ProfileFactory()
        self.profile1.user.email = u"foo@\xfbgmail.com"
        self.profile1.save()

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

        subscription = TopicAnswerSubscription.objects.get(object_id=topic.pk,
                                                      content_type__pk=content_type.pk,
                                                      profile=self.profile1)
        self.assertEqual(subscription.is_active, True)

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
        subscription = TopicAnswerSubscription.objects.get(object_id=topic1.pk,
                                                content_type__pk=subscription_content_type.pk,
                                                profile=self.profile1)
        self.assertEqual(subscription.is_active, True)

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

    def test_new_topic_forum(self):
        forum_subscription = NewTopicSubscription(profile=self.profile1, content_object=self.forum11)
        forum_subscription.save()

        topic = TopicFactory(forum=self.forum11, author=self.profile2.user)

        notification = Notification.objects.get(subscription=forum_subscription)
        self.assertEqual(notification.is_read, False)
        self.assertEqual(notification.sender, self.profile2)
        self.assertEqual(notification.url, topic.get_absolute_url())
        notification.is_read = True

        forum_subscription.activate_email()

        self.assertEquals(len(mail.outbox), 0)
        topic2 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        self.assertEquals(len(mail.outbox), 1)

    def test_new_topic_tag(self):

        tag = TagFactory(title = "top")
        tags = []
        tags.append(tag)

        tag_subscription = NewTopicSubscription(profile=self.profile1, content_object=tag)
        tag_subscription.save()

        topic1 = TopicFactory(forum=self.forum11, author=self.profile2.user, title="Bblala")
        topic1.add_tags(["top"])
        notifications = Notification.objects.filter(subscription=tag_subscription).all()
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications[0].sender, self.profile2)
        self.assertEqual(notifications[0].url, topic1.get_absolute_url())

        topic2 = TopicFactory(forum=self.forum12, author=self.profile2.user)
        topic2.add_tags(["top"])
        notifications = Notification.objects.filter(subscription=tag_subscription).all()
        self.assertEqual(notifications.count(), 2)

        topic3 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        notifications = Notification.objects.filter(subscription=tag_subscription).all()
        self.assertEqual(notifications.count(), 2)

        topic4 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        topic4.add_tags(["top"])
        notifications = Notification.objects.filter(subscription=tag_subscription).all()
        self.assertEqual(notifications.count(), 3)

        topic5 = TopicFactory(forum=self.forum11, author=self.profile1.user)
        topic5.add_tags(["top"])
        notifications = Notification.objects.filter(subscription=tag_subscription).all()
        self.assertEqual(notifications.count(), 3)

        tag_subscription.activate_email()

        self.assertEquals(len(mail.outbox), 0)
        topic6 = TopicFactory(forum=self.forum11, author=self.profile2.user)
        topic6.add_tags(["top"])
        self.assertEquals(len(mail.outbox), 1)


class NotificationArticleTest(TestCase):

    def setUp(self):
        settings.EMAIL_BACKEND = \
            'django.core.mail.backends.locmem.EmailBackend'
        self.mas = ProfileFactory().user
        settings.ZDS_APP['member']['bot_account'] = self.mas.username

        self.profile1 = ProfileFactory()
        self.profile1.user.email = u"foo@\xfbgmail.com"
        self.profile1.save()

        self.profile2 = ProfileFactory()

        self.staff = StaffProfileFactory().user

        self.licence = LicenceFactory()

        bot = Group(name=settings.ZDS_APP["member"]["bot_group"])
        bot.save()

        log = self.client.login(
            username=self.profile1.user.username,
            password='hostel77')
        self.assertEqual(log, True)

        self.article = ArticleFactory()
        self.article.authors.add(self.profile1.user)
        self.article.licence = self.licence
        self.article.save()

        # ask public article
        pub = self.client.post(
            reverse('zds.article.views.modify'),
            {
                'article': self.article.pk,
                'comment': u'Valide ! Je le veux.',
                'pending': 'Demander validation',
                'version': self.article.sha_draft,
                'is_major': True
            },
            follow=False)
        self.assertEqual(pub.status_code, 302)
        self.assertEqual(Validation.objects.count(), 1)

        self.client.logout()
        login_check = self.client.login(
            username=self.staff.username,
            password='hostel77')
        self.assertEqual(login_check, True)

        # reserve tutorial
        validation = Validation.objects.get(
            article__pk=self.article.pk)
        pub = self.client.post(
            reverse('zds.article.views.reservation', args=[validation.pk]),
            follow=False)
        self.assertEqual(pub.status_code, 302)

        # publish article
        pub = self.client.post(
            reverse('zds.article.views.modify'),
            {
                'article': self.article.pk,
                'comment-v': u'Cet article est excellent',
                'valid-article': 'Demander validation',
                'is_major': True
            },
            follow=False)
        self.assertEqual(pub.status_code, 302)
        self.assertEquals(len(mail.outbox), 1)
        mail.outbox = []

    def test_answer_subscription(self):

        self.article.authors.add(self.profile2.user)
        self.article.save()

        subscription1 = ArticleAnswerSubscription.objects.get_existing(
            profile=self.profile1, content_object=self.article)
        self.assertEquals(subscription1.is_active, True)

        subscription2 = ArticleAnswerSubscription.objects.get_existing(
            profile=self.profile2, content_object=self.article)
        self.assertEquals(subscription2.is_active, True)

        reaction = ReactionFactory(
            article=self.article,
            author=self.profile1.user,
            position=1)

        notification = Notification.objects.get(subscription=subscription2)
        self.assertEqual(notification.is_read, False)
        self.assertEqual(notification.sender, self.profile1)
        self.assertEqual(notification.url, reaction.get_absolute_url())

        notification.is_read = True
        notification.save()

        subscription1.activate_email()

        self.assertEquals(len(mail.outbox), 0)
        reaction2 = ReactionFactory(
            article=self.article,
            author=self.profile2.user,
            position=2)

        notification = Notification.objects.get(subscription=subscription1)
        self.assertEqual(notification.is_read, False)

        notification2 = Notification.objects.filter(subscription=subscription2).all()
        self.assertEqual(notification2.count(), 1)
        self.assertEqual(notification2[0].is_read, True)

        self.assertEquals(len(mail.outbox), 1)