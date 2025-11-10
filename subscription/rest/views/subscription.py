from rest_framework.generics import ListCreateAPIView

from subscription.models import Subscription
from subscription.rest.serializers.subscription import SubscriptionSerializer


class SubscriptionListCreateView(ListCreateAPIView):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.get_organization()
        queryset = Subscription.objects.filter(organization=organization)
        return queryset
