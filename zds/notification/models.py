# coding: utf-8
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from django.db import models
from zds.member.models import Profile
from zds.notification.managers import NotificationManager


class Subscription(models.Model):

    """
    Model used to register the subscription of a user to a set of notifications (regarding a tutorial, a forum, ...)
    """
    class Meta:
        verbose_name = _(u'Abonnement')
        verbose_name_plural = _(u'Abonnements')

    profile = models.ForeignKey(Profile, related_name='subscriptor', db_index=True)
    pubdate = models.DateTimeField(_(u'Date de création'), auto_now_add=True, db_index=True)
    active = models.BooleanField(_(u'Actif'), default=True, db_index=True)
    by_email = models.BooleanField(_(u'Recevoir un email'), default=False)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    last_notification = models.ForeignKey(u'Notification', related_name="last_notification", null=True, default=None)

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux notifications pour le {1}, #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def activate_or_save(self, by_email=None):
        """
        Save the subscription if it does not exists yet.
        If it does exists, activates it, (modifying by_email if it is given)
        """
        try:
            existing = self.get_existing()

        except Subscription.DoesNotExist:
            existing = None

        if existing is None:
            if by_email is not None:
                self.by_email = by_email
            self.save()
        else:
            existing.active = True
            if by_email is not None:
                existing.by_email = by_email
            existing.save()

    def deactivate(self):
        """
        Deactivate the corresponding subscription if it exists. Does nothing otherwise
        """
        try:
            existing = self.get_existing()
        except Subscription.DoesNotExist:
            existing = None

        if existing is not None:
            existing.active = False
            existing.save()

    def is_active(self):
        existing = self.get_existing();

        if existing is None:
            return False
        else:
            return existing.active

    def is_by_email(self):
        existing = self.get_existing();

        if existing is None:
            return False
        else:
            return existing.active and existing.by_email

    def get_subscribers(self, only_by_email=False):
        users = []

        if only_by_email:
            # if I'm only interested by the email subscription
            p = Profile.objects.filter(Q(subscription__instance_of=self.__class__)
                                       & Q(subscription__object_id=self.object_id)
                                       & Q(subscription__content_type__pk=self.content_type.pk)
                                       & Q(subscription__active=True)
                                       & Q(subscription__by_email=True)).distinct().all()
        else:
            p = Profile.objects.filter(Q(subscription__instance_of=self.__class__)
                                       & Q(subscription__object_id=self.object_id)
                                       & Q(subscription__content_type__pk=self.content_type.pk)
                                       & Q(subscription__active=True)).distinct().all()

        for profile in p:
            users.append(profile.user)
        return users

    def set_last_notification(self, notification):
        self.last_notification = notification
        self.save()


class AnswerSubscription(Subscription):
    """
    Subscription to new answer, either in a topic, a article or a tutorial
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux réponses au {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_existing(self):
        try:
            existing = AnswerSubscription.objects.get(
                object_id=self.object_id,
                content_type__pk=self.content_type.pk,
                profile=self.profile)
        except AnswerSubscription.DoesNotExist:
            existing = None
        return existing

    def send_notification(self, answer=None, send_email=True):
        if self.last_notification is None or self.last_notification.is_read:
            notification = Notification(subscription=self, content_object=answer, sender=answer.author.profile)
            notification.url = answer.get_absolute_url()
            notification.title = self.content_object.title
            notification.save()
            self.set_last_notification(notification)

            if send_email & self.by_email:
                subject = _(u"{} - {} : {}").format(settings.ZDS_APP['site']['litteral_name'],_(u'Forum'),notification.get_title())
                from_email = _(u"{} <{}>").format(settings.ZDS_APP['site']['litteral_name'],settings.ZDS_APP['site']['email_noreply'])

                receiver = self.profile.user
                context = {
                            'username': receiver.username,
                            'title': notification.get_title(),
                            'url': settings.ZDS_APP['site']['url'] + notification.get_url(),
                            'author': notification.get_author().user.username,
                            'site_name': settings.ZDS_APP['site']['litteral_name']
                }
                message_html = render_to_string(
                            'email/notification/answer_subscription/'
                            + self.content_type.model + '.html', context)
                message_txt = render_to_string(
                            'email/notification/answer_subscription/'
                            + self.content_type.model + '.txt', context)

                msg = EmailMultiAlternatives(subject, message_txt, from_email, [receiver.email])
                msg.attach_alternative(message_html, "text/html")
            msg.send()

    def mark_notification_read(self):
        subscription = self.get_existing();

        if subscription is not None:
            if subscription.last_notification is not None:
                subscription.last_notification.is_read = True
                subscription.last_notification.save()


class UpdateTutorialSubscription(Subscription):
    """
    Subscription to update of a tutorial
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour du tutorial #{1}>')\
            .format(self.profile, self.object_id)

    def get_existing(self):
        try:
            existing = UpdateTutorialSubscription.objects.get(
                object_id=self.object_id,
                content_type__pk=self.content_type.pk,
                profile=self.profile)
        except UpdateTutorialSubscription.DoesNotExist:
            existing = None
        return existing

    def send_notification(self, sender=None):
        if self.last_notification is None or self.last_notification.is_read:
            notification = Notification(subscription=self, sender=sender)
            notification.title = self.content_object.get_title()
            notification.url = reverse('zds.tutorial.views.history', args=[
                self.content_object.pk,
                self.content_object.slug,
            ])
            notification.save()
            self.set_last_notification(notification)

    def mark_notification_read(self):
        subscription = self.get_existing();

        if subscription is not None:
            subscription.last_notification.is_read = True
            subscription.last_notification.save()


class UpdateArticleSubscription(Subscription):
    """
    Subscription to update of a article
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour de l\'article #{1}>')\
            .format(self.profile, self.object_id)

    def get_existing(self):
        try:
            existing = UpdateArticleSubscription.objects.get(
                object_id=self.object_id,
                content_type__pk=self.content_type.pk,
                profile=self.profile)
        except UpdateArticleSubscription.DoesNotExist:
            existing = None
        return existing


    def send_notification(self, sender=None):
        if self.last_notification is None or self.last_notification.is_read:
            notification = Notification(subscription=self, sender=sender)
            notification.title = self.content_object.get_title()
            notification.url = reverse('zds.article.views.history', args=[
                self.content_object.pk,
                self.content_object.slug,
            ])
            notification.save()
            self.set_last_notification(notification)

    def mark_notification_read(self):
        subscription = self.get_existing();

        if subscription is not None:
            subscription.last_notification.is_read = True
            subscription.last_notification.save()


class PublicationSubscription(Subscription):
    """
    Subscription to the publication (public updates) of an article or tutorial
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux publications du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_existing(self):
        try:
            existing = PublicationSubscription.objects.get(
                object_id=self.object_id,
                content_type__pk=self.content_type.pk,
                profile=self.profile)
        except PublicationSubscription.DoesNotExist:
            existing = None
        return existing


    def send_notification(self, validation=None):
        if self.last_notification is None or self.last_notification.is_read:
            notification = Notification(subscription=self, content_object=validation, sender=self.content_object.author)
            notification.url = self.content_object.get_absolute_url_online()
            notification.title = self.content_object.get_title()
            notification.save()
            self.set_last_notification(notification)

    def mark_notification_read(self):
        subscription = self.get_existing();

        if subscription is not None:
            subscription.last_notification.is_read = True
            subscription.last_notification.save()


class NewTopicSubscription(Subscription):
    """
    Subscription to new topics in a forum or with a tag
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux nouveaux sujets du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_existing(self):
        try:
            existing = NewTopicSubscription.objects.get(
                object_id=self.object_id,
                content_type__pk=self.content_type.pk,
                profile=self.profile)
        except NewTopicSubscription.DoesNotExist:
            existing = None
        return existing

    def send_notification(self, topic=None):
        notification = Notification(subscription=self, content_object=topic, sender=topic.author.profile)
        notification.url = topic.get_absolute_url()
        notification.title = topic.title
        notification.save()
        self.set_last_notification(notification)


class PingSubscription(AnswerSubscription):
    """
    Subscription to ping of a user
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mentions>')\
            .format(self.profile, self.object_id)

    def get_existing(self):
        return PingSubscription.objects.get(
            object_id=self.object_id,
            content_type__pk=self.content_type.pk,
            profile=self.profile)


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
    url = models.CharField('Titre', max_length=200)
    sender = models.ForeignKey(Profile, related_name='sender', db_index=True)
    title = models.CharField('Titre', max_length=200)
    objects = NotificationManager()

    def __unicode__(self):
        return _(u'Notification du membre "{0}" à propos de : {1} #{2} ({3})')\
            .format(self.subscription.profile, self.content_type, self.content_object.pk, self.subscription)