# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from globaleaks.handlers import export
from globaleaks.jobs.delivery_sched import DeliverySchedule
from globaleaks.tests import helpers

class TestExportHandler(helpers.TestHandlerWithPopulatedDB):
    _handler = export.ExportHandler

    # All of the setup here is used by the templating that goes into the data.txt file.
    @inlineCallbacks
    def setUp(self):
        yield helpers.TestHandlerWithPopulatedDB.setUp(self)

        yield self.perform_full_submission_actions()
        # populates alarms conditions
        self.pollute_events(10)
        # creates the receiver files
        yield DeliverySchedule().run()

    @inlineCallbacks
    def test_export(self):
        rtips_desc = yield self.get_rtips()

        handler = self.request({}, role='receiver')
        handler.current_user.user_id = rtips_desc[0]['receiver_id']

        # As the handler calls internally the flush() we should
        # mock that function because during tests the flush could not
        # be called as the handler is not fully run.
        def flush_mock():
            pass

        handler.flush = flush_mock

        yield handler.get(rtips_desc[0]['id'])
