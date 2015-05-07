import django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.template.loader import render_to_string
from zds.article.models import Reaction, Article
from zds.forum.models import Topic, Post
from zds.notification.models import Notification, Subscription, activate_subscription
from django.utils.translation import ugettext_lazy as _


# General
answer_unread = Signal(providing_args=["instance", "user"])
content_read = Signal(providing_args=["instance", "user"])

@receiver(answer_unread)
def unread_post_event(sender, **kwargs):
    post = kwargs.get('instance')
    user = kwargs.get('user')
    send_notification(post.topic, post, user)


@receiver(content_read)
def test_signals(sender, **kwargs):
    content = kwargs.get('instance')
    user = kwargs.get('user')
    mark_notification_read(content, user)

# Forums
@receiver(post_save, sender=Topic)
def saved_topic_event(sender, **kwargs):
    if kwargs.get('created', True):
        topic = kwargs.get('instance')

        # Notify the forum followers
        send_notification(topic.forum, topic, topic.author)

        # Notify the tag followers
        for tag in topic.tags.all():
            send_notification(tag, topic, topic.author)

        # Follow the topic
        activate_subscription(topic, topic.author, is_multiple=False)


@receiver(post_save, sender=Post)
def answer_topic_event(sender, **kwargs):
    if kwargs.get('created', True):
        post = kwargs.get('instance')

        send_notification(post.topic, post, post.author)

        # Follow topic on answering
        activate_subscription(post.topic, post.author, is_multiple=False)


# Article
@receiver(post_save, sender=Reaction)
def new_reaction_event(sender, **kwargs):
    if kwargs.get('created', True):
        reaction = kwargs.get('instance')

        send_notification(reaction.article, reaction, reaction.author)

        # Follow topic on answering
        activate_subscription(reaction.article, reaction.author, is_multiple=False)


def send_notification(content_subscription, content_notification, action_by, type_notification='NEW_CONTENT'):
    if content_subscription is None:
        return
    elif content_subscription is not None:
        content_subscription_type = ContentType.objects.get_for_model(content_subscription)
        subscription_list = Subscription.objects\
            .filter(object_id=content_subscription.pk, content_type__pk=content_subscription_type.pk,
                    is_active=True, type=type_notification)
        for subscription in subscription_list:
            if action_by == subscription.profile.user:
                continue
            elif not subscription.is_multiple and subscription.last_notification is not None and not subscription.last_notification.is_read:
                # there's already an unread notification for that subscription and only ne is allowed
                if subscription.last_notification.content_object.position > content_notification.position:
                    # if the content of the new notification is older, it replaces the current notification
                    subscription.last_notification.content_object = content_notification
                    subscription.last_notification.save()
                    subscription.save()
            else:
                notification = Notification(subscription=subscription, content_object=content_notification)
                notification.save()
                subscription.last_notification=notification
                subscription.save()
                if subscription.by_email:
                    subject = _(u"{} - {} : {}").format(settings.ZDS_APP['site']['litteral_name'],_(u'Forum'),notification.get_title())
                    from_email = _(u"{} <{}>").format(settings.ZDS_APP['site']['litteral_name'],settings.ZDS_APP['site']['email_noreply'])

                    receiver = subscription.profile.user
                    context = {
                        'username': receiver.username,
                        'title': notification.get_title(),
                        'url': settings.ZDS_APP['site']['url'] + notification.get_url(),
                        'author': notification.get_author().user.username,
                        'site_name': settings.ZDS_APP['site']['litteral_name']
                    }
                    message_html = render_to_string(
                        'email/notification/'
                        + subscription.type.lower()
                        + '/' + content_subscription_type.model + '.html', context)
                    message_txt = render_to_string(
                        'email/notification/'
                        + subscription.type.lower()
                        + '/' + content_subscription_type.model + '.txt', context)

                    msg = EmailMultiAlternatives(subject, message_txt, from_email, [receiver.email])
                    msg.attach_alternative(message_html, "text/html")
                    msg.send()


def mark_notification_read(content, user):
    content_type = ContentType.objects.get_for_model(content)

    try:
        notif = Notification.objects.get(subscription__profile=user.profile, is_read=False,
                                         subscription__object_id=content.pk,
                                         subscription__content_type__pk=content_type.pk,
                                         subscription__is_multiple=False)

    except Notification.DoesNotExist:
        notif = None
    if notif is not None:
        notif.is_read = True
        notif.save()

    notifications = Notification.objects.filter(subscription__profile=user.profile, is_read=False,
                                                object_id=content.pk,
                                                content_type__pk=content_type.pk)

    for notif in notifications:
        notif.is_read = True
        notif.save()
