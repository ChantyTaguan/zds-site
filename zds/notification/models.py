# coding: utf-8
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import ugettext_lazy as _

from django.db import models
from django.template.loader import render_to_string
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
        verbose_name = _(u'Abonnement')
        verbose_name_plural = _(u'Abonnements')

    profile = models.ForeignKey(Profile, related_name='subscriptor', db_index=True)
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='NEW_CONTENT', db_index=True)
    pubdate = models.DateTimeField(_(u'Date de création'), auto_now_add=True, db_index=True)
    is_active = models.BooleanField(_(u'Actif'), default=True, db_index=True)
    by_email = models.BooleanField(_(u'Recevoir un email'), default=False)
    is_multiple = models.BooleanField(_(u'Peut contenir plusieurs notifications non lues simultanées'), default=True)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    last_notification = models.ForeignKey(u'Notification', related_name="last_notification", null=True, default=None)

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux notifications ' \
                 u'de type {1} pour le {2}, #{3}>').format(self.profile,
                                                           self.type,
                                                           self.content_type,
                                                           self.content_object.pk)


class Notification(models.Model):
    """
    A notification
    """
    class Meta:
        verbose_name = _(u'Notification')
        verbose_name_plural = _(u'Notifications')

    subscription = models.ForeignKey(u'Subscription', related_name='subscription', db_index=True)
    pubdate = models.DateTimeField(_(u'Date de création'), auto_now_add=True, db_index=True)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    is_read = models.BooleanField(_(u'Lue'), default=False, db_index=True)

    def __unicode__(self):
        return _(u'Notification du membre "{0}" à propos de : {1} #{2}')\
            .format(self.subscription.profile, self.content_type, self.content_object.pk)

    def get_author(self):
        return self.content_object.author

    def get_url(self):
        if self.content_type == ContentType.objects.get(model="article") or self.content_type == ContentType.objects.get(model="tutorial"):
            return self.content_object.get_absolute_url_online()
        else:
            return self.content_object.get_absolute_url()

    def get_title(self):
        if self.content_type == ContentType.objects.get(model="post"):
            return self.content_object.topic.title
        elif self.content_type == ContentType.objects.get(model="reaction"):
            return self.subscription.content_object.title
        else:
            return self.content_object.title


def activate_subscription(content_subscription, user=None, type_subscription=None, by_email=False, is_multiple=True):
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
        t = Subscription(content_object=content_subscription,
                         profile=user.profile, type=type_subscription,
                         by_email=by_email, is_multiple=is_multiple)
        t.save()
    else:
        # Activate the existing subscription if it is inactive
        if not existing.is_active:
            existing.is_active = True
            if by_email:
                existing.by_email = True
            existing.save()


def deactivate_email_subscription(content_subscription, user=None, type_subscription='NEW_CONTENT'):
    """Deactivate the email subscription if it does exists and is active"""

    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

    if user is None:
        user = get_current_user()
    try:
        existing = Subscription.objects.get(object_id=content_subscription.pk,
                                            content_type__pk=content_subscription_type.pk,
                                            profile=user.profile, type=type_subscription, is_active=True, by_email=True)
        existing.by_email = False
        existing.save()
    except Subscription.DoesNotExist:
        existing = None

def deactivate_subscription(content_subscription, user=None, type_subscription='NEW_CONTENT'):
    """Deactivate the subscription if it does exists and is active"""

    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

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


def has_subscribed(content_subscription, user=None, type_subscription='NEW_CONTENT', by_email=False):
    if user is None:
        user = get_current_user()

    try:
        content_subscription_type = ContentType.objects.get_for_model(content_subscription)
        existing = Subscription.objects.get(object_id=content_subscription.pk,
                                            content_type__pk=content_subscription_type.pk,
                                            profile=user.profile, type=type_subscription, is_active=True)
    except AttributeError:
        pk = content_subscription['pk']
        content_subscription_type = ContentType.objects.get(model=content_subscription['type'])

        try:
            existing = Subscription.objects.get(object_id=pk,
                                                content_type__pk=content_subscription_type.pk,
                                                profile=user.profile, type=type_subscription, is_active=True)

        except Subscription.DoesNotExist:
            existing = None

    except Subscription.DoesNotExist:
        existing = None

    res = existing is not None

    # if I'm only interested by the email subscription
    if res and by_email:
        res = existing.by_email

    return res


def get_subscribers(content_subscription, type_subscription='NEW_CONTENT', only_by_email=False):
    users = []
    content_subscription_type = ContentType.objects.get_for_model(content_subscription)

    if only_by_email:
        # if I'm only interested by the email subscription
        p = Profile.objects.filter(
            subscription__object_id=content_subscription.pk, subscription__content_type__pk=content_subscription_type.pk,
            subscription__is_active=True, type=type_subscription, by_email=True).distinct().all()
    else:
        p = Profile.objects.filter(
            subscription__object_id=content_subscription.pk, subscription__content_type__pk=content_subscription_type.pk,
            subscription__is_active=True, type=type_subscription).distinct().all()

    for profile in p:
        users.append(profile.user)
    return users

