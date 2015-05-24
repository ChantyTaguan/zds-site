from functools import wraps
import django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver, Signal
from zds.article.models import Reaction, Article
from zds.forum.models import Post, Topic

from zds.notification.models import NewTopicSubscription, Notification, TopicAnswerSubscription, \
    TutorialAnswerSubscription, ArticleAnswerSubscription, TutorialPublicationSubscription, \
    ArticlePublicationSubscription, UpdateTutorialSubscription, UpdateArticleSubscription
from zds.tutorial.models import Tutorial, Note


def disable_for_loaddata(signal_handler):
    """
    Decorator
    Avoid the signal to be treated when sent by fixtures
    """
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        if "raw" in kwargs and kwargs['raw']:
            print "Skipping signal for %s %s" % (args, kwargs)
            return
        signal_handler(*args, **kwargs)
    return wrapper

# is sent whenever an answer is set as unread
answer_unread = Signal(providing_args=["instance", "user"])

# is sent when a content is read (topic, article or tutorial)
content_read = Signal(providing_args=["instance", "user"])

@receiver(answer_unread, sender=Topic)
@disable_for_loaddata
def unread_topic_event(sender, **kwargs):
    """
    :param kwargs: contains
        - instance : the answer being marked as unread
        - user : user marking the answer as unread
    Sends a notification to the user, without sending an email
    """
    answer = kwargs.get('instance')
    user = kwargs.get('user')
    subscription = TopicAnswerSubscription.objects.get_existing(user.profile, answer.topic, is_active=True)
    if subscription is not None:
        subscription.send_notification(content=answer, sender=answer.author.profile, send_email=False)


@receiver(content_read, sender=Tutorial)
def mark_tutorial_notifications_read(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the tutorial marked as read
        - user : the user reading the tutorial

        Marks as read the notifications of the PublicationSubscription
        and AnswerSubscription of the user to the tutorial
    """
    tutorial = kwargs.get('instance')
    user = kwargs.get('user')
    subscription = TutorialPublicationSubscription.objects.get_existing(user, tutorial, is_active=True)
    if subscription is not None:
        subscription.mark_notification_read()

    answer_subscription = TutorialAnswerSubscription.objects.get_existing(user, tutorial, is_active=True)
    if subscription is not None:
        answer_subscription.mark_notification_read()


@receiver(content_read, sender=Article)
def mark_article_notifications_read(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the article marked as read
        - user : the user reading the article

        Marks as read the notifications of the PublicationSubscription
        and AnswerSubscription of the user to the article
    """
    article = kwargs.get('instance')
    user = kwargs.get('user')
    subscription = ArticlePublicationSubscription.objects.get_existing(user, article, is_active=True)
    if subscription is not None:
        subscription.mark_notification_read()

    answer_subscription = ArticleAnswerSubscription.objects.get_existing(user, article, is_active=True)
    if subscription is not None:
        answer_subscription.mark_notification_read()


@receiver(content_read, sender=Topic)
def mark_topic_notifications_read(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the topic marked as read
        - user : the user reading the topic

        Marks as read the notifications of the NewTopicSubscriptions
        and AnswerSubscription of the user to the topic
    """
    topic = kwargs.get('instance')
    user = kwargs.get('user')

    # Subscription to the topic
    subscription = TopicAnswerSubscription.objects.get_existing(user.profile, topic, is_active=True)
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


@receiver(post_save, sender=Topic)
@disable_for_loaddata
def saved_topic_event(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the new topic

        Sends NewTopicSubscription to the subscribers to the forum of the topic
        and subscribe the author to the answers of the topic
    """
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

        # Follow the topic
        subscription = TopicAnswerSubscription.objects.get_existing(topic.author.profile, topic)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = TopicAnswerSubscription(profile=topic.author.profile, content_object=topic)
            subscription.save()


@receiver(m2m_changed, sender=Topic.tags.through)
@disable_for_loaddata
def add_tags_topic_event(sender, **kwargs):
    """
    Sent when there is a change in the many2many relationship between topic and tags
    :param kwargs:  contains
        - sender : the technical class representing the many2many relationship
        - instance : the technical class representing the many2many relationship
        - action : "pre_add", "post_add", ... action having sent the signal
        - reverse : indicates which side of the relation is updated
            (from what I understand, forward is from topic to tags, so when the tag side is modified,
            reverse is from tags to topics, so when the topics are modified)

        Sends NewTopicSubscription to the subscribers to the tags added to the topic
    """

    topic = kwargs.get('instance')
    action = kwargs.get('action')
    reverse = kwargs.get('reverse')

    if action == 'post_add' and not reverse:
        content_subscription_type = ContentType.objects.get(model="tag")
        for tag in topic.tags.all():
            subscription_list = NewTopicSubscription.objects\
                .filter(content_type__pk=content_subscription_type.pk,
                        object_id=tag.pk, is_active=True)
            for subscription in subscription_list:
                if subscription.profile != topic.author.profile:
                    subscription.send_notification(content=topic, sender=topic.author.profile)


@receiver(m2m_changed, sender=Article.authors.through)
@disable_for_loaddata
def add_author_article_event(sender, **kwargs):
    """
    Sent when there is a change in the many2many relationship between topic and tags
    :param kwargs:  contains
        - sender : the technical class representing the many2many relationship
        - instance : the technical class representing the many2many relationship
        - action : "pre_add", "post_add", ... action having sent the signal
        - reverse : indicates which side of the relation is updated
            (from what I understand, forward is from article to users, so when the users side is modified,
            reverse is from users to article, so when the articles are modified)

        Subscribes the authors to the UpdateSubscription, unsubscribe the leaving authors
    """

    article = kwargs.get('instance')
    action = kwargs.get('action')
    reverse = kwargs.get('reverse')

    if action == 'post_add' and not reverse:
        for user in article.authors.all():
            existingUpdate = UpdateArticleSubscription.objects.get_existing(profile=user.profile, content_object=article)
            if existingUpdate is None :
                subscription = UpdateArticleSubscription(profile=user.profile, content_object=article)
                subscription.save()

            existingAnswer = ArticleAnswerSubscription.objects.get_existing(profile=user.profile, content_object=article)
            if existingUpdate is None :
                subscription = ArticleAnswerSubscription(profile=user.profile, content_object=article)
                subscription.save()

    if action == 'post_delete' and not reverse:
        subscribers = UpdateArticleSubscription.objects.get_subscribers(content_object=article)
        for user in subscribers:
            if user not in article.authors.all() :
                subscription = UpdateArticleSubscription.objects.get_existing(
                    profile=user.profile, content_object=article)
                subscription.deactivate()


@receiver(post_save, sender=Post)
@disable_for_loaddata
def answer_topic_event(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the new post

        Sends TopicAnswerSubscription to the subscribers to the topic
        and subscribe the author to the following answers to the topic
    """

    if kwargs.get('created', True):
        post = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="topic")
        subscription_list = TopicAnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=post.topic.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != post.author.profile:
                subscription.send_notification(content=post, sender=post.author.profile)

        # Follow topic on answering
        subscription = TopicAnswerSubscription.objects.get_existing(post.author.profile, post.topic)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = TopicAnswerSubscription(profile=post.author.profile, content_object=post.topic)
            subscription.save()


@receiver(post_save, sender=Reaction)
@disable_for_loaddata
def new_reaction_event(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the new reaction

        Sends ArticleAnswerSubscription to the subscribers to the article
        and subscribe the author to the following answers to the article
    """
    if kwargs.get('created', True):
        reaction = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="article")
        subscription_list = ArticleAnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=reaction.article.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != reaction.author.profile:
                subscription.send_notification(content=reaction, sender=reaction.author.profile)

        # Follow article on answering
        subscription = ArticleAnswerSubscription.objects.get_existing(reaction.author.profile, reaction.article)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = ArticleAnswerSubscription(profile=reaction.author.profile, content_object=reaction.article)
            subscription.save()


@receiver(post_save, sender=Note)
@disable_for_loaddata
def new_note_event(sender, **kwargs):
    """
    :param kwargs:  contains
        - instance : the new note

        Sends TutorialAnswerSubscription to the subscribers to the tutorial
        and subscribe the author to the following answers to the tutorial
    """
    if kwargs.get('created', True):
        note = kwargs.get('instance')

        content_subscription_type = ContentType.objects.get(model="article")
        subscription_list = TutorialAnswerSubscription.objects\
            .filter(content_type__pk=content_subscription_type.pk,
                    object_id=note.tutorial.pk, is_active=True)
        for subscription in subscription_list:
            if subscription.profile != note.author.profile:
                subscription.send_notification(content=note, sender=note.author.profile)

        # Follow tutorial on answering
        subscription = TutorialAnswerSubscription.objects.get_existing(note.author.profile, note.tutorial)
        if subscription is not None:
            subscription.activate()
        else:
            subscription = TutorialAnswerSubscription(profile=note.author.profile, content_object=note.tutorial)
            subscription.save()