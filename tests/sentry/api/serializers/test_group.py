# -*- coding: utf-8 -*-

from __future__ import absolute_import

from datetime import timedelta

from django.utils import timezone
from mock import patch

from sentry.api.serializers import serialize
from sentry.models import (
    GroupResolution, GroupResolutionStatus, GroupSnooze, GroupStatus,
    GroupSubscription, Release, UserOption, UserOptionValue
)
from sentry.testutils import TestCase


class GroupSerializerTest(TestCase):
    def test_is_ignored_with_expired_snooze(self):
        now = timezone.now().replace(microsecond=0)

        user = self.create_user()
        group = self.create_group(
            status=GroupStatus.IGNORED,
        )
        GroupSnooze.objects.create(
            group=group,
            until=now - timedelta(minutes=1),
        )

        result = serialize(group, user)
        assert result['status'] == 'unresolved'
        assert result['statusDetails'] == {}

    def test_is_ignored_with_valid_snooze(self):
        now = timezone.now().replace(microsecond=0)

        user = self.create_user()
        group = self.create_group(
            status=GroupStatus.IGNORED,
        )
        snooze = GroupSnooze.objects.create(
            group=group,
            until=now + timedelta(minutes=1),
        )

        result = serialize(group, user)
        assert result['status'] == 'ignored'
        assert result['statusDetails'] == {'ignoreUntil': snooze.until}

    def test_resolved_in_next_release(self):
        release = Release.objects.create(
            project=self.project,
            organization_id=self.project.organization_id,
            version='a',
        )
        release.add_project(self.project)
        user = self.create_user()
        group = self.create_group(
            status=GroupStatus.RESOLVED,
        )
        GroupResolution.objects.create(
            group=group,
            release=release,
        )

        result = serialize(group, user)
        assert result['status'] == 'resolved'
        assert result['statusDetails'] == {'inNextRelease': True}

    def test_resolved_in_next_release_expired_resolution(self):
        release = Release.objects.create(
            project=self.project,
            organization_id=self.project.organization_id,
            version='a',
        )
        release.add_project(self.project)
        user = self.create_user()
        group = self.create_group(
            status=GroupStatus.RESOLVED,
        )
        GroupResolution.objects.create(
            group=group,
            release=release,
            status=GroupResolutionStatus.RESOLVED,
        )

        result = serialize(group, user)
        assert result['status'] == 'resolved'
        assert result['statusDetails'] == {}

    @patch('sentry.models.Group.is_over_resolve_age')
    def test_auto_resolved(self, mock_is_over_resolve_age):
        mock_is_over_resolve_age.return_value = True

        user = self.create_user()
        group = self.create_group(
            status=GroupStatus.UNRESOLVED,
        )

        result = serialize(group, user)
        assert result['status'] == 'resolved'
        assert result['statusDetails'] == {'autoResolved': True}

    def test_subscribed(self):
        user = self.create_user()
        group = self.create_group()

        GroupSubscription.objects.create(
            user=user,
            group=group,
            project=group.project,
            is_active=True,
        )

        result = serialize(group, user)
        assert result['isSubscribed']
        assert result['subscriptionDetails'] == {
            'reason': 'unknown',
        }

    def test_explicit_unsubscribed(self):
        user = self.create_user()
        group = self.create_group()

        GroupSubscription.objects.create(
            user=user,
            group=group,
            project=group.project,
            is_active=False,
        )

        result = serialize(group, user)
        assert not result['isSubscribed']
        assert not result['subscriptionDetails']

    def test_implicit_subscribed(self):
        user = self.create_user()
        group = self.create_group()

        combinations = (
            # ((default, project), (subscribed, details))
            ((None, None), (True, None)),
            ((UserOptionValue.all_conversations, None), (True, None)),
            ((UserOptionValue.all_conversations, UserOptionValue.all_conversations), (True, None)),
            ((UserOptionValue.all_conversations, UserOptionValue.participating_only), (False, None)),
            ((UserOptionValue.all_conversations, UserOptionValue.no_conversations), (False, {'disabled': True})),
            ((UserOptionValue.participating_only, None), (False, None)),
            ((UserOptionValue.participating_only, UserOptionValue.all_conversations), (True, None)),
            ((UserOptionValue.participating_only, UserOptionValue.participating_only), (False, None)),
            ((UserOptionValue.participating_only, UserOptionValue.no_conversations), (False, {'disabled': True})),
            ((UserOptionValue.no_conversations, None), (False, {'disabled': True})),
            ((UserOptionValue.no_conversations, UserOptionValue.all_conversations), (True, None)),
            ((UserOptionValue.no_conversations, UserOptionValue.participating_only), (False, None)),
            ((UserOptionValue.no_conversations, UserOptionValue.no_conversations), (False, {'disabled': True})),
        )

        def maybe_set_value(project, value):
            if value is not None:
                UserOption.objects.set_value(
                    user=user,
                    project=project,
                    key='workflow:notifications',
                    value=value,
                )
            else:
                UserOption.objects.unset_value(
                    user=user,
                    project=project,
                    key='workflow:notifications',
                )

        for options, (is_subscribed, subscription_details) in combinations:
            default_value, project_value = options
            UserOption.objects.clear_cache()
            maybe_set_value(None, default_value)
            maybe_set_value(group.project, project_value)
            result = serialize(group, user)
            assert result['isSubscribed'] is is_subscribed
            assert result.get('subscriptionDetails') == subscription_details

    def test_global_no_conversations_overrides_group_subscription(self):
        user = self.create_user()
        group = self.create_group()

        GroupSubscription.objects.create(
            user=user,
            group=group,
            project=group.project,
            is_active=True,
        )

        UserOption.objects.set_value(
            user=user,
            project=None,
            key='workflow:notifications',
            value=UserOptionValue.no_conversations,
        )

        result = serialize(group, user)
        assert not result['isSubscribed']
        assert result['subscriptionDetails'] == {
            'disabled': True,
        }

    def test_project_no_conversations_overrides_group_subscription(self):
        user = self.create_user()
        group = self.create_group()

        GroupSubscription.objects.create(
            user=user,
            group=group,
            project=group.project,
            is_active=True,
        )

        UserOption.objects.set_value(
            user=user,
            project=group.project,
            key='workflow:notifications',
            value=UserOptionValue.no_conversations,
        )

        result = serialize(group, user)
        assert not result['isSubscribed']
        assert result['subscriptionDetails'] == {
            'disabled': True,
        }

    def test_no_user_unsubscribed(self):
        group = self.create_group()

        result = serialize(group)
        assert not result['isSubscribed']
