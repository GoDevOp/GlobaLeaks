# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from globaleaks.handlers.admin import files
from globaleaks.tests import helpers


class TestFileInstance(helpers.TestHandler):
    _handler = files.FileInstance

    @inlineCallbacks
    def test_post(self):
        handler = self.request({}, role=self.user_role)

        yield handler.post(u'logo')

    @inlineCallbacks
    def test_delete(self):
        handler = self.request({}, role=self.user_role)
        yield handler.delete(u'logo')
