# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from globaleaks import models
from globaleaks.handlers.admin import modelimgs
from globaleaks.tests import helpers


class TestModelImgInstance(helpers.TestHandlerWithPopulatedDB):
    _handler = modelimgs.ModelImgInstance

    @inlineCallbacks
    def test_post(self):
        handler = self.request({}, role=self.user_role)

        yield handler.post('users', self.dummyReceiverUser_1['id'])

        img = yield modelimgs.get_model_img('users', self.dummyReceiverUser_1['id'])
        self.assertNotEqual(img, '')

    @inlineCallbacks
    def test_delete(self):
        handler = self.request({}, role=self.user_role)
        yield handler.delete('users', self.dummyReceiverUser_1['id'])

        img = yield modelimgs.get_model_img('users', self.dummyReceiverUser_1['id'])
        self.assertEqual(img, '')
