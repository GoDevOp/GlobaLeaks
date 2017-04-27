# -*- encoding: utf-8 -*-
# Implements periodic checks in order to verify pgp key status and other consistencies:
from datetime import timedelta

from globaleaks import models
from globaleaks.handlers.admin.node import db_admin_serialize_node
from globaleaks.handlers.admin.notification import db_get_notification
from globaleaks.handlers.admin.user import db_system_get_admin_users
from globaleaks.handlers.user import user_serialize_user
from globaleaks.jobs.base import GLJob
from globaleaks.orm import transact_sync
from globaleaks.state import app_state
from globaleaks.settings import GLSettings
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import datetime_now, datetime_null


__all__ = ['PGPCheckSchedule']

def db_get_expired_or_expiring_pgp_users(store):
    threshold = datetime_now() + timedelta(days=15)

    return store.find(models.User, models.User.pgp_key_public != u'',
                                   models.User.pgp_key_expiration != datetime_null(),
                                   models.User.pgp_key_expiration < threshold)


class PGPCheckSchedule(GLJob):
    name = "PGP Check"
    interval = 24 * 3600
    monitor_interval = 5 * 60

    def get_start_time(self):
         current_time = datetime_now()
         return (3600 * 24) - (current_time.hour * 3600) - (current_time.minute * 60) - current_time.second

    def prepare_admin_pgp_alerts(self, store, expired_or_expiring):
        for user_desc in db_system_get_admin_users(store, app_state.root_id):
            user_language = user_desc['language']

            # TODO TODO TODO (tid_me) TODO TODO TODO
            data = {
                'type': u'admin_pgp_alert',
                'node': db_admin_serialize_node(store, app_state.root_id, user_language),
                'notification': db_get_notification(store, app_state.root_id, user_language),
                'users': expired_or_expiring
            }

            subject, body = Templating().get_mail_subject_and_body(data)

            store.add(models.Mail({
                'tid': app_state.root_id,
                'address': user_desc['mail_address'],
                'subject': subject,
                'body': body
            }))


    def prepare_user_pgp_alerts(self, store, user_desc):
        user_language = user_desc['language']

        # TODO TODO TODO (tid_me) TODO TODO TODO
        data = {
            'type': u'pgp_alert',
            'node': db_admin_serialize_node(store, app_state.root_id, user_language),
            'notification': db_get_notification(store, app_state.root_id, user_language),
            'user': user_desc
        }

        subject, body = Templating().get_mail_subject_and_body(data)

        store.add(models.Mail({
            'tid': app_state.root_id,
            'address': user_desc['mail_address'],
            'subject': subject,
            'body': body
        }))

    @transact_sync
    def perform_pgp_validation_checks(self, store, tstate):
        expired_or_expiring = []

        for user in db_get_expired_or_expiring_pgp_users(store):
            expired_or_expiring.append(user_serialize_user(store, user, tstate.memc.default_language))

            if user.pgp_key_expiration < datetime_now():
                user.pgp_key_public = ''
                user.pgp_key_fingerprint = ''
                user.pgp_key_expiration = datetime_null()

        if len(expired_or_expiring):
            if not tstate.memc.notif.disable_admin_notification_emails:
                self.prepare_admin_pgp_alerts(store, expired_or_expiring)

            for user_desc in expired_or_expiring:
                self.prepare_user_pgp_alerts(store, user_desc)

    def operation(self):
        # TODO TIDME
        for tstate in app_state.tenant_states.values():
            self.perform_pgp_validation_checks(tstate)
