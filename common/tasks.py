from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


@shared_task
def send_email_task(
    subject,
    recipient,
    template_name,
    context,
    customer_email=None,
    reply_to=None,
):
    html_content = render_to_string(template_name, context)
    if customer_email:
        from_email = f'"{customer_email}" <no-reply@rd1.co.uk>'
    else:
        from_email = "no-reply@rd1.co.uk"
    reply_to_address = reply_to if reply_to else customer_email
    reply_to_list = [reply_to_address] if reply_to_address else None
    email = EmailMultiAlternatives(
        subject=subject,
        body="Please view this email in an HTML-compatible email client.",
        from_email=from_email,
        to=[recipient],
        reply_to=reply_to_list,
    )

    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
        print(f"Email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient}: {str(e)}")
        raise
