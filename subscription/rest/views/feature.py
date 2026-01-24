from rest_framework.generics import ListAPIView

from subscription.models import Feature
from subscription.rest.serializers.feature import FeatureSerializer
from django_filters.rest_framework import DjangoFilterBackend


class FeatureListView(ListAPIView):
    queryset = Feature.objects.filter()
    serializer_class = FeatureSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category_id"]
