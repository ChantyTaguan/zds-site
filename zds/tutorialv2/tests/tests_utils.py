# coding: utf-8

import os
import shutil
import tempfile
import datetime

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from zds.forum.models import Topic
from zds.settings import BASE_DIR

from zds.member.factories import ProfileFactory, StaffProfileFactory
from zds.tutorialv2.factories import PublishableContentFactory, ContainerFactory, LicenceFactory, ExtractFactory, \
    PublishedContentFactory
from zds.gallery.factories import UserGalleryFactory
from zds.tutorialv2.models.models_versioned import Container
from zds.tutorialv2.utils import get_target_tagged_tree_for_container, publish_content, unpublish_content, \
    get_target_tagged_tree_for_extract, retrieve_and_update_images_links, last_participation_is_old, \
    InvalidSlugError, BadManifestError, get_content_from_json
from zds.tutorialv2.models.models_database import PublishableContent, PublishedContent, ContentReaction, ContentRead
from django.core.management import call_command
from zds.tutorial.factories import BigTutorialFactory, MiniTutorialFactory, PublishedMiniTutorial, NoteFactory, \
    BetaMiniTutorialFactory, PublishedBigTutorial
from zds.article.factories import ArticleFactory, PublishedArticleFactory, ReactionFactory
from zds.utils.models import CommentLike
from zds.article.models import ArticleRead
from zds.tutorial.models import TutorialRead, Chapter
from zds.tutorial.models import Validation as OldTutoValidation
from zds.article.models import Validation as OldArticleValidation
from zds.tutorialv2.models.models_database import Validation
from zds.forum.factories import ForumFactory, CategoryFactory

try:
    import ujson as json_reader
except ImportError:
    try:
        import simplejson as json_reader
    except:
        import json as json_reader

overrided_zds_app = settings.ZDS_APP
overrided_zds_app['content']['repo_private_path'] = os.path.join(BASE_DIR, 'contents-private-test')
overrided_zds_app['content']['repo_public_path'] = os.path.join(BASE_DIR, 'contents-public-test')
overrided_zds_app['tutorial']['repo_path'] = os.path.join(BASE_DIR, 'tutoriels-private-test')
overrided_zds_app['tutorial']['repo_public_path'] = os.path.join(BASE_DIR, 'tutoriels-public-test')
overrided_zds_app['article']['repo_path'] = os.path.join(BASE_DIR, 'article-data-test')


@override_settings(MEDIA_ROOT=os.path.join(BASE_DIR, 'media-test'))
@override_settings(ZDS_APP=overrided_zds_app)
class UtilsTests(TestCase):

    def setUp(self):

        # don't build PDF to speed up the tests
        settings.ZDS_APP['content']['build_pdf_when_published'] = False

        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
        self.mas = ProfileFactory().user
        settings.ZDS_APP['member']['bot_account'] = self.mas.username

        self.licence = LicenceFactory()

        self.user_author = ProfileFactory().user
        self.staff = StaffProfileFactory().user

        self.tuto = PublishableContentFactory(type='TUTORIAL')
        self.tuto.authors.add(self.user_author)
        UserGalleryFactory(gallery=self.tuto.gallery, user=self.user_author, mode='W')
        self.tuto.licence = self.licence
        self.tuto.save()

        self.tuto_draft = self.tuto.load_version()
        self.part1 = ContainerFactory(parent=self.tuto_draft, db_object=self.tuto)
        self.chapter1 = ContainerFactory(parent=self.part1, db_object=self.tuto)

    def test_get_target_tagged_tree_for_container(self):
        part2 = ContainerFactory(parent=self.tuto_draft, db_object=self.tuto, title="part2")
        part3 = ContainerFactory(parent=self.tuto_draft, db_object=self.tuto, title="part3")
        tagged_tree = get_target_tagged_tree_for_container(self.part1, self.tuto_draft)

        self.assertEqual(4, len(tagged_tree))
        paths = {i[0]: i[3] for i in tagged_tree}
        self.assertTrue(part2.get_path(True) in paths)
        self.assertTrue(part3.get_path(True) in paths)
        self.assertTrue(self.chapter1.get_path(True) in paths)
        self.assertTrue(self.part1.get_path(True) in paths)
        self.assertFalse(self.tuto_draft.get_path(True) in paths)
        self.assertFalse(paths[self.chapter1.get_path(True)], "can't be moved to a too deep container")
        self.assertFalse(paths[self.part1.get_path(True)], "can't be moved after or before himself")
        self.assertTrue(paths[part2.get_path(True)], "can be moved after or before part2")
        self.assertTrue(paths[part3.get_path(True)], "can be moved after or before part3")
        tagged_tree = get_target_tagged_tree_for_container(part3, self.tuto_draft)
        self.assertEqual(4, len(tagged_tree))
        paths = {i[0]: i[3] for i in tagged_tree}
        self.assertTrue(part2.get_path(True) in paths)
        self.assertTrue(part3.get_path(True) in paths)
        self.assertTrue(self.chapter1.get_path(True) in paths)
        self.assertTrue(self.part1.get_path(True) in paths)
        self.assertFalse(self.tuto_draft.get_path(True) in paths)
        self.assertTrue(paths[self.chapter1.get_path(True)], "can't be moved to a too deep container")
        self.assertTrue(paths[self.part1.get_path(True)], "can't be moved after or before himself")
        self.assertTrue(paths[part2.get_path(True)], "can be moved after or before part2")
        self.assertFalse(paths[part3.get_path(True)], "can be moved after or before part3")

    def test_publish_content(self):
        """test and ensure the behavior of ``publish_content()`` and ``unpublish_content()``"""

        # 1. Article:
        article = PublishableContentFactory(type='ARTICLE')

        article.authors.add(self.user_author)
        UserGalleryFactory(gallery=article.gallery, user=self.user_author, mode='W')
        article.licence = self.licence
        article.save()

        # populate the article
        article_draft = article.load_version()
        ExtractFactory(container=article_draft, db_object=article)
        ExtractFactory(container=article_draft, db_object=article)

        self.assertEqual(len(article_draft.children), 2)

        # publish !
        article = PublishableContent.objects.get(pk=article.pk)
        published = publish_content(article, article_draft)

        self.assertEqual(published.content, article)
        self.assertEqual(published.content_pk, article.pk)
        self.assertEqual(published.content_type, article.type)
        self.assertEqual(published.content_public_slug, article_draft.slug)
        self.assertEqual(published.sha_public, article.sha_draft)

        public = article.load_version(sha=published.sha_public, public=published)
        self.assertIsNotNone(public)
        self.assertTrue(public.PUBLIC)  # its a PublicContent object !
        self.assertEqual(public.type, published.content_type)
        self.assertEqual(public.current_version, published.sha_public)

        # test object created in database
        self.assertEqual(PublishedContent.objects.filter(content=article).count(), 1)
        published = PublishedContent.objects.filter(content=article).last()

        self.assertEqual(published.content_pk, article.pk)
        self.assertEqual(published.content_public_slug, article_draft.slug)
        self.assertEqual(published.content_type, article.type)
        self.assertEqual(published.sha_public, public.current_version)

        # test creation of files:
        self.assertTrue(os.path.isdir(published.get_prod_path()))
        self.assertTrue(os.path.isfile(os.path.join(published.get_prod_path(), 'manifest.json')))
        self.assertTrue(os.path.isfile(public.get_prod_path()))  # normally, an HTML file should exists
        self.assertIsNone(public.introduction)  # since all is in the HTML file, introduction does not exists anymore
        self.assertIsNone(public.conclusion)
        article.public_version = published
        article.save()
        # depublish it !
        unpublish_content(article)
        self.assertEqual(PublishedContent.objects.filter(content=article).count(), 0)  # published object disappear
        self.assertFalse(os.path.exists(public.get_prod_path()))  # article was removed
        # ... For the next tests, I will assume that the unpublication works.

        # 2. Mini-tutorial → Not tested, because at this point, it's the same as an article (with a different metadata)
        # 3. Medium-size tutorial
        midsize_tuto = PublishableContentFactory(type='TUTORIAL')

        midsize_tuto.authors.add(self.user_author)
        UserGalleryFactory(gallery=midsize_tuto.gallery, user=self.user_author, mode='W')
        midsize_tuto.licence = self.licence
        midsize_tuto.save()

        # populate with 2 chapters (1 extract each)
        midsize_tuto_draft = midsize_tuto.load_version()
        chapter1 = ContainerFactory(parent=midsize_tuto_draft, db_objet=midsize_tuto)
        ExtractFactory(container=chapter1, db_object=midsize_tuto)
        chapter2 = ContainerFactory(parent=midsize_tuto_draft, db_objet=midsize_tuto)
        ExtractFactory(container=chapter2, db_object=midsize_tuto)

        # publish it
        midsize_tuto = PublishableContent.objects.get(pk=midsize_tuto.pk)
        published = publish_content(midsize_tuto, midsize_tuto_draft)

        self.assertEqual(published.content, midsize_tuto)
        self.assertEqual(published.content_pk, midsize_tuto.pk)
        self.assertEqual(published.content_type, midsize_tuto.type)
        self.assertEqual(published.content_public_slug, midsize_tuto_draft.slug)
        self.assertEqual(published.sha_public, midsize_tuto.sha_draft)

        public = midsize_tuto.load_version(sha=published.sha_public, public=published)
        self.assertIsNotNone(public)
        self.assertTrue(public.PUBLIC)  # its a PublicContent object
        self.assertEqual(public.type, published.content_type)
        self.assertEqual(public.current_version, published.sha_public)

        # test creation of files:
        self.assertTrue(os.path.isdir(published.get_prod_path()))
        self.assertTrue(os.path.isfile(os.path.join(published.get_prod_path(), 'manifest.json')))

        self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), public.introduction)))
        self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), public.conclusion)))

        self.assertEqual(len(public.children), 2)
        for child in public.children:
            self.assertTrue(os.path.isfile(child.get_prod_path()))  # an HTML file for each chapter
            self.assertIsNone(child.introduction)
            self.assertIsNone(child.conclusion)

        # 4. Big tutorial:
        bigtuto = PublishableContentFactory(type='TUTORIAL')

        bigtuto.authors.add(self.user_author)
        UserGalleryFactory(gallery=bigtuto.gallery, user=self.user_author, mode='W')
        bigtuto.licence = self.licence
        bigtuto.save()

        # populate with 2 part (1 chapter with 1 extract each)
        bigtuto_draft = bigtuto.load_version()
        part1 = ContainerFactory(parent=bigtuto_draft, db_objet=bigtuto)
        chapter1 = ContainerFactory(parent=part1, db_objet=bigtuto)
        ExtractFactory(container=chapter1, db_object=bigtuto)
        part2 = ContainerFactory(parent=bigtuto_draft, db_objet=bigtuto)
        chapter2 = ContainerFactory(parent=part2, db_objet=bigtuto)
        ExtractFactory(container=chapter2, db_object=bigtuto)

        # publish it
        bigtuto = PublishableContent.objects.get(pk=bigtuto.pk)
        published = publish_content(bigtuto, bigtuto_draft)

        self.assertEqual(published.content, bigtuto)
        self.assertEqual(published.content_pk, bigtuto.pk)
        self.assertEqual(published.content_type, bigtuto.type)
        self.assertEqual(published.content_public_slug, bigtuto_draft.slug)
        self.assertEqual(published.sha_public, bigtuto.sha_draft)

        public = bigtuto.load_version(sha=published.sha_public, public=published)
        self.assertIsNotNone(public)
        self.assertTrue(public.PUBLIC)  # its a PublicContent object
        self.assertEqual(public.type, published.content_type)
        self.assertEqual(public.current_version, published.sha_public)

        # test creation of files:
        self.assertTrue(os.path.isdir(published.get_prod_path()))
        self.assertTrue(os.path.isfile(os.path.join(published.get_prod_path(), 'manifest.json')))

        self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), public.introduction)))
        self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), public.conclusion)))

        self.assertEqual(len(public.children), 2)
        for part in public.children:
            self.assertTrue(os.path.isdir(part.get_prod_path()))  # a directory for each part
            # ... and an HTML file for introduction and conclusion
            self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), part.introduction)))
            self.assertTrue(os.path.isfile(os.path.join(public.get_prod_path(), part.conclusion)))

            self.assertEqual(len(part.children), 1)

            for chapter in part.children:
                # the HTML file is located in the good directory:
                self.assertEqual(part.get_prod_path(), os.path.dirname(chapter.get_prod_path()))
                self.assertTrue(os.path.isfile(chapter.get_prod_path()))  # an HTML file for each chapter
                self.assertIsNone(chapter.introduction)
                self.assertIsNone(chapter.conclusion)

    def test_tagged_tree_extract(self):
        midsize = PublishableContentFactory(author_list=[self.user_author])
        midsize_draft = midsize.load_version()
        first_container = ContainerFactory(parent=midsize_draft, db_object=midsize)
        second_container = ContainerFactory(parent=midsize_draft, db_object=midsize)
        first_extract = ExtractFactory(container=first_container, db_object=midsize)
        second_extract = ExtractFactory(container=second_container, db_object=midsize)
        tagged_tree = get_target_tagged_tree_for_extract(first_extract, midsize_draft)
        paths = {i[0]: i[3] for i in tagged_tree}
        self.assertTrue(paths[second_extract.get_full_slug()])
        self.assertFalse(paths[second_container.get_path(True)])
        self.assertFalse(paths[first_container.get_path(True)])

    def test_update_manifest(self):
        opts = {}
        shutil.copy(
            os.path.join(BASE_DIR, "fixtures", "tuto", "balise_audio", "manifest.json"),
            os.path.join(BASE_DIR, "fixtures", "tuto", "balise_audio", "manifest2.json")
        )
        LicenceFactory(code="CC BY")
        args = [os.path.join(BASE_DIR, "fixtures", "tuto", "balise_audio", "manifest2.json")]
        call_command('upgrade_manifest_to_v2', *args, **opts)
        manifest = open(os.path.join(BASE_DIR, "fixtures", "tuto", "balise_audio", "manifest2.json"), 'r')
        json = json_reader.loads(manifest.read())

        self.assertTrue(u"version" in json)
        self.assertTrue(u"licence" in json)
        self.assertTrue(u"children" in json)
        self.assertEqual(len(json[u"children"]), 3)
        self.assertEqual(json[u"children"][0][u"object"], u"extract")
        os.unlink(args[0])
        args = [os.path.join(BASE_DIR, "fixtures", "tuto", "big_tuto_v1", "manifest2.json")]
        shutil.copy(
            os.path.join(BASE_DIR, "fixtures", "tuto", "big_tuto_v1", "manifest.json"),
            os.path.join(BASE_DIR, "fixtures", "tuto", "big_tuto_v1", "manifest2.json")
        )
        call_command('upgrade_manifest_to_v2', *args, **opts)
        manifest = open(os.path.join(BASE_DIR, "fixtures", "tuto", "big_tuto_v1", "manifest2.json"), 'r')
        json = json_reader.loads(manifest.read())
        os.unlink(args[0])
        self.assertTrue(u"version" in json)
        self.assertTrue(u"licence" in json)
        self.assertTrue(u"children" in json)
        self.assertEqual(len(json[u"children"]), 5)
        self.assertEqual(json[u"children"][0][u"object"], u"container")
        self.assertEqual(len(json[u"children"][0][u"children"]), 3)
        self.assertEqual(len(json[u"children"][0][u"children"][0][u"children"]), 3)
        args = [os.path.join(BASE_DIR, "fixtures", "tuto", "article_v1", "manifest2.json")]
        shutil.copy(
            os.path.join(BASE_DIR, "fixtures", "tuto", "article_v1", "manifest.json"),
            os.path.join(BASE_DIR, "fixtures", "tuto", "article_v1", "manifest2.json")
        )
        call_command('upgrade_manifest_to_v2', *args, **opts)
        manifest = open(os.path.join(BASE_DIR, "fixtures", "tuto", "article_v1", "manifest2.json"), 'r')
        json = json_reader.loads(manifest.read())

        self.assertTrue(u"version" in json)
        self.assertTrue(u"licence" in json)
        self.assertTrue(u"children" in json)
        self.assertEqual(len(json[u"children"]), 1)
        os.unlink(args[0])

    def test_retrieve_images(self):
        """test the ``retrieve_and_update_images_links()`` function.

        NOTE: this test require an working internet connection to succeed
        Also, it was implemented with small images on highly responsive server(s), to make it quick !
        """

        tempdir = os.path.join(tempfile.gettempdir(), 'test_retrieve_imgs')
        os.makedirs(tempdir)

        # image which exists, or not
        test_images = [
            # PNG:
            ('http://upload.wikimedia.org/wikipedia/en/9/9d/Commons-logo-31px.png', 'Commons-logo-31px.png'),
            # JPEG:
            ('http://upload.wikimedia.org/wikipedia/commons/6/6b/01Aso.jpg', '01Aso.jpg'),
            # Image which does not exists:
            ('http://test.com/test idiot.png', 'test_idiot.png'),  # NOTE: space changed into `_` !
            # SVG (will be converted to png):
            ('http://upload.wikimedia.org/wikipedia/commons/f/f9/10DF.svg', '10DF.png'),
            # GIF (will be converted to png):
            ('http://upload.wikimedia.org/wikipedia/commons/2/27/AnimatedStar.gif', 'AnimatedStar.png'),
            # local image:
            ('fixtures/image_test.jpg', 'image_test.jpg')
        ]

        # for each of these images, test that the url (and only that) is changed
        for url, filename in test_images:
            random_thing = str(datetime.datetime.now())  # will be used as legend, to ensure that this part remains
            an_image_link = '![{}]({})'.format(random_thing, url)
            new_image_url = 'images/{}'.format(filename)
            new_image_link = '![{}]({})'.format(random_thing, new_image_url)

            new_md = retrieve_and_update_images_links(an_image_link, tempdir)
            self.assertTrue(os.path.isfile(os.path.join(tempdir, new_image_url)))  # image was retrieved
            self.assertEqual(new_image_link, new_md)  # link was updated

        # then, ensure that 3 times the same images link make the code use three times the same image !
        link = '![{}](http://upload.wikimedia.org/wikipedia/commons/5/56/Asteroid_icon.jpg)'
        new_link = '![{}](images/Asteroid_icon.jpg)'
        three_times = ' '.join([link.format(i) for i in range(0, 2)])
        three_times_updated = ' '.join([new_link.format(i) for i in range(0, 2)])

        new_md = retrieve_and_update_images_links(three_times, tempdir)
        self.assertEqual(three_times_updated, new_md)

        # ensure that the original file is deleted if any
        another_svg = '![](http://upload.wikimedia.org/wikipedia/commons/3/32/Arrow.svg)'
        new_md = retrieve_and_update_images_links(another_svg, tempdir)
        self.assertEqual('![](images/Arrow.png)', new_md)

        self.assertTrue(os.path.isfile(os.path.join(tempdir, 'images/Arrow.png')))  # image was converted in PNG
        self.assertFalse(os.path.isfile(os.path.join(tempdir, 'images/Arrow.svg')))  # and the original SVG was deleted

        # finally, clean up:
        shutil.rmtree(tempdir)

    def test_migrate_zep12(self):
        private_mini_tuto = MiniTutorialFactory(title="Private Mini tuto")
        private_mini_tuto.authors.add(self.user_author)
        private_mini_tuto.save()
        multi_author_tuto = MiniTutorialFactory(title="Multi User Tuto")
        multi_author_tuto.authors.add(self.user_author)
        multi_author_tuto.authors.add(self.staff)
        multi_author_tuto.save()
        public_mini_tuto = PublishedMiniTutorial(title="Public Mini Tuto")
        public_mini_tuto.authors.add(self.user_author)
        public_mini_tuto.save()
        OldTutoValidation(tutorial=public_mini_tuto,
                          version=public_mini_tuto.sha_public,
                          date_proposition=datetime.datetime.now(),
                          comment_authors=u"La vie est belle, le destin s'en écarte.",
                          comment_validator=u"Personne ne joue avec les mêmes cartes.",
                          validator=self.staff,
                          status="ACCEPT",
                          date_reserve=datetime.datetime.now(),
                          date_validation=datetime.datetime.now()).save()
        staff_note = NoteFactory(
            tutorial=public_mini_tuto,
            position=1,
            author=self.staff)
        liked_note = NoteFactory(
            tutorial=public_mini_tuto,
            position=2,
            author=self.user_author)
        t_read = TutorialRead()
        t_read.tutorial = public_mini_tuto
        t_read.user = self.staff
        t_read.note = staff_note
        t_read.save()
        like = CommentLike()
        like.comments = liked_note
        like.user = self.staff
        like.save()
        big_tuto = BigTutorialFactory(title="Big tuto")
        big_tuto.authors.add(self.user_author)
        big_tuto.save()
        public_big_tuto = PublishedBigTutorial(light=False, title="Public Big Tuto")
        public_big_tuto.authors.add(self.user_author)
        public_big_tuto.save()
        private_article = ArticleFactory(title="Private Article")
        private_article.authors.add(self.user_author)
        private_article.save()
        multi_author_article = ArticleFactory(title="Multi Author Article")
        multi_author_article.authors.add(self.user_author)
        multi_author_article.authors.add(self.staff)
        multi_author_article.save()
        public_article = PublishedArticleFactory(title="Public Article")
        public_article.authors.add(self.user_author)
        public_article.save()
        OldArticleValidation(article=public_article,
                             version=public_article.sha_public,
                             date_proposition=datetime.datetime.now(),
                             comment_authors=u"Pourquoi fortune et infortune?",
                             comment_validator=u"Pourquoi suis-je né les poches vides?",
                             validator=self.staff,
                             status="ACCEPT",
                             date_reserve=datetime.datetime.now(),
                             date_validation=datetime.datetime.now()).save()
        staff_note = ReactionFactory(
            article=public_article,
            position=1,
            author=self.staff)
        liked_reaction = ReactionFactory(
            article=public_article,
            position=2,
            author=self.user_author)
        a_read = ArticleRead()
        a_read.article = public_article
        a_read.user = self.staff
        a_read.reaction = staff_note
        a_read.save()
        like = CommentLike()
        like.comments = liked_reaction
        like.user = self.staff
        like.save()
        category1 = CategoryFactory(position=1)
        forum11 = ForumFactory(
            category=category1,
            position_in_category=1)
        beta_tuto = BetaMiniTutorialFactory(title=u"Beta Tuto", forum=forum11, author=self.user_author)
        beta_tuto.authors.add(self.user_author)
        beta_tuto.save()
        call_command('migrate_to_zep12')
        # 1 tuto in setup, 4 mini tutos, 1 big tuto, 3 articles
        self.assertEqual(PublishableContent.objects.filter(authors__pk__in=[self.user_author.pk]).count(), 10)
        # if we had n published content we must have 2 * n PublishedContent entities to handle redirections.
        self.assertEqual(PublishedContent.objects.filter(content__authors__pk__in=[self.user_author.pk]).count(), 2 * 3)
        self.assertEqual(ContentReaction.objects.filter(author__pk=self.staff.pk).count(), 2)
        migrated_pulished_article = PublishableContent.objects.filter(authors__in=[self.user_author],
                                                                      title=public_article.title,
                                                                      type="ARTICLE").first()
        self.assertIsNotNone(migrated_pulished_article)
        self.assertIsNotNone(migrated_pulished_article.last_note)
        self.assertEqual(2, ContentReaction.objects.filter(related_content=migrated_pulished_article).count())
        self.assertEqual(1, ContentRead.objects.filter(content=migrated_pulished_article).count())
        self.assertTrue(migrated_pulished_article.is_public(migrated_pulished_article.sha_public))
        self.assertTrue(migrated_pulished_article.load_version(migrated_pulished_article.sha_public).has_extracts())
        self.assertEqual(len(migrated_pulished_article.load_version(migrated_pulished_article.sha_public).children), 2)

        migrated_pulished_tuto = PublishableContent.objects.filter(authors__in=[self.user_author],
                                                                   title=public_mini_tuto.title,
                                                                   type="TUTORIAL").first()
        self.assertIsNotNone(migrated_pulished_tuto)
        self.assertIsNotNone(migrated_pulished_tuto.last_note)
        self.assertEqual(2, ContentReaction.objects.filter(related_content=migrated_pulished_tuto).count())
        self.assertEqual(1, ContentRead.objects.filter(content=migrated_pulished_tuto).count())
        self.assertTrue(migrated_pulished_tuto.is_public(migrated_pulished_tuto.sha_public))
        beta_content = PublishableContent.objects.filter(title=beta_tuto.title).first()
        self.assertIsNotNone(beta_content)
        self.assertEqual(beta_content.sha_beta, beta_tuto.sha_beta)
        self.assertEqual(Topic.objects.filter(key=beta_tuto.pk).first().pk, beta_content.beta_topic.pk)

        multi_author_content = PublishableContent.objects.filter(type="TUTORIAL", title=multi_author_tuto.title)\
            .first()
        self.assertIsNotNone(multi_author_content)
        self.assertEqual(multi_author_content.authors.count(), multi_author_tuto.authors.count())
        multi_author_content = PublishableContent.objects.filter(type="ARTICLE", title=multi_author_article.title)\
            .first()
        self.assertIsNotNone(multi_author_content)
        self.assertEqual(multi_author_content.authors.count(), multi_author_article.authors.count())
        old_tutorial_module_prefix = "oldtutoriels"
        old_article_module_prefix = "oldarticles"
        new_tutorial_module_prefix = "tutoriels"
        new_article_module_prefix = "articles"
        public_article_url = public_article.get_absolute_url_online()\
            .replace(old_article_module_prefix, new_article_module_prefix)
        public_tutorial_url = public_mini_tuto.get_absolute_url_online()\
            .replace(old_tutorial_module_prefix, new_tutorial_module_prefix)
        self.assertEqual(301, self.client.get(public_article_url).status_code)
        self.assertEqual(301, self.client.get(public_tutorial_url).status_code)
        public_chapter = Chapter.objects.filter(part__tutorial__pk=public_big_tuto.pk).first()
        self.assertIsNotNone(public_chapter)
        public_chapter_url = public_chapter.get_absolute_url_online()
        public_chapter_url = public_chapter_url.replace(old_tutorial_module_prefix, new_tutorial_module_prefix)

        self.assertEqual(301, self.client.get(public_chapter_url).status_code)
        self.assertEqual(200, self.client.get(public_chapter_url, follow=True).status_code)
        self.assertEqual(200, self.client.get(public_article_url, follow=True).status_code)
        self.assertEqual(200, self.client.get(public_tutorial_url, follow=True).status_code)
        tuto_validation = Validation.objects.filter(content__pk=migrated_pulished_tuto.pk).first()
        self.assertIsNotNone(tuto_validation)
        self.assertEqual(tuto_validation.status, "ACCEPT")
        self.assertEqual(tuto_validation.validator.pk, self.staff.pk)
        article_validation = Validation.objects.filter(content__pk=migrated_pulished_article.pk).first()
        self.assertIsNotNone(article_validation)
        self.assertEqual(article_validation.status, "ACCEPT")
        self.assertEqual(article_validation.validator.pk, self.staff.pk)

    def test_generate_pdf(self):
        """ensure the behavior of the `python manage.py generate_pdf` commmand"""

        settings.ZDS_APP['content']['build_pdf_when_published'] = True  # this test need PDF build, if any

        tuto = PublishedContentFactory(type='TUTORIAL')  # generate and publish a tutorial
        published = PublishedContent.objects.get(content_pk=tuto.pk)

        tuto2 = PublishedContentFactory(type='TUTORIAL')  # generate and publish a second tutorial
        published2 = PublishedContent.objects.get(content_pk=tuto2.pk)

        # ensure that PDF exists in the first place
        self.assertTrue(published.have_pdf())
        self.assertTrue(published2.have_pdf())

        pdf_path = os.path.join(published.get_extra_contents_directory(), published.content_public_slug + '.pdf')
        pdf_path2 = os.path.join(published2.get_extra_contents_directory(), published2.content_public_slug + '.pdf')
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(os.path.exists(pdf_path2))

        # 1. re-generate (all) PDFs
        os.remove(pdf_path)
        os.remove(pdf_path2)
        self.assertFalse(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(pdf_path2))
        call_command('generate_pdf')
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(os.path.exists(pdf_path2))  # both PDFs are generated

        # 2. re-generate a given PDF
        os.remove(pdf_path)
        os.remove(pdf_path2)
        self.assertFalse(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(pdf_path2))
        call_command('generate_pdf', 'id={}'.format(tuto.pk))
        self.assertTrue(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(pdf_path2))  # only the first PDF is generated

        # 3. re-generate a given PDF with a wrong id
        os.remove(pdf_path)
        self.assertFalse(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(pdf_path2))
        call_command('generate_pdf', 'id=-1')  # There is no content with pk=-1
        self.assertFalse(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(pdf_path2))  # so no PDF is generated !

    def test_last_participation_is_old(self):
        article = PublishedContentFactory(author_list=[self.user_author], type="ARTICLE")
        newUser = ProfileFactory().user
        reac = ContentReaction(author=self.user_author, position=1, related_content=article)
        reac.update_content("I will find you. And I Will Kill you.")
        reac.save()
        article.last_note = reac
        article.save()

        self.assertFalse(last_participation_is_old(article, newUser))
        ContentRead(user=self.user_author, note=reac, content=article).save()
        reac = ContentReaction(author=newUser, position=2, related_content=article)
        reac.update_content("I will find you. And I Will Kill you.")
        reac.save()
        article.last_note = reac
        article.save()
        ContentRead(user=newUser, note=reac, content=article).save()
        self.assertFalse(last_participation_is_old(article, newUser))
        self.assertTrue(last_participation_is_old(article, self.user_author))

    def testParseBadManifest(self):
        base_content = PublishableContentFactory(author_list=[self.user_author])
        versioned = base_content.load_version()
        versioned.add_container(Container(u"un peu plus près de 42"))
        versioned.dump_json()
        manifest = os.path.join(versioned.get_path(), "manifest.json")
        dictionary = json_reader.load(open(manifest))

        old_title = dictionary['title']

        # first bad title
        dictionary['title'] = 81 * ['a']
        self.assertRaises(BadManifestError,
                          get_content_from_json, dictionary, None, '',
                          max_title_len=PublishableContent._meta.get_field('title').max_length)
        dictionary['title'] = "".join(dictionary['title'])
        self.assertRaises(BadManifestError,
                          get_content_from_json, dictionary, None, '',
                          max_title_len=PublishableContent._meta.get_field('title').max_length)
        dictionary['title'] = '...'
        self.assertRaises(InvalidSlugError,
                          get_content_from_json, dictionary, None, '',
                          max_title_len=PublishableContent._meta.get_field('title').max_length)

        dictionary['title'] = old_title
        dictionary['children'][0]['title'] = 81 * ['a']
        self.assertRaises(BadManifestError,
                          get_content_from_json, dictionary, None, '',
                          max_title_len=PublishableContent._meta.get_field('title').max_length)

        dictionary['children'][0]['title'] = "bla"
        dictionary['children'][0]['slug'] = "..."
        self.assertRaises(InvalidSlugError,
                          get_content_from_json, dictionary, None, '',
                          max_title_len=PublishableContent._meta.get_field('title').max_length)

    def tearDown(self):
        if os.path.isdir(settings.ZDS_APP['content']['repo_private_path']):
            shutil.rmtree(settings.ZDS_APP['content']['repo_private_path'])
        if os.path.isdir(settings.ZDS_APP['content']['repo_public_path']):
            shutil.rmtree(settings.ZDS_APP['content']['repo_public_path'])
        if os.path.isdir(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT)
        if os.path.isdir(settings.ZDS_APP['tutorial']['repo_path']):
            shutil.rmtree(settings.ZDS_APP['tutorial']['repo_path'])
        if os.path.isdir(settings.ZDS_APP['tutorial']['repo_public_path']):
            shutil.rmtree(settings.ZDS_APP['tutorial']['repo_public_path'])
        if os.path.isdir(settings.ZDS_APP['article']['repo_path']):
            shutil.rmtree(settings.ZDS_APP['article']['repo_path'])

        # re-active PDF build
        settings.ZDS_APP['content']['build_pdf_when_published'] = True
