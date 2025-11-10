from rest_framework.generics import ListAPIView

from subscription.models import Feature
from subscription.rest.serializers.feature import FeatureSerializer


class FeatureListView(ListAPIView):
    queryset = Feature.objects.filter()
    serializer_class = FeatureSerializer
