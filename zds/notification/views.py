from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from zds.notification.models import Subscription, Notification
from zds.utils.paginator import ZdSPagingListView


class NotificationList(ZdSPagingListView):
    """
    Displays the list of notification of a given member.
    """

    context_object_name = 'notifications'
    paginate_by = settings.ZDS_APP['notification']['notifications_per_page']
    template_name = 'notification/notification/list.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(NotificationList, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        notifications = []
        subscriptions = Subscription.objects.filter(profile=self.request.user.profile, is_active=True)\
            .distinct().order_by('-last_notification__pubdate').all()
        for subscription in subscriptions:
            if subscription.last_notification is not None:
                notifications.append(subscription.last_notification)
        return notifications
