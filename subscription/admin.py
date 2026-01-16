from django.contrib import admin

from .models import Category, Feature, PlanFeature, Subscription

admin.site.register(Subscription)
admin.site.register(Feature)
admin.site.register(PlanFeature)
admin.site.register(Category)
