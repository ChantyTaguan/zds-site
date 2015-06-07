import factory
from zds.forum.factories import CategoryFactory, ForumFactory, TopicFactory, PostFactory
from zds.member.factories import ProfileFactory
from zds.notification.models import Subscription, Notification


class SubscriptionFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Subscription


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
