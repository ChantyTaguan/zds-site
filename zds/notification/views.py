# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from zds.forum.models import Topic
from zds.notification.models import Notification
from zds.utils.mixins import SortMixin, FilterMixin
from zds.utils.paginator import ZdSPagingListView


class NotificationListView(SortMixin, FilterMixin, ZdSPagingListView):
    """
    Displays the list of notification of a given member.
    """

    context_object_name = 'notifications'
    paginate_by = settings.ZDS_APP['notification']['notifications_per_page']
    template_name = 'notification/notification/list.html'
    default_sort_params = ('creation', 'asc')
    default_filter_param = 'all'
    filters = {'topic': Topic}

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(NotificationListView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        self.queryset = Notification.objects.get_unread_notifications_of(self.request.user.profile)
        return super(NotificationListView, self).get_queryset()

    def sort_queryset(self, queryset, sort_by, order):
        if sort_by == 'creation':
            queryset = queryset.order_by('pubdate')
        if order == 'desc':
            queryset = queryset.reverse()
        return queryset

    def filter_queryset(self, queryset, filter_param):
        if filter_param == self.default_filter_param or filter_param in self.filters.keys():
            return queryset
        queryset = queryset.filter_content_type_of(self.filters[filter_param])
        return queryset
