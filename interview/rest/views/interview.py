from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny

from interview.models import InterviewTaken
from interview.rest.serializers.interview import InterviewTakenSerializer


class InterviewTakenCreateView(CreateAPIView):
    queryset = InterviewTaken.objects.filter()
    serializer_class = InterviewTakenSerializer
    permission_classes = [AllowAny]


class InterviewTakenListView(ListAPIView):
    serializer_class = InterviewTakenSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        queryset = InterviewTaken.objects.filter(organization=organization)
        return queryset
