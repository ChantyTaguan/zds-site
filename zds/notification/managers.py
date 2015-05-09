# -*- coding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType

from django.db import models


class NotificationManager(models.Manager):
    """
    Custom notification manager.
    """

    def get_unread_notifications_of(self, profile):
        return self.filter(subscription__profile=profile, is_read=False)

    def filter_content_type_of(self, model):
        content_subscription_type = ContentType.objects.get_for_model(model)
        return self.filter(subscription__content_type__pk=content_subscription_type.pk)
