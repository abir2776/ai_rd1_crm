from rest_framework.generics import ListAPIView

from subscription.models import PlanFeature

from ..serializers.plan import PlanFeatureSerializer


class PlanFeatureListView(ListAPIView):
    queryset = PlanFeature.objects.filter()
    serializer_class = PlanFeatureSerializer
