"""
sentry.models.processingissue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2016 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

from django.db import models

from sentry.db.models import FlexibleForeignKey, Model, GzippedDictField, \
    BaseManager


class ReleaseProblemManager(BaseManager):

    def record_problem(self, release, key, data):
        return self.update_or_create(
            release=release,
            key=key,
            defaults={'data': data},
        )[0]


class ProcessingIssue(Model):
    __core__ = False
    project = FlexibleForeignKey('sentry.Project')
    type = models.CharField(max_length=60)
    key = models.CharField(max_length=256)
    data = GzippedDictField()

    objects = ReleaseProblemManager()

    class Meta:
        app_label = 'sentry'
        db_table = 'sentry_processingissue'
        unique_together = [
            ('project', 'type', 'key'),
        ]


class ProcessingIssueGroup(Model):
    __core__ = False
    group = FlexibleForeignKey('sentry.Group')
    release = FlexibleForeignKey('sentry.Release', null=True)
    issue = FlexibleForeignKey('sentry.ProcessingIssue')
    data = GzippedDictField()

    class Meta:
        app_label = 'sentry'
        db_table = 'sentry_processingissuegroup'
        unique_together = [
            ('group', 'release', 'issue'),
        ]
