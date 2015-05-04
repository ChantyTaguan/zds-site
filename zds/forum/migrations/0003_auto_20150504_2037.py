# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0002_auto_20150410_1505'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='topicfollowed',
            name='topic',
        ),
        migrations.RemoveField(
            model_name='topicfollowed',
            name='user',
        ),
        migrations.DeleteModel(
            name='TopicFollowed',
        ),
    ]
