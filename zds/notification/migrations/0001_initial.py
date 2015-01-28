# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Subscription'
        db.create_table(u'notification_subscription', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('profile', self.gf('django.db.models.fields.related.ForeignKey')(related_name='subscriptor', to=orm['member.Profile'])),
            ('type', self.gf('django.db.models.fields.CharField')(default='NEW_CONTENT', max_length=10, db_index=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('by_email', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('last_notification', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='last_notification', to=orm['notification.Notification'])),
        ))
        db.send_create_signal(u'notification', ['Subscription'])

        # Adding model 'Notification'
        db.create_table(u'notification_notification', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('subscription', self.gf('django.db.models.fields.related.ForeignKey')(related_name='subscription', to=orm['notification.Subscription'])),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('is_read', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal(u'notification', ['Notification'])


    def backwards(self, orm):
        # Deleting model 'Subscription'
        db.delete_table(u'notification_subscription')

        # Deleting model 'Notification'
        db.delete_table(u'notification_notification')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'member.profile': {
            'Meta': {'object_name': 'Profile'},
            'avatar_url': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'biography': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'can_read': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'can_write': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'email_for_answer': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'end_ban_read': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'end_ban_write': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'hover_or_click': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'karma': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'last_ip_address': ('django.db.models.fields.CharField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'last_visit': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'sdz_tutorial': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'show_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_sign': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'sign': ('django.db.models.fields.TextField', [], {'max_length': '250', 'blank': 'True'}),
            'site': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'profile'", 'unique': 'True', 'to': u"orm['auth.User']"})
        },
        u'notification.notification': {
            'Meta': {'object_name': 'Notification'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_read': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subscription'", 'to': u"orm['notification.Subscription']"})
        },
        u'notification.subscription': {
            'Meta': {'object_name': 'Subscription'},
            'by_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'last_notification': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'last_notification'", 'to': u"orm['notification.Notification']"}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subscriptor'", 'to': u"orm['member.Profile']"}),
            'type': ('django.db.models.fields.CharField', [], {'default': "'NEW_CONTENT'", 'max_length': '10', 'db_index': 'True'})
        }
    }

    complete_apps = ['notification']