from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from zds.notification.models import Subscription
from zds.utils.paginator import ZdSPagingListView


class SubscriptionList(ZdSPagingListView):
    """
    Displays the list of subscriptions of a given member.
    """

    context_object_name = 'subscriptions'
    paginate_by = settings.ZDS_APP['notification']['subscriptions_per_page']
    template_name = 'notification/subscriptions/index.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(SubscriptionList, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user.profile, is_active=True)\
            .distinct().order_by('-last_notification__pubdate').all()


class NotificationList(ZdSPagingListView):
    """
    Displays the list of notification of a given member.
    """

    context_object_name = 'notifications'
    paginate_by = settings.ZDS_APP['notification']['notifications_per_page']
    template_name = 'notification/index.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(SubscriptionList, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user.profile)\
            .distinct().order_by('-pubdate').all()
