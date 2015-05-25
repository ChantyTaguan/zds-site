# -*- coding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist

from django.db import models


class SubscriptionManager(models.Manager):
    """
    Custom subscription manager
    """

    def get_existing(self, profile, content_object, is_active=None):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            if is_active is None:
                existing = self.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile)
            else:
                existing = self.get(
                    object_id=content_object.pk,
                    content_type__pk=content_type.pk,
                    profile=profile, is_active=is_active)
        except ObjectDoesNotExist:
            existing = None
        return existing

    def get_or_create_active(self, profile, content_object):
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            subscription = self.get(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                profile=profile)
            if not subscription.is_active:
                subscription.activate()
        except ObjectDoesNotExist:
            subscription = self.model(profile=profile, content_object=content_object)
            subscription.save()

        return subscription

    def get_subscribers(self, content_object, only_by_email=False):
        users = []

        content_type = ContentType.objects.get_for_model(content_object)
        if only_by_email:
            # if I'm only interested by the email subscription
            subscription_list = self.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk,
                by_email=True)
        else:
            subscription_list = self.filter(
                object_id=content_object.pk,
                content_type__pk=content_type.pk)

        for subscription in subscription_list:
            users.append(subscription.profile.user)
        return users

    def get_objects_followed_by(self, profile):
        """
        :return: All objects followed by this user.
        """
        followed_objects = []
        subscription_list = self.filter(profile=self, is_active=True)\
            .order_by('last_notification__pubdate')

        for subscription in subscription_list:
            followed_objects.append(subscription.content_object)

        return followed_objects


class NotificationManager(models.Manager):
    """
    Custom notification manager.
    """

    def get_unread_notifications_of(self, profile):
        return self.filter(subscription__profile=profile, is_read=False)

    def filter_content_type_of(self, model):
        content_subscription_type = ContentType.objects.get_for_model(model)
        return self.filter(subscription__content_type__pk=content_subscription_type.pk)
