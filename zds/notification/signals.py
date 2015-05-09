from functools import wraps
import django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from zds.article.models import Reaction
from zds.forum.models import Topic, Post

from zds.notification.models import AnswerSubscription, NewTopicSubscription


def disable_for_loaddata(signal_handler):
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        if "raw" in kwargs and kwargs['raw']:
            print "Skipping signal for %s %s" % (args, kwargs)
            return
        signal_handler(*args, **kwargs)
    return wrapper

answer_unread = Signal(providing_args=["instance", "user"])
content_read = Signal(providing_args=["instance", "user"])

@receiver(answer_unread)
@disable_for_loaddata
def unread_post_event(sender, **kwargs):
    post = kwargs.get('instance')
    user = kwargs.get('user')
    # content_subscription_type = ContentType.objects.get_for_model(content_subscription)
    # AnswerSubscription.objects.filter()
    # send_notification(post.topic, post, user)


@receiver(content_read)
@disable_for_loaddata
def test_signals(sender, **kwargs):
    content = kwargs.get('instance')
    user = kwargs.get('user')
    # mark_notification_read(content, user)

# Forums
@receiver(post_save, sender=Topic)
@disable_for_loaddata
def saved_topic_event(sender, **kwargs):
    if kwargs.get('created', True):
        topic = kwargs.get('instance')

        # Notify the forum followers
        content_subscription_type = ContentType.objects.get(model="forum")
        subscription_list = NewTopicSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=topic.forum.pk, active=True)
        for subscription in subscription_list:
            subscription.send_notification(topic=topic)

        # Notify the tag followers
        content_subscription_type = ContentType.objects.get(model="tag")
        for tag in topic.tags.all():
            subscription_list = NewTopicSubscription.objects\
                .filter(content_type__pk=content_subscription_type.pk,
                        object_id=topic.forum.pk, active=True)
            for subscription in subscription_list:
                subscription.send_notification(topic=topic)

        # Follow the topic
        subscription = AnswerSubscription(profile=topic.author.profile, content_object=topic)
        subscription.activate_or_save()


@receiver(post_save, sender=Post)
@disable_for_loaddata
def answer_topic_event(sender, **kwargs):
    if kwargs.get('created', True):
        post = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="topic")
        subscription_list = AnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=post.topic.pk, active=True)
        for subscription in subscription_list:
            subscription.send_notification(answer=post)

        # Follow topic on answering
        subscription = AnswerSubscription(profile=post.author.profile, content_object=post.topic)
        subscription.activate_or_save()


# Article
@receiver(post_save, sender=Reaction)
@disable_for_loaddata
def new_reaction_event(sender, **kwargs):
    if kwargs.get('created', True):
        reaction = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="article")
        subscription_list = AnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=reaction.article.pk, active=True)
        for subscription in subscription_list:
            subscription.send_notification(answer=reaction)

        # Follow article on answering
        subscription = AnswerSubscription(profile=reaction.author.profile, content_object=reaction.article)
        subscription.activate_or_save()

