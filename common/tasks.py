from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


@shared_task
def send_email_task(
    subject,
    recipient,
    template_name,
    context,
    customer_email="osmangoni00255@gmail.com",
):
    html_content = render_to_string(template_name, context)
    if customer_email:
        from_email = f'"{customer_email} via AIRD1" <no-reply@rd1.co.uk>'
    else:
        from_email = "AIRD1 <no-reply@rd1.co.uk>"

    email = EmailMultiAlternatives(
        subject=subject,
        body="Please view this email in an HTML-compatible email client.",
        from_email=from_email,
        to=[recipient],
        reply_to=[customer_email] if customer_email else None,
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
