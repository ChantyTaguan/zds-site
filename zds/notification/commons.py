# -*- coding: utf-8 -*-


class NotificationFollowMixin(object):
    @staticmethod
    def perform_follow(active, subscription_model, content, user):
        if active:
            subscription_model.objects.get_or_create_active(user.profile, content)
            return -1
        subscription = subscription_model.objects.get_existing(user.profile, content)
        if subscription is not None:
            subscription.deactivate()
        return 1

    @staticmethod
    def perform_follow_by_email(active, subscription_model, content, user):
        subscription = subscription_model.objects.get_existing(user.profile, content)
        if active:
            if subscription is not None:
                subscription.activate_email()
            else:
                subscription = subscription_model(profile=user.profile, content_object=content, by_email=True)
                subscription.save()
            return -1
        if subscription is not None:
            subscription.deactivate_email()
        return 1
