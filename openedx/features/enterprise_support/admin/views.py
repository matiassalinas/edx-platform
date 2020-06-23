from django.views.generic import View
from django.contrib import admin, messages
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from openedx.features.enterprise_support.admin.forms import CSVImportForm
from student.models import CourseEnrollment, CourseEnrollmentAttribute
from django.views.generic.edit import FormView

from enterprise.admin.utils import validate_csv
from enterprise.models import EnterpriseCourseEnrollment

from django.core.exceptions import ValidationError


class EnrollmentAttributeOverrideView(FormView):
    """
    Learner Enrollment Attribute Override View.
    """
    template_name = 'enterprise_support/admin/enrollment_attributes_override.html'
    form_class = CSVImportForm

    @staticmethod
    def _get_admin_context(request):
        admin_context = {'opts': EnterpriseCourseEnrollment._meta}
        return admin_context

    def get_success_url(self):
        return reverse('admin:enterprise_override_attributes')

    def get_context_data(self, **kwargs):
        context = super(EnrollmentAttributeOverrideView, self).get_context_data(**kwargs)
        context.update(self._get_admin_context(self.request))
        return context

    def form_valid(self, form):
        total_records = 0
        error_line_numbers = []
        csv_reader = form.cleaned_data['csv_file']
        for index, record in enumerate(csv_reader):
            total_records += 1
            try:
                course_enrollment = CourseEnrollment.objects.get(
                    user_id=record['lms_user_id'],
                    course_id=record['course_id'],
                )
            except CourseEnrollment.DoesNotExist:
                error_line_numbers.append(str(index + 1))
            else:
                CourseEnrollmentAttribute.objects.update_or_create(
                    enrollment=course_enrollment,
                    namespace='salesforce',
                    name='opportunity_id',
                    defaults={
                        'value': record['opportunity_id'],
                    }
                )

        # if for some reason not a single enrollment updated than do not show success message.
        if len(error_line_numbers) != total_records:
            messages.success(self.request, 'Successfully updated learner enrollment opportunity ids.')

        if error_line_numbers:
            messages.error(
                self.request,
                _(
                    'Enrollment attributes were not updated for records at following line numbers '
                    'in csv because no enrollment found for these records: {error_line_numbers}'
                ).format(error_line_numbers=', '.join(error_line_numbers))
            )

        return super(EnrollmentAttributeOverrideView, self).form_valid(form)
