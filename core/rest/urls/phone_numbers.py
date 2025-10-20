from django.urls import path
from ..views import phone_numbers

urlpatterns = [
    path(
        "/buy",
        phone_numbers.buy_phone_number,
        name="buy_phone_number",
    ),
    path(
        "/search",
        phone_numbers.search_phone_numbers,
        name="search_phone_numbers",
    ),
]
