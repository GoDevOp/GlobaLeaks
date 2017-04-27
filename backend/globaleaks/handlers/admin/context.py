# -*- coding: UTF-8
#
#   /admin/contexts
#   *****
# Implementation of the code executed on handler /admin/contexts
#
from twisted.internet.defer import inlineCallbacks

from globaleaks import models
from globaleaks.acl import db_access_context, db_access_tenant
from globaleaks.handlers.admin.modelimgs import db_get_model_img
from globaleaks.handlers.admin.questionnaire import db_get_default_questionnaire_id
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.public import  db_prepare_contexts_serialization
from globaleaks.orm import transact
from globaleaks.rest import errors, requests
from globaleaks.rest.apicache import GLApiCache
from globaleaks.utils.structures import fill_localized_keys, get_localized_values
from globaleaks.utils.utility import log


def admin_serialize_context(store, context, language, data=None):
    """
    Serialize the specified context

    :param store: the store on which perform queries.
    :param language: the language in which to localize data.
    :return: a dictionary representing the serialization of the context.
    """
    if data is None:
        data = db_prepare_contexts_serialization(store, [context])

    img = data['imgs'][context.id]

    ret_dict = {
        'id': context.id,
        'tid': context.tid,
        'tip_timetolive': context.tip_timetolive,
        'select_all_receivers': context.select_all_receivers,
        'maximum_selectable_receivers': context.maximum_selectable_receivers,
        'show_context': context.show_context,
        'show_recipients_details': context.show_recipients_details,
        'allow_recipients_selection': context.allow_recipients_selection,
        'show_small_receiver_cards': context.show_small_receiver_cards,
        'enable_comments': context.enable_comments,
        'enable_messages': context.enable_messages,
        'enable_two_way_comments': context.enable_two_way_comments,
        'enable_two_way_messages': context.enable_two_way_messages,
        'enable_attachments': context.enable_attachments,
        'enable_rc_to_wb_files': context.enable_rc_to_wb_files,
        'presentation_order': context.presentation_order,
        'show_receivers_in_alphabetical_order': context.show_receivers_in_alphabetical_order,
        'questionnaire_id': context.questionnaire_id,
        'receivers': data['receivers'][context.id],
        'picture': img.data if img else ''
    }

    return get_localized_values(ret_dict, context, context.localized_keys, language)


@transact
def get_context_recipients(store, context_id):
    return [rc.receiver_id for rc in store.find(models.Receiver_Context, context_id=context_id)]


@transact
def get_context_list(store, rstate, language):
    """
    Returns the context list.

    :param store: the store on which perform queries.
    :param language: the language in which to localize data.
    :return: a dictionary representing the serialization of the contexts.
    """
    db_access_tenant(store, rstate, rstate.tid)

    contexts = store.find(models.Context, tid=rstate.tid)

    data = db_prepare_contexts_serialization(store, contexts)

    return [admin_serialize_context(store, context, language, data) for context in contexts]


def db_associate_receiver_contexts(store, receiver, contexts_ids):
    receiver.contexts.clear()

    for context_id in contexts_ids:
        context = models.Context.db_get(store, id=context_id)

        if context.tid in [t.id for t in receiver.user.tenants]:
            receiver.contexts.add(context)


def db_associate_context_receivers(store, context, receivers_ids):
    context.receivers.clear()

    for receiver_id in receivers_ids:
        receiver = models.Receiver.db_get(store, id=receiver_id)

        if context.tid in [t.id for t in receiver.user.tenants]:
            context.receivers.add(receiver)


@transact
def get_context(store, rstate, context_id, language):
    """
    Returns:
        (dict) the context with the specified id.
    """
    context = db_access_context(store, rstate, context_id)

    return admin_serialize_context(store, context, language)


def fill_context_request(request, language):
    fill_localized_keys(request, models.Context.localized_keys, language)

    request['tip_timetolive'] = -1 if request['tip_timetolive'] < 0 else request['tip_timetolive']

    if request['select_all_receivers']:
        if request['maximum_selectable_receivers']:
            log.debug("Resetting maximum_selectable_receivers (%d) because 'select_all_receivers' is True" %
                      request['maximum_selectable_receivers'])
        request['maximum_selectable_receivers'] = 0

    return request


def db_create_context(store, tid, request, language):
    request['tid'] = int(tid)

    request = fill_context_request(request, language)

    if request['questionnaire_id'] == '':
        request['questionnaire_id'] = db_get_default_questionnaire_id(store)

    if not request['allow_recipients_selection']:
        request['select_all_receivers'] = True

    context = models.Context(request)
    store.add(context)

    db_associate_context_receivers(store, context, request['receivers'])

    return context


def db_update_context(store, context, request, language):
    request = fill_context_request(request, language)

    if request['questionnaire_id'] == '':
        request['questionnaire_id'] = db_get_default_questionnaire_id(store)

    if not request['allow_recipients_selection']:
        request['select_all_receivers'] = True

    context.update(request)

    db_associate_context_receivers(store, context, request['receivers'])

    return context


@transact
def create_context(store, rstate, request, language):
    """
    Creates a new context from the request of a client.

    We associate to the context the list of receivers and if the receiver is
    not valid we raise a ReceiverIdNotFound exception.

    Args:
        (dict) the request containing the keys to set on the model.

    Returns:
        (dict) representing the configured context
    """
    db_access_tenant(store, rstate, rstate.tid)

    context = db_create_context(store, rstate.tid, request, language)

    return admin_serialize_context(store, context, language)


@transact
def update_context(store, rstate, context_id, request, language):
    """
    Updates the specified context. If the key receivers is specified we remove
    the current receivers of the Context and reset set it to the new specified
    ones.
    If no such context exists raises :class:`globaleaks.errors.ContextIdNotFound`.

    Args:
        context_id:

        request:
            (dict) the request to use to set the attributes of the Context

    Returns:
            (dict) the serialized object updated
    """
    context = db_access_context(store, rstate, context_id)

    context = db_update_context(store, context, request, language)

    return admin_serialize_context(store, context, language)


@transact
def delete_context(store, rstate, context_id):
    context = db_access_context(store, rstate, context_id)

    store.remove(context)


class ContextsCollection(BaseHandler):
    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def get(self):
        """
        Return all the contexts.

        Parameters: None
        Response: adminContextList
        Errors: None
        """
        response = yield get_context_list(self.req_state,
                                          self.request.language)

        self.write(response)

    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def post(self):
        """
        Create a new context.

        Request: AdminContextDesc
        Response: AdminContextDesc
        Errors: InvalidInputFormat, ReceiverIdNotFound
        """
        request = self.validate_message(self.request.body, requests.AdminContextDesc)

        response = yield create_context(self.req_state,
                                        request,
                                        self.request.language)

        GLApiCache.invalidate(self.current_tenant)

        self.write(response)


class ContextInstance(BaseHandler):
    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def get(self, context_id):
        """
        Get the specified context.

        Parameters: context_id
        Response: AdminContextDesc
        Errors: ContextIdNotFound, InvalidInputFormat
        """
        response = yield get_context(self.req_state,
                                     context_id,
                                     self.request.language)

        self.write(response)

    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def put(self, context_id):
        """
        Update the specified context.

        Parameters: context_id
        Request: AdminContextDesc
        Response: AdminContextDesc
        Errors: InvalidInputFormat, ContextIdNotFound, ReceiverIdNotFound

        Updates the specified context.
        """
        request = self.validate_message(self.request.body,
                                        requests.AdminContextDesc)

        response = yield update_context(self.req_state,
                                        context_id,
                                        request,
                                        self.request.language)

        GLApiCache.invalidate(self.current_tenant)

        self.write(response)


    @BaseHandler.transport_security_check('admin')
    @BaseHandler.authenticated('admin')
    @inlineCallbacks
    def delete(self, context_id):
        """
        Delete the specified context.

        Request: AdminContextDesc
        Response: None
        Errors: InvalidInputFormat, ContextIdNotFound
        """
        yield delete_context(self.req_state, context_id)

        GLApiCache.invalidate(self.current_tenant)
