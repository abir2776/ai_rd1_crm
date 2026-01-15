from django.urls import path

from whatsapp_campaign.rest.views.list import jobadder_contacts_list

urlpatterns = [path("contacts", jobadder_contacts_list, name="job-adder-contact-list")]
