"""
Django admin command to send verification approved email to learners
"""

import datetime
import logging
import threading

from crum import set_current_request
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from verify_student.emails import send_verification_approved_email, send_verification_confirmation_email
from verify_student.toggles import use_new_templates_for_id_verification_emails

logger = logging.getLogger(__name__)

_thread_locals = threading.local()


class Command(BaseCommand):
    """
    This command sends email to learner for which the Software Secure Photo Verification has approved

    Example usage:
        $ ./manage.py lms send_verification_email_test --username=staff --method=approved
        OR
        $ ./manage.py lms send_verification_email_test --username=staff --method=submitted
    """
    help = 'Send email to specified user to test new templates'

    def __init__(self, *args, **kwargs):
        super(Command).__init__(*args, **kwargs)
        self.request = RequestFactory().request()

    def add_arguments(self, parser):
        parser.add_argument('--username', help="The learner's username.")
        parser.add_argument('--method', required=True, help="Choose email method. `approved` or `submitted`")

    def init_request(self):
        self.request.session = {}
        self.request.site = Site.objects.get_current()
        self.request.user = User.objects.get(username='staff')
        set_current_request(self.request)

    def handle(self, *args, **options):
        """
        Handler for the command

        It creates batches of expired Software Secure Photo Verification and sends it to send_verification_expiry_email
        that used edx_ace to send email to these learners
        """
        self.init_request()
        if not use_new_templates_for_id_verification_emails():
            logger.info('WaffleFlag is disabled. Falling back.')
            return

        method = options['method']
        username = options['username']
        user = User.objects.get(username=username)
        context = {'user': user}

        if method == 'approved':
            logger.info('1. Trying to send ID verification approved email to user: {}'.format(username))
            expiry_date = datetime.date.today() + datetime.timedelta(
                days=settings.VERIFY_STUDENT["DAYS_GOOD_FOR"]
            )
            context['expiry_date'] = expiry_date.strftime("%m/%d/%Y")
            email_was_successful = send_verification_approved_email(context)
            logger.info('2. Email sending to user: {}, success: {}'.format(username, email_was_successful))

        else:
            logger.info('1. Trying to send ID verification submission confirmation email to user: {}'.format(username))
            email_was_successful = send_verification_confirmation_email(context)
            logger.info('2. Email sending to user: {}, success: {}'.format(username, email_was_successful))
