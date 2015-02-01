# coding: utf-8

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from zds.utils import slugify
from math import ceil
import os
import string
import uuid

from django.contrib.auth.models import Group, User
from datetime import datetime
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_text

from zds.forum.managers import TopicManager
from zds.utils import get_current_user
from zds.utils.models import Comment, Tag


def sub_tag(g):
    start = g.group('start')
    end = g.group('end')
    return u"{0}".format(start + end)


def image_path_forum(instance, filename):
    """
    Return path to an image.
    TODO: what is the usage of this function?
    :param instance:
    :param filename:
    :return:
    """
    ext = filename.split('.')[-1]
    filename = u'{}.{}'.format(str(uuid.uuid4()), string.lower(ext))
    return os.path.join('forum/normal', str(instance.pk), filename)


class Category(models.Model):
    """
    A Category is a simple container for Forums.
    There is no kind of logic in a Category. It simply here for Forum presentation in a predefined order.
    """
    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['position', 'title']

    title = models.CharField('Titre', max_length=80)
    position = models.IntegerField('Position', null=True, blank=True)
    # Some category slugs are forbidden due to path collisions: Category path is `/forums/<slug>` but some actions on
    # forums have path like `/forums/<action_name>`. Forbidden slugs are all top-level path in forum's `url.py` module.
    # As Categories can only be managed by superadmin, this is purely declarative and there is no control on slug.
    slug = models.SlugField(max_length=80,
                            unique=True,
                            help_text="Ces slugs vont provoquer des conflits "
                            "d'URL et sont donc interdits : notifications "
                            "resolution_alerte sujet sujets message messages")

    def __unicode__(self):
        """Textual form of a category."""
        return self.title

    def get_absolute_url(self):
        return reverse('zds.forum.views.cat_details',
                       kwargs={'cat_slug': self.slug})

    def get_forums(self):
        """
        :return: All forums in category, ordered by forum's position in category
        """
        return Forum.objects.all()\
            .filter(category=self)\
            .order_by('position_in_category')


class Forum(models.Model):
    """
    A Forum, containing Topics. It can be public or restricted to some groups.
    """
    class Meta:
        verbose_name = 'Forum'
        verbose_name_plural = 'Forums'
        ordering = ['position_in_category', 'title']

    title = models.CharField('Titre', max_length=80)
    subtitle = models.CharField('Sous-titre', max_length=200)

    # Groups authorized to read this forum. If no group is defined, the forum is public (and anyone can read it).
    group = models.ManyToManyField(
        Group,
        verbose_name='Groupe autorisés (Aucun = public)',
        null=True,
        blank=True)
    # TODO: A forum defines an image, but it doesn't seems to be used...
    image = models.ImageField(upload_to=image_path_forum)

    category = models.ForeignKey(Category, db_index=True, verbose_name='Catégorie')
    position_in_category = models.IntegerField('Position dans la catégorie',
                                               null=True, blank=True, db_index=True)

    slug = models.SlugField(max_length=80, unique=True)

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('zds.forum.views.details',
                       kwargs={'cat_slug': self.category.slug,
                               'forum_slug': self.slug})

    def get_topic_count(self):
        """
        :return: the number of threads in the forum.
        """
        return Topic.objects.all().filter(forum__pk=self.pk).count()

    def get_post_count(self):
        """
        :return: the number of posts for a forum.
        """
        return Post.objects.filter(topic__forum=self).count()

    # TODO: Rename this method for something clearer
    def get_last_message(self):
        """
        :return: the last message on the forum, if there are any.
        """
        try:
            return Post.objects.all().filter(topic__forum__pk=self.pk).order_by('-pubdate')[0]
        except IndexError:
            return None

    def can_read(self, user):
        """
        Checks if an user can read current forum.
        The forum can be read if:
        - The forum has no access restriction (= no group), or
        - The user is authenticated and he has access to groups defined for this forum.
        :param user: the user to check the rights
        :return: `True` if the user can read this forum, `False` otherwise.
        """

        if self.group.count() == 0:
            return True
        else:
            if user.is_authenticated():
                groups = Group.objects.filter(user=user).all()
                return Forum.objects.filter(
                    group__in=groups,
                    pk=self.pk).exists()
            else:
                return False


class Topic(models.Model):
    """
    A Topic is a thread of posts.
    A topic has several states, witch are all independent:
    - Solved: it was a question, and this question has been answered. The "solved" state is set at author's discretion.
    - Locked: none can write on a locked topic.
    - Sticky: sticky topics are displayed on top of topic lists (ex: on forum page).
    """

    class Meta:
        verbose_name = 'Sujet'
        verbose_name_plural = 'Sujets'

    title = models.CharField('Titre', max_length=80)
    subtitle = models.CharField('Sous-titre', max_length=200)

    forum = models.ForeignKey(Forum, verbose_name='Forum', db_index=True)
    author = models.ForeignKey(User, verbose_name='Auteur',
                               related_name='topics', db_index=True)
    last_message = models.ForeignKey('Post', null=True,
                                     related_name='last_message',
                                     verbose_name='Dernier message')
    pubdate = models.DateTimeField('Date de création', auto_now_add=True)

    is_solved = models.BooleanField('Est résolu', default=False, db_index=True)
    is_locked = models.BooleanField('Est verrouillé', default=False)
    is_sticky = models.BooleanField('Est en post-it', default=False, db_index=True)

    tags = models.ManyToManyField(
        Tag,
        verbose_name='Tags du forum',
        null=True,
        blank=True,
        db_index=True)

    # This attribute is the link between beta of tutorials and topic of these beta.
    # In Tuto logic we can found something like this: `Topic.objet.get(key=tutorial.pk)`
    # TODO: 1. Use a better name, 2. maybe there can be a cleaner way to do this
    key = models.IntegerField('cle', null=True, blank=True)

    objects = TopicManager()

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            'zds.forum.views.topic',
            args=[self.pk, slugify(self.title)]
        )

    def get_post_count(self):
        """
        :return: the number of posts in the topic.
        """
        return Post.objects.filter(topic__pk=self.pk).count()

    def get_last_post(self):
        """
        :return: the last post in the thread.
        """
        return self.last_message

    def get_last_answer(self):
        """
        Gets the last answer in this tread, if any.
        Note the first post is not considered as an answer, therefore a topic with a single post (the 1st one) will
        return `None`.
        :return: the last answer in the thread, if any.
        """
        last_post = self.get_last_post()

        if last_post == self.first_post():
            return None
        else:
            return last_post

    def first_post(self):
        """
        :return: the first post of a topic, written by topic's author.
        """
        # TODO: Force relation with author here is strange. Probably linked with the `get_last_answer` function that
        # should compare PK and not objects
        return Post.objects\
            .filter(topic=self)\
            .select_related("author")\
            .order_by('position')\
            .first()

    def add_tags(self, tag_collection):
        """
        Add all tags contained in `tag_collection` to this topic.
        If a tag is unknown, it is added to the system.
        :param tag_collection: A collection of tags.
        """
        for tag in tag_collection:
            tag_title = smart_text(tag.strip().lower())
            current_tag = Tag.objects.filter(title=tag_title).first()
            if current_tag is None:
                current_tag = Tag(title=tag_title)
                current_tag.save()

            self.tags.add(current_tag)
        self.save()

    def get_followers_by_email(self):
        """
        :return: the set of users that follows this topic by email.
        """
        return TopicFollowed.objects.filter(topic=self, email=True).select_related("user")

    def last_read_post(self):
        """
        Returns the last post the current user has read in this topic.
        If it has never read this topic, returns the first post.
        Used in "last read post" balloon (base.html line 91).
        :return: the last post the user has read.
        """
        try:
            return TopicRead.objects\
                .select_related()\
                .filter(topic=self, user=get_current_user())\
                .latest('post__position').post
        except:
            return self.first_post()

    def first_unread_post(self):
        """
        Returns the first post of this topics the current user has never read, or the first post if it has never read
        this topic.
        Used in notification menu.
        :return: The first unread post for this topic and this user.
        """
        # TODO: Why 2 nearly-identical functions? What is the functional need of these 2 things?
        try:
            last_post = TopicRead.objects\
                .filter(topic=self, user=get_current_user())\
                .latest('post__position').post

            next_post = Post.objects.filter(
                topic__pk=self.pk,
                position__gt=last_post.position)\
                .select_related("author").first()
            return next_post
        except:
            return self.first_post()

    def is_followed(self, user=None):
        """
        Checks if the user follows this topic.
        :param user: An user. If undefined, the current user is used.
        :return: `True` if the user follows this topic, `False` otherwise.
        """
        if user is None:
            user = get_current_user()

        return TopicFollowed.objects.filter(topic=self, user=user).exists()

    def is_email_followed(self, user=None):
        """
        Checks if the user follows this topic by email.
        :param user: An user. If undefined, the current user is used.
        :return: `True` if the user follows this topic by email, `False` otherwise.
        """
        if user is None:
            user = get_current_user()

        try:
            TopicFollowed.objects.get(topic=self, user=user, email=True)
        except TopicFollowed.DoesNotExist:
            return False
        return True

    def antispam(self, user=None):
        """
        Check if the user is allowed to post in a topic according to the `ZDS_APP['forum']['spam_limit_seconds']` value.
        The user can always post if someone else has posted last.
        If the user is the last poster and there is less than `ZDS_APP['forum']['spam_limit_seconds']` since the last
        post, the anti-spam is active and the user cannot post.
        :param user: An user. If undefined, the current user is used.
        :return: `True` if the anti-spam is active (user can't post), `False` otherwise.
        """
        if user is None:
            user = get_current_user()

        last_user_post = Post.objects\
            .filter(topic=self)\
            .filter(author=user.pk)\
            .order_by('position')\
            .last()

        if last_user_post and last_user_post == self.get_last_post():
            t = datetime.now() - last_user_post.pubdate
            if t.total_seconds() < settings.ZDS_APP['forum']['spam_limit_seconds']:
                return True

        return False

    def never_read(self):
        return never_read(self)


class Post(Comment):
    """
    A forum post written by an user.
    A post can be marked as useful: topic's author (or admin) can declare any topic as "useful", and this post is
    displayed as is on front.
    """

    topic = models.ForeignKey(Topic, verbose_name='Sujet', db_index=True)

    is_useful = models.BooleanField('Est utile', default=False)

    def __unicode__(self):
        return u'<Post pour "{0}", #{1}>'.format(self.topic, self.pk)

    def get_absolute_url(self):
        """
        :return: the absolute URL for this post, including page in the topic.
        """
        page = int(ceil(float(self.position) / settings.ZDS_APP['forum']['posts_per_page']))

        return '{0}?page={1}#p{2}'.format(
            self.topic.get_absolute_url(),
            page,
            self.pk)


class TopicRead(models.Model):
    """
    This model tracks the last post read in a topic by a user.
    Technically it is a simple joint [user, topic, last read post].
    """
    class Meta:
        verbose_name = 'Sujet lu'
        verbose_name_plural = 'Sujets lus'

    # TODO: ça a l'air d'être OK en base, mais ne devrait-il pas y avoir une contrainte unique sur (topic, user) ?
    topic = models.ForeignKey(Topic, db_index=True)
    post = models.ForeignKey(Post, db_index=True)
    user = models.ForeignKey(User, related_name='topics_read', db_index=True)

    def __unicode__(self):
        return u'<Sujet "{0}" lu par {1}, #{2}>'.format(self.topic,
                                                        self.user,
                                                        self.post.pk)


class TopicFollowed(models.Model):
    """
    This model tracks which user follows which topic.
    It serves only to manual topic following.
    This model also indicates if the topic is followed by email.
    """
    class Meta:
        verbose_name = 'Sujet suivi'
        verbose_name_plural = 'Sujets suivis'

    topic = models.ForeignKey(Topic, db_index=True)
    user = models.ForeignKey(User, related_name='topics_followed', db_index=True)
    email = models.BooleanField('Notification par courriel', default=False, db_index=True)

    def __unicode__(self):
        return u'<Sujet "{0}" suivi par {1}>'.format(self.topic.title,
                                                     self.user.username)


def never_read(topic, user=None):
    """
    Check if the user has read the **last post** of the topic.
    Note if the user has already read the topic but not the last post, it will consider it has never read the topic...
    Technically this is done by check if there is a `TopicRead` for the topic, its last post and the user.
    :param topic: A topic
    :param user: A user. If undefined, the current user is used.
    :return:
    """
    # TODO: cette méthode est très mal nommée en plus d'avoir un nom "booléen négatif" !
    if user is None:
        user = get_current_user()

    return not TopicRead.objects\
        .filter(post=topic.last_message, topic=topic, user=user).exists()


def mark_read(topic):
    """
    Mark the last message of a topic as read for the current user.
    :param topic: A topic.
    """
    u = get_current_user()
    # TODO: voilà entre autres pourquoi il devrait y avoir une contrainte unique sur (topic, user) sur TopicRead.
    t = TopicRead.objects.filter(topic=topic, user=u).first()
    if t is None:
        t = TopicRead(post=topic.last_message, topic=topic, user=u)
    else:
        t.post = topic.last_message
    t.save()


def follow(topic, user=None):
    """
    Toggle following of a topic for an user.
    :param topic: A topic.
    :param user: A user. If undefined, the current user is used.
    :return: `True` if the topic is now followed, `False` if is has been un-followed.
    """
    from zds.notification.models import Subscription

    content_type = ContentType.objects.get(model="topic")
    ret = None
    if user is None:
        user = get_current_user()
    try:
        existing = Subscription.objects.get(
            object_id=topic.pk, content_type=content_type, profile=user.profile
        )
    except Subscription.DoesNotExist:
        existing = None

    if not existing:
        # Make the user follow the topic
        t = Subscription(
            content_object=topic,
            profile=user.profile
        )
        t.save()
        ret = True
    else:
        # If user is already following the topic, we make him don't anymore
        existing.delete()
        ret = False
    return ret


def follow_by_email(topic, user=None):
    """
    Toggle following by email of a topic for an user.
    :param topic: A topic.
    :param user: A user. If undefined, the current user is used.
    :return: `True` if the topic is now followed, `False` if is has been un-followed.
    """
    ret = None
    if user is None:
        user = get_current_user()
    try:
        existing = TopicFollowed.objects.get(
            topic=topic,
            user=user
        )
    except TopicFollowed.DoesNotExist:
        existing = None

    if not existing:
        # Make the user follow the topic
        t = TopicFollowed(
            topic=topic,
            user=user,
            email=True
        )
        t.save()
        ret = True
    else:
        existing.email = not existing.email
        existing.save()
        ret = existing.email
    return ret


def get_last_topics(user):
    """Returns the 5 very last topics."""
    # TODO semble inutilisé (et peu efficace dans la manière de faire)
    topics = Topic.objects.all().order_by('-last_message__pubdate')

    tops = []
    cpt = 1
    for topic in topics:
        if topic.forum.can_read(user):
            tops.append(topic)
            cpt += 1
        if cpt > 5:
            break
    return tops


def get_topics(forum_pk, is_sticky, filter=None):
    """
    Get topics for a forum.
    The optional filter allows to retrieve only solved, unsolved or "non-answered" (i.e. with only the 1st post) topics.
    :param forum_pk: the primary key of forum
    :param is_sticky: indicates if the sticky topics must or must not be retrieved
    :param filter: optional filter to retrieve only specific topics.
    :return:
    """

    if filter == 'solve':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, is_solved=True)
    elif filter == 'unsolve':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, is_solved=False)
    elif filter == 'noanswer':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, last_message__position=1)
    else:
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky)

    return topics.order_by('-last_message__pubdate')\
        .select_related('author__profile')\
        .prefetch_related('last_message', 'tags')\
        .all()
