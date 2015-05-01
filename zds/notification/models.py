# coding: utf-8
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from zds.member.models import Profile
from zds.utils import get_current_user

TYPE_CHOICES = (
    ('UPDATE', 'Mise à jour'),
    ('NEW_CONTENT', 'Nouveau contenu'),
    ('PING', 'Mention')
)


class Subscription(models.Model):

    """
    Model used to register the subscription of a user to a set of notifications (regarding a tutorial, a forum, ...)
    """
    class Meta:
        verbose_name = 'Abonnement'
        verbose_name_plural = 'Abonnements'

    profile = models.ForeignKey(Profile, related_name='subscriptor', db_index=True)
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='NEW_CONTENT', db_index=True)
    pubdate = models.DateTimeField(u'Date de création', auto_now_add=True, db_index=True)
    is_active = models.BooleanField('Actif', default=True, db_index=True)
    by_email = models.BooleanField('Recevoir un email', default=False)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    last_notification = models.ForeignKey('Notification', related_name="last_notification", null=True, default=None)

    def __unicode__(self):
        return u'<Abonnement du membre "{0}" aux notifications ' \
               u'de type {1} pour le {2}, #{3}>'.format(self.profile,
                                                        self.type,
                                                        self.content_type,
                                                        self.content_object.pk)


class Notification(models.Model):
    """
    A notification
    """
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    subscription = models.ForeignKey('Subscription', related_name='subscription', db_index=True)
    pubdate = models.DateTimeField(u'Date de création', auto_now_add=True, db_index=True)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    is_read = models.BooleanField('Lue', default=False, db_index=True)

    def __unicode__(self):
        return u'Notification du membre "{0}" à propos de : {1} #{2}'\
            .format(self.subscription.profile, self.content_type, self.content_object.pk)

    def get_author(self):
        return self.content_object.author

    def get_url(self):
        return self.content_object.get_absolute_url()

    def get_title(self):
        if self.content_type == ContentType.objects.get(model="post"):
            return self.content_object.topic.title
        elif self.content_type == ContentType.objects.get(model="private_post"):
            return self.content_object.privatetopic.title
        else:
            return self.subscription.type


def send_notification(content_subscription, content_notification, action_by=None, type_notification='NEW_CONTENT'):
    if content_subscription is None:
        return
    elif content_subscription is not None:
        content_subscription_type = ContentType.objects.get_for_model(content_subscription)
        subscription_list = Subscription.objects\
            .filter(object_id=content_subscription.pk, content_type__pk=content_subscription_type.pk,
                    is_active=True, type=type_notification)
        for subscription in subscription_list:
            if (action_by is not None and action_by == subscription.profile.user) \
                    or (subscription.last_notification is not None and not subscription.last_notification.is_read):
                continue
            else:
                notification = Notification(subscription=subscription, content_object=content_notification)
                notification.save()
                subscription.last_notification=notification
                subscription.save()
                # if subscription.by_email:


def activate_subscription(content_subscription, user=None, type_subscription=None):
    """create a subscription if it does not exists, activate the existing subscription if it's not active"""

    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

    if type_subscription is None:
        type_subscription = 'NEW_CONTENT'
    if user is None:
        user = get_current_user()
    try:
        existing = Subscription.objects.get(object_id=content_subscription.pk,
                                            content_type__pk=content_subscription_type.pk,
                                            profile=user.profile, type=type_subscription)
    except Subscription.DoesNotExist:
        existing = None

    if not existing:
        # Make the user follow the topic
        t = Subscription(
            content_object=content_subscription,
            profile=user.profile,
            type=type_subscription
        )

        t.save()
    else:
        # Activate the existing subscription if it is inactive
        if not existing.is_active:
            existing.is_active = True
            existing.save()


def deactivate_subscription(content_subscription, user=None, type_subscription=None):
    """Deactivate the subscription if it does exists and is active"""

    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

    if type_subscription is None:
        type_subscription = 'NEW_CONTENT'
    if user is None:
        user = get_current_user()
    try:
        existing = Subscription.objects.get(object_id=content_subscription.pk,
                                            content_type__pk=content_subscription_type.pk,
                                            profile=user.profile, type=type_subscription, is_active=True)
        existing.is_active = False
        existing.save()
    except Subscription.DoesNotExist:
        existing = None


def mark_notification_read(content_subscription):
    user = get_current_user()
    content_subscription_type = ContentType.objects.get_for_model(content_subscription)
    n = Notification.objects.filter(subscription__profile=user.profile, is_read=False,
                                    subscription__object_id=content_subscription.pk,
                                    subscription__content_type__pk=content_subscription_type.pk)
    for notification in n:
        notification.is_read = True
        notification.save()


def has_subscribed(content_subscription, user=None, type_subscription='NEW_CONTENT'):
    if user is None:
        user = get_current_user()

    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

    try:
        existing = Subscription.objects.get(object_id=content_subscription.pk,
                                            content_type__pk=content_subscription_type.pk,
                                            profile=user.profile, type=type_subscription)
    except Subscription.DoesNotExist:
        existing = None

    return existing is not None