"""
"""

import csv
import os
import tempfile

from django.test import TestCase
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from student.tests.factories import TEST_PASSWORD, AdminFactory, UserFactory

from django.test import Client
from django.urls import reverse

from openedx.features.enterprise_support.admin.forms import CSVImportForm
from student.tests.factories import CourseEnrollmentFactory
from openedx.core.djangoapps.catalog.tests.factories import CourseRunFactory
from student.models import CourseEnrollment, CourseEnrollmentAttribute


class EnrollmentAttributeOverrideViewTest(ModuleStoreTestCase):
    """
    Tests for course creator admin.
    """

    def setUp(self):
        """ Test case setup """
        super(EnrollmentAttributeOverrideViewTest, self).setUp()

        self.client = Client()
        user = AdminFactory()
        self.view_url = reverse('admin:enterprise_override_attributes')
        self.client.login(username=user.username, password=TEST_PASSWORD)

        self.users = []
        for _ in range(3):
            self.users.append(UserFactory())

        self.course = CourseRunFactory()
        self.course_id = self.course.get('key')
        self.csv_data = [
            [self.users[0].id, self.course_id, 'OP_4321'],
            [self.users[1].id, self.course_id, 'OP_8765'],
            [self.users[2].id, self.course_id, 'OP_2109'],
        ]
        self.csv_data_for_existing_attributes = [
            [self.users[0].id, self.course_id, 'OP_1234'],
            [self.users[1].id, self.course_id, 'OP_5678'],
            [self.users[2].id, self.course_id, 'OP_9012'],
        ]

        for user in self.users:
            CourseEnrollmentFactory(
                course_id=self.course_id,
                user=user
            )

    def create_csv(self, header=None, data=None):
        """Create csv"""
        header = header or ['user_id', 'course_id', 'opportunity_id']
        data = data or self.csv_data
        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')
        with open(tmp_csv_path, 'w') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(header)
            csv_writer.writerows(data)

        return tmp_csv_path

    def verify_enrollment_attributes(self, data=None):
        """
        Verify that data from csv is imported correctly and tables have correct data.
        """
        data = data or self.csv_data
        for user_id, course_id, opportunity_id in data:
            enrollment = CourseEnrollment.objects.get(user_id=user_id, course_id=course_id)
            enrollment_attribute = CourseEnrollmentAttribute.objects.get(
                enrollment=enrollment,
                namespace='salesforce',
                name='opportunity_id'
            )
            assert enrollment_attribute.value == opportunity_id

    def test_get(self):
        """
        Tests that HTTP GET is working as expected.
        """
        response = self.client.get(self.view_url)
        assert response.status_code == 200
        assert isinstance(response.context['csv_form'], CSVImportForm)

    def test_post(self):
        """
        Tests that HTTP POST is working as expected when creating new attributes and updating.
        """
        csv_path = self.create_csv()
        post_data = {'csv_file': open(csv_path)}
        response = self.client.post(self.view_url, data=post_data)
        assert response.status_code == 200
        self.verify_enrollment_attributes()
        assert isinstance(response.context['csv_form'], CSVImportForm)

        # override existing
        csv_path = self.create_csv(data=self.csv_data_for_existing_attributes)
        post_data = {'csv_file': open(csv_path)}
        response = self.client.post(self.view_url, data=post_data)
        assert response.status_code == 200
        self.verify_enrollment_attributes(data=self.csv_data_for_existing_attributes)
        assert isinstance(response.context['csv_form'], CSVImportForm)

    def test_post_with_no_csv(self):
        """
        Tests that HTTP POST without out csv file is working as expected.
        """
        response = self.client.post(self.view_url)
        assert response.status_code == 302
        assert response.url == '/admin/enterprise/enterprisecourseenrollment/'

    def test_post_with_incorrect_csv_header(self):
        """
        Tests that HTTP POST with incorrect csv header is working as expected.
        """
        csv_path = self.create_csv(header=['a', 'b'])
        post_data = {'csv_file': open(csv_path)}
        response = self.client.post(self.view_url, data=post_data)
        assert response.status_code == 200
        messages = []
        for msg in response.context['messages']:
            messages.append(str(msg))
        assert messages == [
            'Expected a CSV file with [user_id, course_id, opportunity_id] columns, but found [a, b] columns instead.'
        ]
        assert isinstance(response.context['csv_form'], CSVImportForm)

    def test_post_with_no_enrollment_error(self):
        """
        Tests that HTTP POST is working as expected when for some records there is no enrollment.
        """
        csv_data = self.csv_data + [[999, self.course_id, 'NOPE']]
        csv_path = self.create_csv(data=csv_data)
        post_data = {'csv_file': open(csv_path)}
        response = self.client.post(self.view_url, data=post_data)
        assert response.status_code == 200
        messages = []
        for msg in response.context['messages']:
            messages.append(str(msg))
        assert messages == [
            'Enrollment attributes were not updated for some users because no ' +
            'enrollment found for records at line numbers: 4'
        ]
        assert isinstance(response.context['csv_form'], CSVImportForm)
