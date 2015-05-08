# -*- coding: utf-8 -*-

from django.db import models


class NotificationManager(models.Manager):
    """
    Custom notification manager.
    """

    def get_unread_notifications_of(self, profile):
        return self.filter(subscription__profile=profile, is_read=False)
