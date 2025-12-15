from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


@shared_task
def send_email_task(subject, recipient, template_name, context):
    html_content = render_to_string(template_name, context)
    from_email = f"{'osmangoni00255@gmail.com'} via AIRD1 <no-reply@rd1.co.uk>"

    email = EmailMultiAlternatives(
        subject=subject,
        body="Please view this email in an HTML-compatible email client.",
        from_email=from_email,
        to=[recipient],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
