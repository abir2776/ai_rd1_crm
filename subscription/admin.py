from django.contrib import admin

from .models import Feature, PlanFeature, Subscription, SubscriptionPlan

admin.site.register(SubscriptionPlan)
admin.site.register(Subscription)
admin.site.register(Feature)
admin.site.register(PlanFeature)
