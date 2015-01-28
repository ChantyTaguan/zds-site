# coding: utf-8

from django.contrib import admin

from .models import Notification, Subscription


admin.site.register(Notification)
admin.site.register(Subscription)
