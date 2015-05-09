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

    def activate(self, by_email=False):
        """
        Activates the subscription if it's inactive
        """
        changed = False
        if not self.active:
            self.active = True
            changed = True
        if by_email and not self.by_email:
            self.by_email = by_email
            changed = True
        if changed:
            self.save()

    def deactivate(self):
        """
        Deactivate the subscription if it is active. Does nothing otherwise
        """
        if self.active:
            self.active = False
            self.save()

    def deactivate_email(self):
        """
        Deactivate the email if it is active. Does nothing otherwise
        """
        if self.active and self.by_email:
            self.by_email = False
            self.save()

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

    @staticmethod
    def get_existing(profile, content_object, active=False):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if active:
                existing = AnswerSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, active=True)
            else:
                existing = AnswerSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
        except AnswerSubscription.DoesNotExist:
            existing = None
        return existing

    @staticmethod
    def get_subscribers(content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = AnswerSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = AnswerSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def send_notification(self, answer=None, send_email=True):
        if self.active:
            if self.last_notification is None or self.last_notification.is_read:
                notification = Notification(subscription=self, content_object=answer, sender=answer.author.profile)
                notification.url = answer.get_absolute_url()
                notification.title = self.content_object.title
                notification.save()
                self.set_last_notification(notification)
                self.save()

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
            elif self.last_notification is not None:
                if not self.last_notification.is_read and self.last_notification.pubdate > answer.pubdate:
                    self.last_notification.content_object = answer
                    self.last_notification.save()

    def mark_notification_read(self):
        if self.last_notification is not None:
            self.last_notification.is_read = True
            self.last_notification.save()


class UpdateTutorialSubscription(Subscription):
    """
    Subscription to update of a tutorial
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour du tutorial #{1}>')\
            .format(self.profile, self.object_id)

    @staticmethod
    def get_existing(profile, content_object, active=False):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if active:
                existing = UpdateTutorialSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, active=True)
            else:
                existing = UpdateTutorialSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
        except UpdateTutorialSubscription.DoesNotExist:
            existing = None
        return existing

    @staticmethod
    def get_subscribers(content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = UpdateTutorialSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = UpdateTutorialSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def send_notification(self, sender=None):
        if self.active:
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
        if self.last_notification is not None:
            self.last_notification.is_read = True
            self.last_notification.save()


class UpdateArticleSubscription(Subscription):
    """
    Subscription to update of a article
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour de l\'article #{1}>')\
            .format(self.profile, self.object_id)

    @staticmethod
    def get_existing(profile, content_object, active=False):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if active:
                existing = UpdateArticleSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, active=True)
            else:
                existing = UpdateArticleSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
        except UpdateArticleSubscription.DoesNotExist:
            existing = None
        return existing

    @staticmethod
    def get_subscribers(content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = UpdateArticleSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = UpdateArticleSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def send_notification(self, sender=None):
        if self.active:
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
        if self.last_notification is not None:
            self.last_notification.is_read = True
            self.last_notification.save()


class PublicationSubscription(Subscription):
    """
    Subscription to the publication (public updates) of an article or tutorial
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux publications du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    @staticmethod
    def get_existing(profile, content_object, active=False):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if active:
                existing = PublicationSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, active=True)
            else:
                existing = PublicationSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
        except PublicationSubscription.DoesNotExist:
            existing = None
        return existing

    @staticmethod
    def get_subscribers(content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = PublicationSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = PublicationSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def send_notification(self, validation=None):
        if self.active:
            if self.last_notification is None or self.last_notification.is_read:
                notification = Notification(subscription=self, content_object=validation, sender=self.content_object.author)
                notification.url = self.content_object.get_absolute_url_online()
                notification.title = self.content_object.get_title()
                notification.save()
                self.set_last_notification(notification)

    def mark_notification_read(self):
        self.last_notification.is_read = True
        self.last_notification.save()


class NewTopicSubscription(Subscription):
    """
    Subscription to new topics in a forum or with a tag
    """

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux nouveaux sujets du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    @staticmethod
    def get_existing(profile, content_object, active=False):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if active:
                existing = NewTopicSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, active=True)
            else:
                existing = NewTopicSubscription.objects.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
        except NewTopicSubscription.DoesNotExist:
            existing = None
        return existing

    @staticmethod
    def get_subscribers(content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = NewTopicSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = NewTopicSubscription.objects.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def send_notification(self, topic=None):
        if self.active:
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