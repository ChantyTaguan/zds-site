# coding: utf-8

from datetime import datetime, timedelta
import time

from django import template
from django.contrib.contenttypes.models import ContentType
from django.db.models import F

from zds.article.models import Reaction, ArticleRead
from zds.forum.models import never_read as never_read_topic, Post, TopicRead, Topic
from zds.mp.models import PrivateTopic
from zds.notification.models import Notification, Subscription, AnswerSubscription, UpdateTutorialSubscription
from zds.tutorial.models import Note, TutorialRead
from zds.utils import get_current_user
from zds.utils.models import Alert


register = template.Library()


@register.filter('is_read')
def is_read(topic):
    if never_read_topic(topic):
        return False
    else:
        return True


@register.filter('humane_delta')
def humane_delta(value):
    # mapping between label day and key
    const = {1: "Aujourd'hui", 2: "Hier", 3: "Cette semaine", 4: "Ce mois-ci", 5: "Cette année"}

    return const[value]


@register.filter('followed_topics')
def followed_topics(user):
    topics_followed = AnswerSubscription.objects.filter(profile=user.profile, content_type__model='topic', active=True)\
        .order_by('-last_notification__pubdate')[:10]
    # This period is a map for link a moment (Today, yesterday, this week, this month, etc.) with
    # the number of days for which we can say we're still in the period
    # for exemple, the tuple (2, 1) means for the period "2" corresponding to "Yesterday" according
    # to humane_delta, means if your pubdate hasn't exceeded one day, we are always at "Yesterday"
    # Number is use for index for sort map easily
    period = ((1, 0), (2, 1), (3, 7), (4, 30), (5, 360))
    topics = {}
    for tf in topics_followed:
        for p in period:
            if tf.content_object.last_message.pubdate.date() >= (datetime.now() - timedelta(days=int(p[1]),
                                                                                   hours=0, minutes=0,
                                                                                   seconds=0)).date():
                if p[0] in topics:
                    topics[p[0]].append(tf.content_object)
                else:
                    topics[p[0]] = [tf.content_object]
                break
    return topics


def comp(d1, d2):
    v1 = int(time.mktime(d1['pubdate'].timetuple()))
    v2 = int(time.mktime(d2['pubdate'].timetuple()))
    if v1 > v2:
        return -1
    elif v1 < v2:
        return 1
    else:
        return 0

@register.filter('notifications')
def notifications(user):
    unread_notifications = Notification.objects.filter(subscription__profile=user.profile, is_read=False)\
        .order_by('-pubdate')
    return unread_notifications

@register.filter('notif_title')
def notif_title(notification):
    return notification.title

@register.filter('notif_author_profile')
def notif_author_profile(notification):
    return notification.sender

@register.filter('notif_username')
def notif_username(notification):
    return notification.sender.user.username

@register.filter('notif_url')
def notif_url(notification):
    return notification.url

@register.filter('has_subscribed_new')
def has_subscribed_new(content_subscription):
    subscription = AnswerSubscription.get_existing(get_current_user().profile, content_subscription, active=True)
    return subscription is not None

@register.filter('has_suscribed_email_new')
def has_suscribed_email_new(content_subscription):
    subscription = AnswerSubscription(get_current_user().profile, content_subscription, active=True)
    if subscription is not None:
        return subscription.by_email
    else:
        return False

@register.filter('has_subscribed_update_tutorial')
def has_subscribed_update(content_subscription):
    subscription = UpdateTutorialSubscription.get_existing(get_current_user().profile, content_subscription, active=True)
    return subscription is not None

@register.filter('from_topic')
def from_topic(notification):
    return notification.subscription.content_type.model == 'topic'


@register.filter('interventions_privatetopics')
def interventions_privatetopics(user):

    # Raw query because ORM doesn't seems to allow this kind of "left outer join" clauses.
    # Parameters = list with 3x the same ID because SQLite backend doesn't allow map parameters.
    privatetopics_unread = PrivateTopic.objects.raw(
        '''
        select distinct t.*
        from mp_privatetopic t
        left outer join mp_privatetopic_participants p on p.privatetopic_id = t.id
        left outer join mp_privatetopicread r on r.user_id = %s and r.privatepost_id = t.last_message_id
        where (t.author_id = %s or p.user_id = %s)
          and r.id is null
        order by t.pubdate desc''',
        [user.id, user.id, user.id])

    # "total" re-do the query, but there is no other way to get the length as __len__ is not available on raw queries.
    topics = list(privatetopics_unread)
    return {'unread': topics, 'total': len(topics)}


@register.filter(name='alerts_list')
def alerts_list(user):
    total = []
    alerts = Alert.objects.select_related('author', 'comment').all().order_by('-pubdate')[:10]
    for alert in alerts:
        if alert.scope == Alert.FORUM:
            post = Post.objects.select_related('topic').get(pk=alert.comment.pk)
            total.append({'title': post.topic.title,
                          'url': post.get_absolute_url(),
                          'pubdate': alert.pubdate,
                          'author': alert.author,
                          'text': alert.text})
        if alert.scope == Alert.ARTICLE:
            reaction = Reaction.objects.select_related('article').get(pk=alert.comment.pk)
            total.append({'title': reaction.article.title,
                          'url': reaction.get_absolute_url(),
                          'pubdate': alert.pubdate,
                          'author': alert.author,
                          'text': alert.text})
        if alert.scope == Alert.TUTORIAL:
            note = Note.objects.select_related('tutorial').get(pk=alert.comment.pk)
            total.append({'title': note.tutorial.title,
                          'url': note.get_absolute_url(),
                          'pubdate': alert.pubdate,
                          'author': alert.author,
                          'text': alert.text})

    return total
