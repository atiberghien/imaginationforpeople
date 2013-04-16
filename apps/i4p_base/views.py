#-- encoding: utf-8 --
#
# This file is part of I4P.
#
# I4P is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# I4P is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
# 
# You should have received a copy of the GNU Affero Public License
# along with I4P.  If not, see <http://www.gnu.org/licenses/>.
#
# -*- coding: utf-8 -*-
from datetime import datetime
from functools import update_wrapper
import random
from urlparse import urlsplit

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils import translation
from django.utils.decorators import classonlymethod, method_decorator
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.base import RedirectView

from haystack.query import SearchQuerySet
from haystack.views import FacetedSearchView as HaystackFacetedSearchView

from apps.project_sheet.models import I4pProject
from apps.project_sheet.utils import get_project_translations_from_parents

from .models import VersionActivity
from .forms import ProjectSearchForm

def homepage(request):
    """
    I4P Homepage
    """
    project_sheets = I4pProject.on_site.filter(best_of=True).order_by('?')[:14]
    project_translations = get_project_translations_from_parents(project_sheets,
                                                                 language_code=translation.get_language()
                                                                 )

    latest_members = list(User.objects.filter(is_active=True).order_by('-date_joined')[:7])
    random.shuffle(latest_members)

    
    data = request.GET

    context = {'project_sheets': project_sheets,
               'project_translations': project_translations,
               'last_members': latest_members,
               'about_tab_selected' : True}

    return render_to_response(template_name='pages/homepage.html',
                              dictionary=context,
                              context_instance=RequestContext(request)
                              )


class VersionActivityCheckView(RedirectView):
    """
    Approves a Version Activity (an admin reviewed it).
    """
    permanent = False

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super(VersionActivityCheckView, self).dispatch(*args, **kwargs)
        
    def get_redirect_url(self, pk):
        activity_revision = get_object_or_404(VersionActivity, pk=pk)

        activity_revision.checked_by = self.request.user
        activity_revision.checked_on = datetime.now()
        activity_revision.save()
        
        referer = self.request.META.get('HTTP_REFERER', None)
        if referer:
            try:
                redirect_to = urlsplit(referer, 'http', False)[2]
            except IndexError:
                pass
                
            return redirect_to
        
class FacetedSearchView(TemplateResponseMixin, HaystackFacetedSearchView):
    template_name = None
    facets = None
    filter_models = None
    order_by = None
    paginate_by = getattr(settings, 'HAYSTACK_SEARCH_RESULTS_PER_PAGE', 20)
    form_class = ProjectSearchForm

    def __init__(self, *args, **kwargs):
        form_class = kwargs.get('form_class', self.form_class)
        super(FacetedSearchView, self).__init__(*args, **kwargs)
        # Needed to switch out the default form class.
        self.form_class = form_class
        if not self.results_per_page and self.paginate_by:
            self.results_per_page = self.paginate_by

    def get_context_data(self):
        return {}

    def extra_context(self):
        ctx = super(FacetedSearchView, self).extra_context()
        ctx.update(self.get_context_data())
        return ctx

    def get_facets(self):
        if not self.facets:
            return []
        return self.facets

    def get_filter_model(self, models=None):
        if models:
            return (models + self.filter_models)
        return self.filter_models

    def get_order_by_fields(self):
        return self.order_by

    def get_extra_filters(self):
        return {}

    def get_search_queryset(self, queryset=None, models=None):
        searchqueryset = queryset or self.searchqueryset or SearchQuerySet()
        searchqueryset = searchqueryset.filter(
            **self.get_extra_filters()
        )
        for facet_field in self.get_facets():
            searchqueryset = searchqueryset.facet(facet_field)
        # check we should filter by model
        filter_models = self.get_filter_model(models)
        if filter_models:
            searchqueryset = searchqueryset.models(*filter_models)
        # check for defined order by list
        if self.get_order_by_fields():
            searchqueryset = searchqueryset.order_by(
                *self.get_order_by_fields()
            )
        return searchqueryset

    @property
    def template(self):
        """ Provide property to be backwards compatible with haystack. """
        template_names = self.get_template_names()
        if template_names:
            return template_names[0]
        return None

    def get(self, request, *args, **kwargs):
        self.searchqueryset = self.get_search_queryset()
        return super(FacetedSearchView, self).__call__(request)

    def __call__(self, request, *args, **kwargs):
        self.request = request
        self.kwargs = kwargs
        return self.get(request, *args, **kwargs)

    @classonlymethod
    def as_view(cls, *initargs, **initkwargs):
        def view(request, *args, **kwargs):
            return cls(*initargs, **initkwargs)(request, *args, **kwargs)
        update_wrapper(view, cls, updated=())
        return view
        
class SearchView(FacetedSearchView):
    """
    Search projects, members, etc ; using haystack
    """
    template_name = 'i4p_base/search/search.html'
    filter_models = [I4pProject]
    
    def get(self, request, *args, **kwargs):
        self.filter_data = request.GET.copy()

        return super(SearchView, self).get(request, *args, **kwargs)

    def get_search_queryset(self, queryset=None, models=None):
        project_sheets_queryset = super(SearchView, self).get_search_queryset(queryset, models)
        
        language_code = translation.get_language()
        
        return project_sheets_queryset
    
    def get_context_data(self, **kwargs):
        context = super(SearchView, self).get_context_data(**kwargs)

        context["getparams"] = self.filter_data.urlencode()
        context["orderparams"] = context["getparams"].replace("order=creation", "") \
                                                     .replace("order=modification", "")

        # context["selected_tags"] = [int(t.id) for t in self.filter_forms_dict["themes_filter"].cleaned_data["themes"]]
        # context.update(self.filter_forms_dict)
        # context["filters_tab_selected"] = True

        context['project_translation_list'] = self.searchqueryset

        return context
