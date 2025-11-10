from rest_framework.generics import ListAPIView

from subscription.models import SubscriptionPlan

from ..serializers.plan import SubscriptionPlanSerializer


class SubscriptionPlanListView(ListAPIView):
    queryset = SubscriptionPlan.objects.filter()
    serializer_class = SubscriptionPlanSerializer
