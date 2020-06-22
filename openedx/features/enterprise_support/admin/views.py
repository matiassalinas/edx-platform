from django.views.generic import View
from django.contrib import admin, messages
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from openedx.features.enterprise_support.admin.forms import CSVImportForm
from student.models import CourseEnrollment, CourseEnrollmentAttribute

from enterprise.admin.utils import parse_csv
from enterprise.models import EnterpriseCourseEnrollment


class EnrollmentAttributeOverrideView(View):
    """
    Learner Enrollment Attribute Override View.
    """
    template = 'enterprise_support/admin/enrollment_attributes_override.html'

    @staticmethod
    def _get_admin_context(request):
        admin_context = {'opts': EnterpriseCourseEnrollment._meta}
        admin_context.update(admin.site.each_context(request))

        return admin_context

    def get(self, request):
        """
        """
        context = {'csv_form': CSVImportForm()}
        context.update(self._get_admin_context(request))

        return render(request, self.template, context)

    def post(self, request):
        """
        """
        redirect_url = reverse('admin:enterprise_enterprisecourseenrollment_changelist')
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            messages.error(request, 'CSV file is required.')
            return HttpResponseRedirect(redirect_url)

        parsed_csv = parse_csv(csv_file, expected_columns=['user_id', 'course_id', 'opportunity_id'])

        error_line_numbers = []
        for index, record in enumerate(parsed_csv):
            try:
                course_enrollment = CourseEnrollment.objects.get(
                    user_id=record['user_id'],
                    course_id=record['course_id'],
                )
                CourseEnrollmentAttribute.objects.update_or_create(
                    enrollment=course_enrollment,
                    namespace='salesforce',
                    name='opportunity_id',
                    defaults={
                        'value': record['opportunity_id'],
                    }
                )
            except CourseEnrollment.DoesNotExist:
                error_line_numbers.append(str(index + 1))

        messages.error(
            request,
            _(
                'Enrollment attributes were not updated for some users '
                'because no enrollment found for records at line numbers: {error_line_numbers}'
            ).format(error_line_numbers=', '.join(error_line_numbers))
        )

        context = {'csv_form': CSVImportForm()}
        context.update(self._get_admin_context(request))
        return render(request, self.template, context)
