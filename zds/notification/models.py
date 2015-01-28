# coding: utf-8
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from zds.member.models import Profile

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
    is_active = models.BooleanField('Actif', default=False, db_index=True)
    by_email = models.BooleanField('Recevoir un email', default=False)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    last_notification = models.ForeignKey('Notification', related_name="last_notification", default=None)

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
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    is_read = models.BooleanField('Lue', default=False, db_index=True)

    def __unicode__(self):
        return u'Notification du membre "{0}" à propos de : {1} #{2}'.format(self.user,
                                                                             self.content_type.model_class(),
                                                                             self.content_object.pk)

def send_notification(type_notif, content_subscription = None, content_notification = None):
    if content_notification is None & type_notif != 'PING':
        return
    else:
        subscription_list = Subscription.objects.filter(content_object=content_subscription, is_active=True)
        for subscription in subscription_list:
            if content_notification.user == subscription.profile.user:
                return
            else:
                notification = Notification(subscription=subscription, content_object=content_notification)
                notification.save()
                #if subscription.by_email: