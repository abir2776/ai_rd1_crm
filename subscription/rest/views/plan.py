from rest_framework.generics import ListAPIView

from subscription.models import PlanFeature

from ..serializers.plan import PlanFeatureSerializer


class PlanFeatureListView(ListAPIView):
    serializer_class = PlanFeatureSerializer

    def get_queryset(self):
        uid = self.kwargs.get("feature_uid")
        return PlanFeature.objects.filter(feature__uid=uid)
