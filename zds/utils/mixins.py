# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured


class SortMixin(object):
    """
    View mixin which provides sorting for ListView.
    """
    sort_url_kwargs = 'sort'
    order_url_kwargs = 'order'
    default_sort_params = None

    def sort_queryset(self, queryset, sort_by, order):
        return queryset

    def get_default_sort_params(self):
        if self.default_sort_params is None:
            raise ImproperlyConfigured(
                "'SortMixin' requires the 'default_sort_params' attribute "
                "to be set.")
        return self.default_sort_params

    def get_sort_params(self):
        default_sort_by, default_order = self.get_default_sort_params()
        sort_by = self.request.GET.get(self.sort_url_kwargs, default_sort_by)
        order = self.request.GET.get(self.order_url_kwargs, default_order)
        return (sort_by, order)

    def get_queryset(self):
        return self.sort_queryset(super(SortMixin, self).get_queryset(), *self.get_sort_params())

    def get_context_data(self, *args, **kwargs):
        context = super(SortMixin, self).get_context_data(*args, **kwargs)
        sort_by, order = self.get_sort_params()
        context.update({
            self.sort_url_kwargs: sort_by,
            self.order_url_kwargs: order,
        })
        return context


class FilterMixin(object):
    """
    View mixin which provides filtering for ListView.
    """
    filter_url_kwarg = 'type'
    default_filter_param = None

    def filter_queryset(self, queryset, filter_param):
        """
        Filter the queryset `queryset`, given the selected `filter_param`. Default
        implementation does no filtering at all.
        """
        return queryset

    def get_default_filter_param(self):
        if self.default_filter_param is None:
            raise ImproperlyConfigured(
                "'FilterMixin' requires the 'default_filter_param' attribute "
                "to be set.")
        return self.default_filter_param

    def get_filter_param(self):
        return self.request.GET.get(self.filter_url_kwarg, self.get_default_filter_param())

    def get_queryset(self):
        return self.filter_queryset(super(FilterMixin, self).get_queryset(), self.get_filter_param())

    def get_context_data(self, *args, **kwargs):
        context = super(FilterMixin, self).get_context_data(*args, **kwargs)
        context.update({
            self.filter_url_kwarg: self.get_filter_param(),
        })
        return context