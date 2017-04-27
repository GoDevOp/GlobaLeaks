# -*- coding: UTF-8
#
#   /admin/receivers
#   *****
# Implementation of the code executed on handler /admin/receivers
#
from twisted.internet.defer import inlineCallbacks

from globaleaks import models
from globaleaks.acl import db_access_receiver, db_access_tenant
from globaleaks.handlers.admin.context import db_associate_receiver_contexts
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.public import db_prepare_receivers_serialization
from globaleaks.handlers.user import user_serialize_user
from globaleaks.orm import transact
from globaleaks.rest import errors, requests
from globaleaks.rest.apicache import GLApiCache
from globaleaks.state import app_state
from globaleaks.utils.structures import fill_localized_keys, get_localized_values

from globaleaks.state import app_state


def admin_serialize_receiver(store, receiver, language, data = None):
    """
    Serialize the specified receiver

    :param language: the language in which to localize data
    :return: a dictionary representing the serialization of the receiver
    """
    if data is None:
        data = db_prepare_receivers_serialization(store, [receiver])

    ret_dict = user_serialize_user(store, receiver.user, language)

    ret_dict.update({
        'can_delete_submission': receiver.can_delete_submission,
        'can_postpone_expiration': receiver.can_postpone_expiration,
        'can_grant_permissions': receiver.can_grant_permissions,
        'mail_address': receiver.user.mail_address,
        'configuration': receiver.configuration,
        'tip_notification': receiver.tip_notification,
        'presentation_order': receiver.presentation_order,
        'contexts': data['contexts'][receiver.id]
    })

    return get_localized_values(ret_dict, receiver, receiver.localized_keys, language)


def db_get_usermodel_list(store, model, tid):
    return store.find(model, model.id == models.User_Tenant.user_id,
                             models.User_Tenant.tenant_id == tid)

def db_get_usermodel(store, model, id):
    return store.find(model, id = id).one()

@transact
def get_receiver_list(store, rstate, language):
    """
    Returns:
        (list) the list of receivers
    """
    db_access_tenant(store, rstate, rstate.tid)

    receivers = db_get_usermodel_list(store, models.Receiver, rstate.tid)

    data = db_prepare_receivers_serialization(store, receivers)

    return [admin_serialize_receiver(store, receiver, language, data) for receiver in receivers]


@transact
def get_receiver(store, receiver_id, language):
    receiver = db_get_usermodel(store, models.Receiver, receiver_id)

    return admin_serialize_receiver(store, receiver, language)


@transact
def update_receiver(store, tid, receiver_id, request, language):
    """
    Updates the specified receiver with the details.
    raises :class:`globaleaks.errors.ReceiverIdNotFound` if the receiver does
    not exist.
    """
    receiver = models.Receiver.db_get(store, id=receiver_id)

    fill_localized_keys(request, models.Receiver.localized_keys, language)

    receiver.update(request)

    db_associate_receiver_contexts(store, receiver, request['contexts'])

    return admin_serialize_receiver(store, receiver, language)


class ReceiversCollection(BaseHandler):
    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def get(self):
        """
        Return all the receivers.

        Parameters: None
        Response: adminReceiverList
        Errors: None
        """
        response = yield get_receiver_list(self.req_state,
                                           self.request.language)

        self.write(response)


class ReceiverInstance(BaseHandler):
    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def get(self, receiver_id):
        """
        Get the specified receiver.

        Parameters: receiver_id
        Response: AdminReceiverDesc
        Errors: InvalidInputFormat, ReceiverIdNotFound
        """
        response = yield get_receiver(receiver_id,
                                      self.request.language)

        self.write(response)

    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def put(self, receiver_id):
        """
        Update the specified receiver.

        Parameters: receiver_id
        Request: AdminReceiverDesc
        Response: AdminReceiverDesc
        Errors: InvalidInputFormat, ReceiverIdNotFound, ContextIdNotFound
        """
        request = self.validate_message(self.request.body, requests.AdminReceiverDesc)

        response = yield update_receiver(self.current_tenant,
                                         receiver_id,
                                         request,
                                         self.request.language)

        GLApiCache.invalidate(self.current_tenant)

        self.write(response)
