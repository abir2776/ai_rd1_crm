from rest_framework.generics import ListAPIView

from cv_formatter.models import FormattedCV
from cv_formatter.rest.serializers.reports import ReportsSerializer


class RepostListAPIView(ListAPIView):
    serializer_class = ReportsSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return FormattedCV.objects.filter(organization=organization)
