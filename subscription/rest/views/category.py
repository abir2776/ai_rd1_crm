from rest_framework.generics import ListAPIView

from subscription.models import Category
from subscription.rest.serializers.category import CategorySerializer


class CategoryListView(ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.filter().order_by("-created_at")
