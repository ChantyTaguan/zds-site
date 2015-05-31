# -*- coding: utf-8 -*-
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView
from django.views.generic.detail import SingleObjectMixin
from zds.forum.models import Topic
from zds.member.decorator import can_write_and_read_now
from zds.notification.commons import NotificationFollowMixin
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


class NotificationFollowEdit(UpdateView, SingleObjectMixin, NotificationFollowMixin):

    object = None
    subscription = None
    type = None
    param = None

    @method_decorator(require_POST)
    @method_decorator(login_required)
    @method_decorator(can_write_and_read_now)
    def dispatch(self, request, *args, **kwargs):
        assert self.subscription is not None
        assert self.type is not None
        assert self.param is not None

        self.object = self.get_object()
        if hasattr(self.object, 'can_read') and not self.object.can_read(request.user):
            raise PermissionDenied

        return super(NotificationFollowEdit, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = {}
        if 'follow' in request.POST:
            response['follow'] = self.perform_follow(request.POST.get('follow') == '1',
                                                     self.subscription, self.object, request.user)

        if request.is_ajax():
            return HttpResponse(json.dumps(response), content_type='application/json')
        return redirect(self.object.get_absolute_url())

    def get_object(self, queryset=None):
        try:
            identifier = int(self.request.POST.get(self.param))
        except (KeyError, ValueError, TypeError):
            raise Http404
        return get_object_or_404(self.type, pk=identifier)
