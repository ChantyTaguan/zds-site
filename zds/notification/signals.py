from functools import wraps
import django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from zds.article.models import Reaction
from zds.forum.models import Topic, Post

from zds.notification.models import AnswerSubscription, NewTopicSubscription, PublicationSubscription, Notification


def disable_for_loaddata(signal_handler):
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        if "raw" in kwargs and kwargs['raw']:
            print "Skipping signal for %s %s" % (args, kwargs)
            return
        signal_handler(*args, **kwargs)
    return wrapper

answer_unread = Signal(providing_args=["instance", "user", "answer_to"])
topic_read = Signal(providing_args=["instance", "user"])
publication_read = Signal(providing_args=["instance", "user"])

@receiver(answer_unread)
@disable_for_loaddata
def unread_answer_event(sender, **kwargs):
    answer = kwargs.get('instance')
    user = kwargs.get('user')
    answer_to = kwargs.get('answer_to')
    subscription = AnswerSubscription.objects.get_existing(user.profile, answer_to, is_active=True)
    if subscription is not None:
        subscription.send_notification(content=answer, sender=answer.author.profile, send_email=False)


@receiver(publication_read)
def mark_publication_notifications_read(sender, **kwargs):
    publication = kwargs.get('instance')
    user = kwargs.get('user')
    subscription = PublicationSubscription.objects.get_existing(user, publication, is_active=True)
    if subscription is not None:
        subscription.mark_notification_read()

    answer_subscription = AnswerSubscription.objects.get_existing(user, publication, is_active=True)
    if subscription is not None:
        answer_subscription.mark_notification_read()


@receiver(topic_read)
def mark_topic_notifications_read(sender, **kwargs):
    topic = kwargs.get('instance')
    user = kwargs.get('user')

    # Subscription to the topic
    subscription = AnswerSubscription.objects.get_existing(user.profile, topic, is_active=True)
    if subscription is not None:
        subscription.mark_notification_read()

    # Subscription to the forum
    subscription = NewTopicSubscription.objects.get_existing(user.profile, topic.forum, is_active=True)
    if subscription is not None:
        subscription.mark_notification_read(topic=topic)

    # Subscription to the tags
    for tag in topic.tags.all():
        subscription = NewTopicSubscription.objects.get_existing(user.profile, tag, is_active=True)
        if subscription is not None:
            subscription.mark_notification_read(topic=topic)


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
                    object_id=topic.forum.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != topic.author.profile:
                subscription.send_notification(content=topic, sender=topic.author.profile)

        # Notify the tag followers
        content_subscription_type = ContentType.objects.get(model="tag")
        for tag in topic.tags.all():
            subscription_list = NewTopicSubscription.objects\
                .filter(content_type__pk=content_subscription_type.pk,
                        object_id=topic.forum.pk, is_active=True)
            for subscription in subscription_list:
                if subscription.profile != topic.author.profile:
                    subscription.send_notification(content=topic, sender=topic.author.profile)

        # Follow the topic
        subscription = AnswerSubscription.objects.get_existing(topic.author.profile, topic)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = AnswerSubscription(profile=topic.author.profile, content_object=topic)
            subscription.save()


@receiver(post_save, sender=Post)
@disable_for_loaddata
def answer_topic_event(sender, **kwargs):
    if kwargs.get('created', True):
        post = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="topic")
        subscription_list = AnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=post.topic.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != post.author.profile:
                subscription.send_notification(content=post, sender=post.author.profile)

        # Follow topic on answering
        subscription = AnswerSubscription.objects.get_existing(post.author.profile, post.topic)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = AnswerSubscription(profile=post.author.profile, content_object=post.topic)
            subscription.save()


# Article
@receiver(post_save, sender=Reaction)
@disable_for_loaddata
def new_reaction_event(sender, **kwargs):
    if kwargs.get('created', True):
        reaction = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="article")
        subscription_list = AnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=reaction.article.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != reaction.author.profile:
                subscription.send_notification(content=reaction, sender=reaction.author.profile)

        # Follow article on answering
        subscription = AnswerSubscription.objects.get_existing(reaction.author.profile, reaction.article)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = AnswerSubscription(profile=reaction.author.profile, content_object=reaction.article)
            subscription.save()