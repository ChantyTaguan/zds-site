# coding: utf-8
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from django.db import models
from zds.member.models import Profile
from zds.notification.managers import NotificationManager, SubscriptionManager


class Subscription(models.Model):

    """
    Model used to register the subscription of a user to a set of notifications (regarding a tutorial, a forum, ...)
    """
    class Meta:
        verbose_name = _(u'Abonnement')
        verbose_name_plural = _(u'Abonnements')

    profile = models.ForeignKey(Profile, related_name='subscriptor', db_index=True)
    pubdate = models.DateTimeField(_(u'Date de création'), auto_now_add=True, db_index=True)
    is_active = models.BooleanField(_(u'Actif'), default=True, db_index=True)
    by_email = models.BooleanField(_(u'Recevoir un email'), default=False)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    last_notification = models.ForeignKey(u'Notification', related_name="last_notification", null=True, default=None)

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux notifications pour le {1}, #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def activate(self):
        """
        Activates the subscription if it's inactive. Does nothing otherwise
        """
        if not self.is_active:
            self.is_active = True
            self.save()

    def activate_email(self):
        """
        Acitvates the notifications by email (and the subscription itself if needed)
        """
        if not self.is_active or not self.by_email:
            self.is_active = True
            self.by_email = True
            self.save()

    def deactivate(self):
        """
        Deactivate the subscription if it is active. Does nothing otherwise
        """
        if self.is_active:
            self.is_active = False
            self.save()

    def deactivate_email(self):
        """
        Deactivate the email if it is active. Does nothing otherwise
        """
        if self.is_active and self.by_email:
            self.by_email = False
            self.save()

    def set_last_notification(self, notification):
        """
        Replace last_notification by the one given
        """
        self.last_notification = notification
        self.save()

    def send_email(self, notification):
        """
        Sends an email notification
        """

        assert hasattr(self, "module")

        subject = _(u"{} - {} : {}").format(settings.ZDS_APP['site']['litteral_name'],self.module,notification.title)
        from_email = _(u"{} <{}>").format(settings.ZDS_APP['site']['litteral_name'],settings.ZDS_APP['site']['email_noreply'])

        receiver = self.profile.user
        context = {
            'username': self.profile.user.username,
            'title': notification.title,
            'url': settings.ZDS_APP['site']['url'] + notification.url,
            'author': notification.sender.user.username,
            'site_name': settings.ZDS_APP['site']['litteral_name']
        }
        message_html = render_to_string('email/notification/' + self._meta.model_name + '.html', context)
        message_txt = render_to_string('email/notification/' + self._meta.model_name + '.txt', context)

        msg = EmailMultiAlternatives(subject, message_txt, from_email, [receiver.email])
        msg.attach_alternative(message_html, "text/html")
        msg.send()


class SingleNotificationMixin(object):
    """
    Mixin for the subscription that can only have one active notification at a time
    """
    def send_notification(self, content=None, send_email=True, sender=None):
        """
        Sends the notification about the given content
        :param content:  the content the notification is about
        :param sender: the user whose action triggered the notification
        :param send_email : whether an email must be sent if the subscription by email is active
        """
        assert hasattr(self, "get_notification_url")
        assert hasattr(self, "get_notification_title")
        assert hasattr(self, "send_email")

        # If the last notification has not been read yet, no new notification is sent
        if self.last_notification is None or self.last_notification.is_read:
            notification = Notification(subscription=self, content_object=content, sender=sender)
            notification.url = self.get_notification_url(content)
            notification.title = self.get_notification_title(content)
            notification.save()
            self.set_last_notification(notification)
            self.save()

            if send_email & self.by_email:
                self.send_email(notification)
        elif self.last_notification is not None:
            # Update last notif if the new content is older (case of unreading answer)
            if not self.last_notification.is_read and self.last_notification.pubdate > content.pubdate:
                self.last_notification.content_object = content
                self.last_notification.save()

    def mark_notification_read(self):
        """
        Marks the notification of the subscription as read.
        As there's only one active unread notification at all time,
        no need for more precision
        """
        if self.last_notification is not None:
            self.last_notification.is_read = True
            self.last_notification.save()


class MultipleNotificationsMixin(object):

    def send_notification(self, content=None, send_email=True, sender=None):
        """
        Sends the notification about the given content
        :param content:  the content the notification is about
        :param sender: the user whose action triggered the notification
        :param send_email : whether an email must be sent if the subscription by email is active
        """

        assert hasattr(self, "get_notification_url")
        assert hasattr(self, "get_notification_title")
        assert hasattr(self, "send_email")

        notification = Notification(subscription=self, content_object=content, sender=sender)
        notification.url = self.get_notification_url(content)
        notification.title = self.get_notification_title(content)
        notification.save()
        self.set_last_notification(notification)

        if send_email & self.by_email:
            self.send_email(notification)

    def mark_notification_read(self, content):
        """
        Marks the notification of the subscription as read.
        :param content : the content whose notification has been read
        """
        if content is None:
            raise Exception('Object content of notification must be defined')

        content_notification_type = ContentType.objects.get_for_model(content)
        try:
            notification = Notification.objects.get(subscription=self,
                                                    content_type__pk=content_notification_type.pk,
                                                    object_id=content.pk, is_read=False)
        except Notification.DoesNotExist:
            notification = None
        if notification is not None:
            notification.is_read = True
            notification.save()


class AnswerSubscription(Subscription):
    """
    Subscription to new answer, either in a topic, a article or a tutorial
    NOT used directly, use one of its subtype
    """
    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux réponses au {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_notification_url(self, answer):
        return answer.get_absolute_url()

    def get_notification_title(self, answer):
        return self.content_object.title


class TopicAnswerSubscription(AnswerSubscription, SingleNotificationMixin):
    """
    Subscription to new answer in a topic
    """
    module = _(u'Forum')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux réponses au sujet #{1}>')\
            .format(self.profile, self.object_id)



class ArticleAnswerSubscription(AnswerSubscription, SingleNotificationMixin):
    """
    Subscription to new answer (comment) in an article
    """
    module = _(u'Article')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux réponses à l\'article #{1}>')\
            .format(self.profile, self.object_id)


class TutorialAnswerSubscription(AnswerSubscription, SingleNotificationMixin):
    """
    Subscription to new answer (comment) in a tutorial
    """
    module = _(u'Tutoriel')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux réponses au tutoriel #{1}>')\
            .format(self.profile, self.object_id)


class UpdateTutorialSubscription(Subscription, SingleNotificationMixin):
    """
    Subscription to update of a tutorial
    """
    module = _(u'Tutoriel')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour du tutoriel #{1}>')\
            .format(self.profile, self.object_id)

    def get_notification_url(self, tutorial):
        return reverse('zds.tutorial.views.history', args=[
                    tutorial.pk,
                    tutorial.slug,
                ])

    def get_notification_url(self, tutorial):
        return tutorial.title


class UpdateArticleSubscription(Subscription, SingleNotificationMixin):
    """
    Subscription to update of a article
    """
    module = _(u'Article')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux mises à jour de l\'article #{1}>')\
            .format(self.profile, self.object_id)

    def get_notification_url(self, article):
        return reverse('zds.tutorial.views.history', args=[
                    article.pk,
                    article.slug,
                ])

    def get_notification_title(self, article):
        return article.title


class PublicationSubscription(Subscription):
    """
    Subscription to the publication (public updates) of an article or tutorial
    Do NOT use this directly, use one of its two subtypes
    """
    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux publications du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_notification_url(self, publication):
        return publication.get_absolute_url_online()

    def get_notification_url(self, publication):
        return publication.title


class ArticlePublicationSubscription(PublicationSubscription, SingleNotificationMixin):
    """
    Subscription to the publication (public updates) of an article
    """
    module = _(u'Article')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux publications de l\'article #{1}>')\
            .format(self.profile, self.object_id)


class TutorialPublicationSubscription(PublicationSubscription, SingleNotificationMixin):
    """
    Subscription to the publication (public updates) of an article
    """
    module = _(u'Tutoriel')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux publications du tutoriel #{1}>')\
            .format(self.profile, self.object_id)


class NewTopicSubscription(Subscription, MultipleNotificationsMixin):
    """
    Subscription to new topics in a forum or with a tag
    """
    module = _(u'Forum')
    objects = SubscriptionManager()

    def __unicode__(self):
        return _(u'<Abonnement du membre "{0}" aux nouveaux sujets du {1} #{2}>')\
            .format(self.profile, self.content_type, self.object_id)

    def get_notification_url(self, topic):
        return topic.get_absolute_url()

    def get_notification_title(self, topic):
        return topic.title


class PingSubscription(AnswerSubscription):
    """
    Subscription to ping of a user
    """
    module = _(u'Forum')
    objects = SubscriptionManager()

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
