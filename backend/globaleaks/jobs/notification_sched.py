# -*- encoding: utf-8 -*-
# Implement the notification of new submissions

import copy

from twisted.internet import reactor, threads

from globaleaks import models
from globaleaks.constants import ROOT_TENANT
from globaleaks.handlers.admin.context import admin_serialize_context
from globaleaks.handlers.admin.node import db_admin_serialize_node
from globaleaks.handlers.admin.notification import db_get_notification
from globaleaks.handlers.admin.receiver import admin_serialize_receiver
from globaleaks.handlers.rtip import serialize_rtip, serialize_message, serialize_comment
from globaleaks.jobs.base import GLJob
from globaleaks.orm import transact, transact_sync
from globaleaks.security import GLBPGP
from globaleaks.state import app_state
from globaleaks.settings import GLSettings
from globaleaks.utils.mailutils import sendmail
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import log


trigger_template_map = {
    'ReceiverTip': u'tip',
    'Message': u'message',
    'Comment': u'comment',
    'ReceiverFile': u'file'
}


trigger_model_map = {
    'ReceiverTip': models.ReceiverTip,
    'Message': models.Message,
    'Comment': models.Comment,
    'ReceiverFile': models.ReceiverFile
}


class MailGenerator(object):
    def __init__(self):
        self.cache = {}

    def serialize_config(self, store, key, language):
        cache_key = key + '-' + language

        if cache_key not in self.cache:
            if key == 'node':
                cache_obj = db_admin_serialize_node(store, ROOT_TENANT, language)
            elif key == 'notification':
                cache_obj = db_get_notification(store, ROOT_TENANT, language)

            self.cache[cache_key] = cache_obj

        return self.cache[cache_key]

    def serialize_obj(self, store, key, obj, language):
        obj_id = obj.id

        cache_key = key + '-' + obj_id + '-' + language

        if cache_key not in self.cache:
            if key == 'tip':
                cache_obj = serialize_rtip(store, obj, language)
            elif key == 'context':
                cache_obj = admin_serialize_context(store, obj, language)
            elif key == 'receiver':
                cache_obj = admin_serialize_receiver(store, obj, language)
            elif key == 'message':
                cache_obj = serialize_message(obj)
            elif key == 'comment':
                cache_obj = serialize_comment(obj)
            elif key == 'file':
                cache_obj = models.serializers.serialize_ifile(obj)

            self.cache[cache_key] = cache_obj

        return self.cache[cache_key]

    def process_ReceiverTip(self, store, rtip, data):
        language = rtip.receiver.user.language

        data['tip'] = self.serialize_obj(store, 'tip', rtip, language)
        data['context'] = self.serialize_obj(store, 'context', rtip.internaltip.context, language)
        data['receiver'] = self.serialize_obj(store, 'receiver', rtip.receiver, language)

        self.process_mail_creation(store, data)

    def process_Message(self, store, message, data):
        # if the message is destinated to the whistleblower no mail should be sent
        if message.type == u"receiver":
            return

        language = message.receivertip.receiver.user.language

        data['tip'] = self.serialize_obj(store, 'tip', message.receivertip, language)
        data['context'] = self.serialize_obj(store, 'context', message.receivertip.internaltip.context, language)
        data['receiver'] = self.serialize_obj(store, 'receiver', message.receivertip.receiver, language)
        data['message'] = self.serialize_obj(store, 'message', message, language)

        self.process_mail_creation(store, data)

    def process_Comment(self, store, comment, data):
        for rtip in comment.internaltip.receivertips:
            if comment.type == u'receiver' and comment.author == rtip.receiver.user.name:
                continue

            language = rtip.receiver.user.language

            dataX = copy.deepcopy(data)
            dataX['tip'] = self.serialize_obj(store, 'tip', rtip, language)
            dataX['context'] = self.serialize_obj(store, 'context', comment.internaltip.context, language)
            dataX['receiver'] = self.serialize_obj(store, 'receiver', rtip.receiver, language)
            dataX['comment'] = self.serialize_obj(store, 'comment', comment, language)

            self.process_mail_creation(store, dataX)

    def process_ReceiverFile(self, store, rfile, data):
        # avoid sending an email for the files that have been loaded during the initial submission
        if rfile.internalfile.submission:
            return

        language = rfile.receivertip.receiver.user.language

        data['tip'] = self.serialize_obj(store, 'tip', rfile.receivertip, language)
        data['context'] = self.serialize_obj(store, 'context', rfile.internalfile.internaltip.context, language)
        data['receiver'] = self.serialize_obj(store, 'receiver', rfile.receivertip.receiver, language)
        data['file'] = self.serialize_obj(store, 'file', rfile.internalfile, language)

        self.process_mail_creation(store, data)

    def process_mail_creation(self, store, data):
        data['tid'] = data['context']['tid']
        receiver_id = data['receiver']['id']

        # Do not spool emails if the receiver has opted out of ntfns for this tip.
        if not data['tip']['enable_notifications']:
          log.debug("Discarding emails for %s due to receiver's preference." % receiver_id)
          return

        # TODO(tid_state) the current solution is global and configurable only
        # by the root admin. See also #798
        sent_emails = GLSettings.get_mail_counter(receiver_id)
        if sent_emails >= app_state.memc.notif.notification_threshold_per_hour:
            log.debug("Discarding emails for receiver %s due to threshold already exceeded for the current hour" %
                      receiver_id)
            return

        GLSettings.increment_mail_counter(receiver_id)
        if sent_emails >= app_state.memc.notif.notification_threshold_per_hour:
            log.info("Reached threshold of %d emails with limit of %d for receiver %s" % (
                     sent_emails,
                     app_state.memc.notif.notification_threshold_per_hour,
                     receiver_id)
            )

            # simply changing the type of the notification causes
            # to send the notification_limit_reached
            data['type'] = u'receiver_notification_limit_reached'

        data['notification'] = self.serialize_config(store, 'notification', data['receiver']['language'])
        data['node'] = self.serialize_config(store, 'node', data['receiver']['language'])

        if not data['node']['allow_unencrypted'] and len(data['receiver']['pgp_key_public']) == 0:
            return

        subject, body = Templating().get_mail_subject_and_body(data)

        # If the receiver has encryption enabled encrypt the mail body
        if len(data['receiver']['pgp_key_public']):
            gpob = GLBPGP()

            try:
                gpob.load_key(data['receiver']['pgp_key_public'])
                body = gpob.encrypt_message(data['receiver']['pgp_key_fingerprint'], body)
            except Exception as excep:
                log.err("Error in PGP interface object (for %s: %s)! (notification+encryption)" %
                        (data['receiver']['username'], str(excep)))

                return
            finally:
                # the finally statement is always called also if
                # except contains a return or a raise
                gpob.destroy_environment()

        store.add(models.Mail({
            'tid': data['tid'],
            'address': data['receiver']['mail_address'],
            'subject': subject,
            'body': body
        }))


    @transact_sync
    def generate(self, store):
        for trigger in ['ReceiverTip', 'Comment', 'Message', 'ReceiverFile']:
            model = trigger_model_map[trigger]

            elements = store.find(model, model.new == True)
            for element in elements:
                element.new = False

                data = {
                    'type': trigger_template_map[trigger]
                }

                getattr(self, 'process_%s' % trigger)(store, element, data)

            count = elements.count()
            if count > 0:
                log.debug("Notification: generated %d notifications of type %s" %
                          (count, trigger))


@transact
def delete_sent_mail(store, result, mail_id):
    store.find(models.Mail, models.Mail.id == mail_id).remove()


@transact_sync
def get_mails_from_the_pool(store):
    ret = []

    for mail in store.find(models.Mail):
        if mail.processing_attempts > 9:
            store.remove(mail)
            continue

        mail.processing_attempts += 1

        ret.append({
            'id': mail.id,
            'address': mail.address,
            'subject': mail.subject,
            'body': mail.body
        })

    return ret


class NotificationSchedule(GLJob):
    name = "Notification"
    interval = 5
    monitor_interval = 3 * 60

    def sendmail(self, mail):
        d = sendmail(app_state.get_root_tenant(), mail['address'], mail['subject'], mail['body'])
        d.addCallback(delete_sent_mail, mail['id'])
        return d

    def spool_emails(self):
        mails = get_mails_from_the_pool()
        for mail in mails:
            threads.blockingCallFromThread(reactor, self.sendmail, mail)

    def operation(self):
        MailGenerator().generate()

        self.spool_emails()
