# coding: utf-8

from datetime import datetime
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, get_object_or_404, render, render_to_response
from django.template import Context
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.forms.util import ErrorList
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic.detail import SingleObjectMixin

from zds.utils.mps import send_mp
from zds.utils.paginator import ZdSPagingListView
from zds.utils.templatetags.emarkdown import emarkdown

from .forms import PrivateTopicForm, PrivatePostForm
from .models import PrivateTopic, PrivatePost, \
    never_privateread, mark_read, PrivateTopicRead
from django.utils.translation import ugettext as _


class PrivateTopicList(ZdSPagingListView):
    """
    Displays the list of private topics of a member given.
    """

    context_object_name = 'privatetopics'
    paginate_by = settings.ZDS_APP['forum']['topics_per_page']
    template_name = 'mp/index.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(PrivateTopicList, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        return PrivateTopic.objects \
            .filter(Q(participants__in=[self.request.user.id]) | Q(author=self.request.user.id)) \
            .select_related("author", "participants") \
            .distinct().order_by('-last_message__pubdate').all()


@login_required
@require_POST
def leave_mps(request):
    """
    Deletes list of private topics.
    """

    list = request.POST.getlist('items')
    topics = PrivateTopic.objects.filter(pk__in=list) \
        .filter(Q(participants__in=[request.user]) | Q(author=request.user))

    for topic in topics:
        if topic.participants.all().count() == 0:
            topic.delete()
        elif request.user == topic.author:
            topic.author = topic.participants.all()[0]
            topic.participants.remove(topic.participants.all()[0])
            topic.save()
        else:
            topic.participants.remove(request.user)
            topic.save()

    return redirect(reverse('mp-list'))


class PrivatePostList(SingleObjectMixin, ZdSPagingListView):
    """
    Display a thread and its posts using a pager.
    """

    paginate_by = settings.ZDS_APP['forum']['posts_per_page']
    template_name = 'mp/topic/index.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(PrivatePostList, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(queryset=PrivateTopic.objects.all())
        if not self.object.author == request.user \
            and request.user not in list(self.object.participants.all()):
            raise PermissionDenied
        return super(PrivatePostList, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PrivatePostList, self).get_context_data(**kwargs)
        context['topic'] = self.object
        context['last_post_pk'] = self.object.last_message.pk
        context['form'] = PrivatePostForm(self.object)
        context['posts'] = self.build_list()
        if never_privateread(self.object):
            mark_read(self.object)
        return context

    def get_queryset(self):
        return PrivatePost.objects\
            .filter(privatetopic__pk=self.object.pk) \
            .order_by('position_in_topic') \
            .all()


@login_required
def new(request):
    """Creates a new private topic."""

    if request.method == 'POST':
        # If the client is using the "preview" button
        if 'preview' in request.POST:
            if request.is_ajax():
                content = render_to_response('misc/previsualization.part.html', {'text': request.POST['text']})
                return StreamingHttpResponse(content)
            else:
                form = PrivateTopicForm(request.user.username,
                                        initial={
                                            'participants': request.POST['participants'],
                                            'title': request.POST['title'],
                                            'subtitle': request.POST['subtitle'],
                                            'text': request.POST['text'],
                                        })
                return render(request, 'mp/topic/new.html', {
                    'form': form,
                })

        form = PrivateTopicForm(request.user.username, request.POST)

        if form.is_valid():
            data = form.data
            tried_unauthorized_member = False
            # Retrieve all participants of the MP.
            ctrl = []
            list_part = data['participants'].split(",")
            for part in list_part:
                part = part.strip()
                if part == '':
                    continue
                p = get_object_or_404(User, username=part)
                # We don't the author of the MP.
                if request.user == p:
                    continue
                if p.profile.is_private():
                    tried_unauthorized_member = True
                ctrl.append(p)

            # user add only himself
            if len(ctrl) < 1 and len(list_part) == 1 and list_part[0] == request.user.username:
                errors = form._errors.setdefault("participants", ErrorList())  # TODO: use mutators instead of _errors
                errors.append(_(u'Vous êtes déjà auteur du message'))
                if tried_unauthorized_member:
                    errors.append(_(u'Vous avez tenté d\'ajouter un utilisateur injoignable.'))
                return render(request, 'mp/topic/new.html', {
                    'form': form,
                })
            if tried_unauthorized_member:
                errors = form._errors.setdefault("participants", ErrorList())
                errors.append(_(u'Vous avez tenté d\'ajouter un utilisateur injoignable.'))
            else:
                p_topic = send_mp(request.user,
                                  ctrl,
                                  data['title'],
                                  data['subtitle'],
                                  data['text'],
                                  True,
                                  False)

                return redirect(p_topic.get_absolute_url())
            return render(request, 'mp/topic/new.html', {
                'form': form,
            })
        else:
            return render(request, 'mp/topic/new.html', {
                'form': form,
            })
    else:
        dest = None
        if 'username' in request.GET:
            dest_list = []
            # check that usernames in url is in the database
            for username in request.GET.getlist('username'):
                try:
                    dest_list.append(User.objects.get(username=username).username)
                except:
                    pass
            if len(dest_list) > 0:
                dest = ', '.join(dest_list)

        title = None
        if 'title' in request.GET:
            title = request.GET['title']

        form = PrivateTopicForm(username=request.user.username,
                                initial={
                                    'participants': dest,
                                    'title': title
                                })
        return render(request, 'mp/topic/new.html', {
            'form': form,
        })


@login_required
@require_POST
def edit(request):
    """Edit the given topic."""

    try:
        topic_pk = request.POST['privatetopic']
    except KeyError:
        raise Http404

    try:
        page = int(request.POST['page'])
    except KeyError:
        page = 1
    except ValueError:
        raise Http404

    g_topic = get_object_or_404(PrivateTopic, pk=topic_pk)

    if request.POST['username']:
        u = get_object_or_404(User, username=request.POST['username'])
        if not request.user == u and not u.profile.is_private():
            g_topic.participants.add(u)
            g_topic.save()

    return redirect(u'{}?page={}'.format(g_topic.get_absolute_url(), page))


@login_required
def answer(request):
    """Adds an answer from an user to a topic."""
    try:
        topic_pk = request.GET['sujet']
    except KeyError:
        raise Http404

    # Retrieve current topic.
    g_topic = get_object_or_404(PrivateTopic, pk=topic_pk)

    # check if user has right to answer
    if not g_topic.author == request.user \
            and request.user not in list(g_topic.participants.all()):
        raise PermissionDenied

    last_post_pk = g_topic.last_message.pk
    # Retrieve last posts of the current private topic.
    posts = PrivatePost.objects.filter(privatetopic=g_topic) \
        .prefetch_related() \
        .order_by("-pubdate")[:settings.ZDS_APP['forum']['posts_per_page']]

    # User would like preview his post or post a new post on the topic.
    if request.method == 'POST':
        data = request.POST

        if not request.is_ajax():
            print data['last_post']
            newpost = last_post_pk != int(data['last_post'])

        # Using the « preview button », the « more » button or new post
        if 'preview' in data or newpost:
            if request.is_ajax():
                content = render_to_response('misc/previsualization.part.html', {'text': data['text']})
                return StreamingHttpResponse(content)
            else:
                form = PrivatePostForm(g_topic, initial={
                    'text': data['text']
                })

                return render(request, 'mp/post/new.html', {
                    'topic': g_topic,
                    'last_post_pk': last_post_pk,
                    'posts': posts,
                    'newpost': newpost,
                    'form': form,
                })

        # Saving the message
        else:
            form = PrivatePostForm(g_topic, data)
            if form.is_valid():
                data = form.data

                post = PrivatePost()
                post.privatetopic = g_topic
                post.author = request.user
                post.text = data['text']
                post.text_html = emarkdown(data['text'])
                post.pubdate = datetime.now()
                post.position_in_topic = g_topic.get_post_count() + 1
                post.save()

                g_topic.last_message = post
                g_topic.save()

                # send email
                subject = u"{} - MP : {}".format(settings.ZDS_APP['site']['abbr'], g_topic.title)
                from_email = u"{} <{}>".format(settings.ZDS_APP['site']['litteral_name'],
                                               settings.ZDS_APP['site']['email_noreply'])
                parts = list(g_topic.participants.all())
                parts.append(g_topic.author)
                parts.remove(request.user)
                for part in parts:
                    profile = part.profile
                    if profile.email_for_answer:
                        pos = post.position_in_topic - 1
                        last_read = PrivateTopicRead.objects.filter(
                            privatetopic=g_topic,
                            privatepost__position_in_topic=pos,
                            user=part).count()
                        if last_read > 0:
                            message_html = get_template('email/mp/new.html') \
                                .render(
                                    Context({
                                        'username': part.username,
                                        'url': settings.ZDS_APP['site']['url'] + post.get_absolute_url(),
                                        'author': request.user.username
                                    }))
                            message_txt = get_template('email/mp/new.txt').render(
                                Context({
                                    'username': part.username,
                                    'url': settings.ZDS_APP['site']['url'] + post.get_absolute_url(),
                                    'author': request.user.username
                                }))

                            msg = EmailMultiAlternatives(
                                subject, message_txt, from_email, [
                                    part.email])
                            msg.attach_alternative(message_html, "text/html")
                            msg.send()

                return redirect(post.get_absolute_url())
            else:
                return render(request, 'mp/post/new.html', {
                    'topic': g_topic,
                    'last_post_pk': last_post_pk,
                    'newpost': newpost,
                    'posts': posts,
                    'form': form,
                })

    else:
        text = ''

        # Using the quote button
        if 'cite' in request.GET:
            resp = {}
            post_cite_pk = request.GET['cite']
            post_cite = get_object_or_404(PrivatePost, pk=post_cite_pk)

            for line in post_cite.text.splitlines():
                text = text + '> ' + line + '\n'

            text = u'{0}Source:[{1}]({2}{3})'.format(
                text,
                post_cite.author.username,
                settings.ZDS_APP['site']['url'],
                post_cite.get_absolute_url())

            if request.is_ajax():
                resp["text"] = text
                return HttpResponse(json.dumps(resp), content_type='application/json')

        form = PrivatePostForm(g_topic, initial={
            'text': text
        })
        return render(request, 'mp/post/new.html', {
            'topic': g_topic,
            'posts': posts,
            'last_post_pk': last_post_pk,
            'form': form
        })


@login_required
def edit_post(request):
    """Edit the given user's post."""
    try:
        post_pk = request.GET['message']
    except KeyError:
        raise Http404

    post = get_object_or_404(PrivatePost, pk=post_pk)

    # Only edit last private post
    tp = get_object_or_404(PrivateTopic, pk=post.privatetopic.pk)
    last = get_object_or_404(PrivatePost, pk=tp.last_message.pk)
    if not last.pk == post.pk:
        raise PermissionDenied

    g_topic = None
    if post.position_in_topic >= 1:
        g_topic = get_object_or_404(PrivateTopic, pk=post.privatetopic.pk)

    # Making sure the user is allowed to do that. Author of the post
    # must to be the user logged.
    if post.author != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        data = request.POST

        if 'text' not in data:
            # if preview mode return on
            if 'preview' in data:
                return redirect(
                    reverse('zds.mp.views.edit_post') +
                    '?message=' +
                    str(post_pk))
            # disallow send mp
            else:
                raise PermissionDenied

        # Using the preview button
        if 'preview' in data:
            if request.is_ajax():
                content = render_to_response('misc/previsualization.part.html', {'text': data['text']})
                return StreamingHttpResponse(content)
            else:
                form = PrivatePostForm(g_topic, initial={
                    'text': data['text']
                })
                form.helper.form_action = reverse(
                    'zds.mp.views.edit_post') + '?message=' + str(post_pk)

                return render(request, 'mp/post/edit.html', {
                    'post': post,
                    'topic': g_topic,
                    'form': form,
                })

        # The user just sent data, handle them
        post.text = data['text']
        post.text_html = emarkdown(data['text'])
        post.update = datetime.now()
        post.save()

        return redirect(post.get_absolute_url())

    else:
        form = PrivatePostForm(g_topic, initial={
            'text': post.text
        })
        form.helper.form_action = reverse(
            'zds.mp.views.edit_post') + '?message=' + str(post_pk)
        return render(request, 'mp/post/edit.html', {
            'post': post,
            'topic': g_topic,
            'text': post.text,
            'form': form,
        })


@login_required
@require_POST
@transaction.atomic
def leave(request):
    if 'leave' in request.POST:
        ptopic = get_object_or_404(PrivateTopic, pk=request.POST['topic_pk'])
        if ptopic.participants.count() == 0:
            ptopic.delete()
        elif request.user.pk == ptopic.author.pk:
            move = ptopic.participants.first()
            ptopic.author = move
            ptopic.participants.remove(move)
            ptopic.save()
        else:
            ptopic.participants.remove(request.user)
            ptopic.save()

        messages.success(
            request, _(u'Vous avez quitté la conversation avec succès.'))

    return redirect(reverse('mp-list'))


@login_required
@require_POST
@transaction.atomic
def add_participant(request):
    try:
        ptopic = get_object_or_404(PrivateTopic, pk=request.POST['topic_pk'])
    except KeyError:
        messages.warning(
            request, _(u'La conversation que vous avez essayé d\'utiliser n\'existe pas.'))

    # check if user is the author of topic
    if ptopic is not None and not ptopic.author == request.user:
        raise PermissionDenied

    try:
        # user_pk or user_username ?
        part = User.objects.get(username__exact=request.POST['user_pk'])
        if part.profile.is_private():
            raise ObjectDoesNotExist
        if part.pk == ptopic.author.pk or part in ptopic.participants.all():
            messages.warning(
                request,
                _(u'Le membre que vous essayez d\'ajouter '
                  u'à la conversation y est déjà.'))
        else:
            ptopic.participants.add(part)
            ptopic.save()

            messages.success(
                request,
                _(u'Le membre a bien été ajouté à la conversation.'))
    except (KeyError, ObjectDoesNotExist):
        messages.warning(
            request, _(u'Le membre que vous avez essayé d\'ajouter n\'existe pas ou ne peut être contacté.'))

    return redirect(reverse('posts-private-list', args=[ptopic.pk]))
