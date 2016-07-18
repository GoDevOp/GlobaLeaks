# -*- encoding: utf-8 -*-

from storm.locals import Int, Bool, Unicode, DateTime, JSON, ReferenceSet

from globaleaks.db.migrations.update import MigrationBase
from globaleaks.models import *

from globaleaks import __version__, DATABASE_VERSION

class Node_v_32(Model):
    __storm_table__ = 'node'
    version = Unicode(default=unicode(__version__))
    version_db = Unicode(default=unicode(DATABASE_VERSION))
    name = Unicode(validator=shorttext_v, default=u'')
    basic_auth = Bool(default=False)
    basic_auth_username = Unicode(default=u'')
    basic_auth_password = Unicode(default=u'')
    public_site = Unicode(validator=shorttext_v, default=u'')
    hidden_service = Unicode(validator=shorttext_v, default=u'')
    receipt_salt = Unicode(validator=shorttext_v)
    languages_enabled = JSON(default=LANGUAGES_SUPPORTED_CODES)
    default_language = Unicode(validator=shorttext_v, default=u'en')
    default_timezone = Int(default=0)
    default_password = Unicode(validator=longtext_v, default=u'globaleaks')
    description = JSON(validator=longlocal_v, default=empty_localization)
    presentation = JSON(validator=longlocal_v, default=empty_localization)
    footer = JSON(validator=longlocal_v, default=empty_localization)
    security_awareness_title = JSON(validator=longlocal_v, default=empty_localization)
    security_awareness_text = JSON(validator=longlocal_v, default=empty_localization)
    maximum_namesize = Int(default=128)
    maximum_textsize = Int(default=4096)
    maximum_filesize = Int(default=30)
    tor2web_admin = Bool(default=True)
    tor2web_custodian = Bool(default=True)
    tor2web_whistleblower = Bool(default=False)
    tor2web_receiver = Bool(default=True)
    tor2web_unauth = Bool(default=True)
    allow_unencrypted = Bool(default=False) # Changed to enforce_notification_encryption in Node_v_32
    disable_encryption_warnings = Bool(default=False)
    allow_iframes_inclusion = Bool(default=False)
    submission_minimum_delay = Int(default=10)
    submission_maximum_ttl = Int(default=10800)
    can_postpone_expiration = Bool(default=False)
    can_delete_submission = Bool(default=False)
    can_grant_permissions = Bool(default=False)
    ahmia = Bool(default=False)
    allow_indexing = Bool(default=False)
    wizard_done = Bool(default=False)

    disable_submissions = Bool(default=False)
    disable_privacy_badge = Bool(default=False)
    disable_security_awareness_badge = Bool(default=False)
    disable_security_awareness_questions = Bool(default=False)
    disable_key_code_hint = Bool(default=False)
    disable_donation_panel = Bool(default=False)

    enable_captcha = Bool(default=True)
    enable_proof_of_work = Bool(default=True)

    enable_experimental_features = Bool(default=False)

    whistleblowing_question = JSON(validator=longlocal_v, default=empty_localization)
    whistleblowing_button = JSON(validator=longlocal_v, default=empty_localization)
    whistleblowing_receipt_prompt = JSON(validator=longlocal_v, default=empty_localization)

    simplified_login = Bool(default=True)

    enable_custom_privacy_badge = Bool(default=False)
    custom_privacy_badge_tor = JSON(validator=longlocal_v, default=empty_localization)
    custom_privacy_badge_none = JSON(validator=longlocal_v, default=empty_localization)

    header_title_homepage = JSON(validator=longlocal_v, default=empty_localization)
    header_title_submissionpage = JSON(validator=longlocal_v, default=empty_localization)
    header_title_receiptpage = JSON(validator=longlocal_v, default=empty_localization)
    header_title_tippage = JSON(validator=longlocal_v, default=empty_localization)

    widget_comments_title = JSON(validator=shortlocal_v, default=empty_localization)
    widget_messages_title = JSON(validator=shortlocal_v, default=empty_localization)
    widget_files_title = JSON(validator=shortlocal_v, default=empty_localization)

    landing_page = Unicode(default=u'homepage')

    contexts_clarification = JSON(validator=longlocal_v, default=empty_localization)
    show_small_context_cards = Bool(default=False)
    show_contexts_in_alphabetical_order = Bool(default=False)

    threshold_free_disk_megabytes_high = Int(default=200)
    threshold_free_disk_megabytes_medium = Int(default=500)
    threshold_free_disk_megabytes_low = Int(default=1000)

    threshold_free_disk_percentage_high = Int(default=3)
    threshold_free_disk_percentage_medium = Int(default=5)
    threshold_free_disk_percentage_low = Int(default=10)

    context_selector_type = Unicode(validator=shorttext_v, default=u'list')

class MigrationScript(MigrationBase):
    def migrate_Node(self):
        old_node = self.store_old.find(self.model_from['Node']).one()
        new_node = self.model_to['Node']()

        for _, v in new_node._storm_columns.iteritems():

            if v.name == 'wbtip_timetolive':
                new_node.wbtip_timetolive = 90
                continue
            setattr(new_node, v.name, getattr(old_node, v.name))

        self.store_new.add(new_node)
