from rest_framework.generics import ListAPIView

from subscription.models import SubscriptionPlan

from ..serializers.plan import PlanFeatureSerializer


class PlanFeatureListView(ListAPIView):
    queryset = SubscriptionPlan.objects.filter()
    serializer_class = PlanFeatureSerializer
