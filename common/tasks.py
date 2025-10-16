from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


@shared_task
def send_email_task(subject, recipient, template_name, context):
    html_content = render_to_string(template_name, context)

    email = EmailMultiAlternatives(
        subject=subject,
        body="Please view this email in an HTML-compatible email client.",
        to=[recipient],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
