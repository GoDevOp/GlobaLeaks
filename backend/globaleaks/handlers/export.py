# -*- coding: utf-8 -*-
#
# export
# *****
#
# Tip export utils
import copy

from cyclone.web import asynchronous
from storm.expr import In
from twisted.internet.defer import inlineCallbacks

from globaleaks import models
from globaleaks.handlers.admin.context import admin_serialize_context
from globaleaks.handlers.admin.node import db_admin_serialize_node
from globaleaks.handlers.admin.notification import db_get_notification
from globaleaks.handlers.admin.receiver import admin_serialize_receiver
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.rtip import db_access_rtip, serialize_rtip
from globaleaks.orm import transact
from globaleaks.settings import GLSettings
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import msdos_encode
from globaleaks.utils.zipstream import ZipStream


@transact
def get_tip_export(store, tid, user_id, rtip_id, language):
    rtip = db_access_rtip(store, user_id, rtip_id)

    receiver = rtip.receiver

    rtip_dict = serialize_rtip(store, rtip, language)

    export_dict = {
        'type': u'export_template',
        'node': db_admin_serialize_node(store, tid, language),
        'notification': db_get_notification(store, tid, language),
        'tip': serialize_rtip(store, rtip, language),
        'context': admin_serialize_context(store, rtip.internaltip.context, language),
        'receiver': admin_serialize_receiver(store, receiver, language),
        'comments': rtip_dict['comments'],
        'messages': rtip_dict['messages'],
        'files': []
    }

    export_template = Templating().format_template(export_dict['notification']['export_template'], export_dict).encode('utf-8')

    export_template = msdos_encode(export_template)

    export_dict['files'].append({'buf': export_template, 'name': "data.txt"})

    for rf in store.find(models.ReceiverFile, receivertip_id=rtip_id):
        rf.downloads += 1
        file_dict = models.serializers.serialize_rfile(rf)
        file_dict['name'] = 'files/' + file_dict['name']
        export_dict['files'].append(copy.deepcopy(file_dict))

    rtips_ids = [rt.id for rt in rtip.internaltip.receivertips]
    wfs = store.find(models.WhistleblowerFile, In(models.WhistleblowerFile.receivertip_id, rtips_ids))

    for wf in wfs:
        file_dict = models.serializers.serialize_wbfile(wf)
        file_dict['name'] = 'files_from_recipients/' + file_dict['name']
        export_dict['files'].append(copy.deepcopy(file_dict))

    return export_dict


class ZipStreamProducer(object):
    """ Streaming producter for ZipStream

    @ivar handler: The L{IRequest} to write the contents of the file to.
    @ivar fileObject: The file the contents of which to write to the request.
    """
    bufferSize = GLSettings.file_chunk_size

    def __init__(self, handler, zipstreamObject):
        """
        Initialize the instance.
        """
        self.handler = handler
        self.zipstreamObject = zipstreamObject

    def start(self):
        self.handler.request.connection.transport.registerProducer(self, False)

    def resumeProducing(self):
        try:
            if not self.handler:
                return

            data = self.zip_chunk()
            if data:
                self.handler.write(data)
                self.handler.flush()
            else:
                self.handler.request.connection.transport.unregisterProducer()
                self.handler.finish()
                self.stopProducing()
        except:
            self.handler.finish()
            raise

    def stopProducing(self):
        self.handler = None

    def zip_chunk(self):
        chunk = []
        chunk_size = 0

        for data in self.zipstreamObject:
            if len(data):
                chunk_size += len(data)
                chunk.append(data)
                if chunk_size >= GLSettings.file_chunk_size:
                    return ''.join(chunk)

        return ''.join(chunk)


class ExportHandler(BaseHandler):
    handler_exec_time_threshold = 3600

    @BaseHandler.transport_security_check('receiver')
    @BaseHandler.authenticated('receiver')
    @inlineCallbacks
    @asynchronous
    def get(self, rtip_id):
        tip_export = yield get_tip_export(self.current_tenant, self.current_user.user_id, rtip_id, self.request.language)

        self.set_header('X-Download-Options', 'noopen')
        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=\"%s.zip\"' % tip_export['tip']['sequence_number'])

        self.zip_stream = iter(ZipStream(tip_export['files']))

        ZipStreamProducer(self, self.zip_stream).start()
