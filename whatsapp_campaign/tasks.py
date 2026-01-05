import json
import os
from typing import Dict, List

import requests
from celery import shared_task
from dotenv import load_dotenv
from openai import OpenAI
from twilio.rest import Client

from phone_number.models import TwilioSubAccount

from .models import WhatsAppCampaignConfig, WhatsAppCampaignReport

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def fetch_contacts_from_jobadder(
    platform_base_url: str,
    access_token: str,
    contact_ids: List[str] = None,
    fetch_all: bool = False,
) -> List[Dict]:
    contacts = []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        if fetch_all:
            next_url = f"{platform_base_url}/contacts"

            while next_url:
                print(f"Fetching contacts from: {next_url}")
                response = requests.get(next_url, headers=headers, timeout=30)

                if response.status_code == 401:
                    print("Token expired, need to refresh")
                    return contacts

                response.raise_for_status()
                data = response.json()
                for contact in data.get("items", []):
                    phone = contact.get("phone")
                    if phone:
                        contact_data = {
                            "contact_id": contact.get("contactId"),
                            "name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                            "email": contact.get("email", ""),
                            "phone": "+8801537468323",
                            "company": contact.get("company", ""),
                        }
                        contacts.append(contact_data)
                        break
                links = data.get("links", {})
                next_url = links.get("next")

                print(
                    f"Fetched {len(data.get('items', []))} contacts, total so far: {len(contacts)}"
                )

                if not next_url:
                    break

        else:
            for contact_id in contact_ids:
                try:
                    contact_url = f"{platform_base_url}/contacts/{contact_id}"
                    response = requests.get(contact_url, headers=headers, timeout=30)

                    if response.status_code == 401:
                        print(f"Token expired while fetching contact {contact_id}")
                        continue

                    response.raise_for_status()
                    contact = response.json()

                    phone = contact.get("phone")
                    if phone:
                        contact_data = {
                            "contact_id": contact.get("contactId"),
                            "name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                            "email": contact.get("email", ""),
                            "phone": "+8801537468323",
                            "company": contact.get("company", ""),
                        }
                        contacts.append(contact_data)

                except Exception as e:
                    print(f"Error fetching contact {contact_id}: {str(e)}")
                    continue

        print(f"Total contacts fetched: {len(contacts)}")
        return contacts

    except Exception as e:
        print(f"Error fetching contacts from JobAdder: {str(e)}")
        return contacts


def send_campaign_whatsapp_message(
    to_number: str,
    from_number: str,
    content_sid: str,
    content_variables: dict,
    organization_id: int,
) -> tuple[bool, str, str]:
    try:
        twillio_sub_account = TwilioSubAccount.objects.get(
            organization_id=organization_id
        )
        account_sid = twillio_sub_account.twilio_account_sid
        auth_token = twillio_sub_account.twilio_auth_token

        twilio_client = Client(account_sid, auth_token)
        whatsapp_from = f"whatsapp:{from_number}"
        whatsapp_to = f"whatsapp:{to_number}"
        content_vars_json = json.dumps(content_variables)

        print(f"Sending campaign message to {to_number}")
        print(f"ContentSid: {content_sid}")
        print(f"ContentVariables: {content_vars_json}")
        message_obj = twilio_client.messages.create(
            from_=whatsapp_from,
            to=whatsapp_to,
            content_sid=content_sid,
            content_variables=content_vars_json,
        )

        print(f"Campaign message sent successfully: {message_obj.sid}")
        return True, message_obj.sid, ""

    except Exception as e:
        error_msg = str(e)
        print(f"Error sending campaign WhatsApp message: {error_msg}")
        return False, "", error_msg


def generate_campaign_ai_instructions(
    campaign_title: str,
    chatbot_template: str,
    custom_instructions: str = "",
) -> str:
    base_instructions = f"""You are an AI assistant for a WhatsApp campaign: "{campaign_title}"

Keep your responses:
- Conversational and friendly
- Professional and helpful
- Under 300 characters
- In a natural WhatsApp tone

"""

    if chatbot_template == "ai_call":
        base_instructions += """## Your Role
You're here to engage with contacts who respond to our campaign message.

## Guidelines
- Answer questions about the campaign naturally
- Keep responses brief and to the point
- Be helpful and informative
- If asked about something you don't know, politely say so
- Maintain a friendly, professional tone
- Use emojis sparingly (✅ 👍 are fine)

"""

    if custom_instructions:
        base_instructions += f"\n## Custom Instructions\n{custom_instructions}\n"

    return base_instructions


@shared_task
def send_campaign_message_to_contact(
    campaign_id: int,
    contact_data: dict,
):
    try:
        campaign = WhatsAppCampaignConfig.objects.get(id=campaign_id)
        phone = contact_data.get("phone", "")
        if phone and not phone.startswith("+"):
            phone = f"+{phone}"
        phone = phone.replace(" ", "").replace("-", "")
        report = WhatsAppCampaignReport.objects.create(
            campaign=campaign,
            contact_id=contact_data.get("contact_id"),
            contact_name=contact_data.get("name", ""),
            contact_email=contact_data.get("email", ""),
            contact_phone=phone,
            message_status="sending",
        )
        content_variables = campaign.get_content_variables_dict()
        success, message_sid, error_message = send_campaign_whatsapp_message(
            to_number=phone,
            from_number=str(campaign.from_phone_number),
            content_sid=campaign.twilio_content_sid,
            content_variables=content_variables,
            organization_id=campaign.organization_id,
        )

        if success:
            report.message_sid = message_sid
            report.update_status("sent")
            campaign.increment_sent()
            report.start_ai_conversation()

            print(f"Campaign message sent to {contact_data.get('name')} ({phone})")
        else:
            report.update_status("failed", error_message=error_message)
            campaign.increment_failed()

            print(f"Failed to send campaign message to {phone}: {error_message}")

    except WhatsAppCampaignConfig.DoesNotExist:
        print(f"Campaign {campaign_id} not found")
    except Exception as e:
        print(f"Error sending campaign message to contact: {str(e)}")


@shared_task
def process_campaign(campaign_id: int):
    try:
        campaign = WhatsAppCampaignConfig.objects.get(id=campaign_id)
        campaign.mark_as_sending()
        access_token = campaign.platform.access_token
        if not access_token:
            print(f"No access token for campaign {campaign_id}")
            campaign.mark_as_failed()
            return
        if campaign.contact_filter_type == "all":
            contacts = fetch_contacts_from_jobadder(
                platform_base_url=campaign.platform.base_url,
                access_token=access_token,
                fetch_all=True,
            )
        else:
            contacts = fetch_contacts_from_jobadder(
                platform_base_url=campaign.platform.base_url,
                access_token=access_token,
                contact_ids=campaign.selected_contact_ids,
                fetch_all=False,
            )

        if not contacts:
            print(f"No contacts found for campaign {campaign_id}")
            campaign.mark_as_failed()
            return
        campaign.total_contacts = len(contacts)
        campaign.save(update_fields=["total_contacts", "updated_at"])

        ai_instructions = generate_campaign_ai_instructions(
            campaign_title=campaign.campaign_title,
            chatbot_template=campaign.chatbot_template,
            custom_instructions=campaign.ai_instructions,
        )
        campaign.ai_instructions = ai_instructions
        campaign.save(update_fields=["ai_instructions", "updated_at"])

        print(f"Processing campaign {campaign_id} with {len(contacts)} contacts")
        for i, contact in enumerate(contacts):
            countdown = i * 10

            send_campaign_message_to_contact.apply_async(
                kwargs={
                    "campaign_id": campaign_id,
                    "contact_data": contact,
                },
                countdown=countdown,
            )
        campaign.mark_as_completed()

        print(f"Campaign {campaign_id} processed: {len(contacts)} messages queued")

    except WhatsAppCampaignConfig.DoesNotExist:
        print(f"Campaign {campaign_id} not found")
    except Exception as e:
        print(f"Error processing campaign {campaign_id}: {str(e)}")
        try:
            campaign = WhatsAppCampaignConfig.objects.get(id=campaign_id)
            campaign.mark_as_failed()
        except:
            pass


@shared_task
def process_campaign_response(
    contact_phone: str,
    contact_message: str,
):
    try:
        report = (
            WhatsAppCampaignReport.objects.filter(
                contact_phone=contact_phone,
                ai_conversation_active=True,
            )
            .select_related("campaign")
            .order_by("-created_at")
            .first()
        )

        if not report:
            print(f"No active campaign conversation found for {contact_phone}")
            return

        campaign = report.campaign
        report.add_message_to_conversation("contact", contact_message)
        ai_message = get_campaign_ai_response(
            conversation_history=report.conversation_json,
            ai_instructions=campaign.ai_instructions,
            contact_message=contact_message,
        )
        report.add_message_to_conversation("ai", ai_message)
        send_campaign_follow_up_message(
            to_number=contact_phone,
            from_number=str(campaign.from_phone_number),
            message=ai_message,
            organization_id=campaign.organization_id,
        )

        print(f"Processed campaign response from {contact_phone}")

    except Exception as e:
        print(f"Error processing campaign response: {str(e)}")


def get_campaign_ai_response(
    conversation_history: List[Dict],
    ai_instructions: str,
    contact_message: str,
) -> str:
    try:
        messages = [{"role": "system", "content": ai_instructions}]
        for msg in conversation_history:
            role = "assistant" if msg.get("sender") == "ai" else "user"
            messages.append({"role": role, "content": msg.get("message", "")})
        if (
            not conversation_history
            or conversation_history[-1].get("message") != contact_message
        ):
            messages.append({"role": "user", "content": contact_message})
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.7,
        )

        ai_message = response.choices[0].message.content.strip()
        return ai_message

    except Exception as e:
        print(f"Error getting campaign AI response: {str(e)}")
        return "Thanks for your message! We'll get back to you soon. 👍"


def send_campaign_follow_up_message(
    to_number: str,
    from_number: str,
    message: str,
    organization_id: int,
) -> bool:
    try:
        twillio_sub_account = TwilioSubAccount.objects.get(
            organization_id=organization_id
        )
        account_sid = twillio_sub_account.twilio_account_sid
        auth_token = twillio_sub_account.twilio_auth_token

        twilio_client = Client(account_sid, auth_token)

        whatsapp_from = f"whatsapp:{from_number}"
        whatsapp_to = f"whatsapp:{to_number}"

        message_obj = twilio_client.messages.create(
            body=message,
            from_=whatsapp_from,
            to=whatsapp_to,
        )

        print(f"Campaign follow-up message sent: {message_obj.sid}")
        return True

    except Exception as e:
        print(f"Error sending campaign follow-up message: {str(e)}")
        return False


@shared_task
def check_scheduled_campaigns():
    from django.utils import timezone

    try:
        now = timezone.now()
        campaigns = WhatsAppCampaignConfig.objects.filter(
            status="scheduled",
            schedule_type="scheduled",
            scheduled_at__lte=now,
        )

        for campaign in campaigns:
            print(f"Processing scheduled campaign: {campaign.campaign_title}")
            process_campaign.delay(campaign.id)

    except Exception as e:
        print(f"Error checking scheduled campaigns: {str(e)}")


@shared_task
def update_campaign_message_status(
    message_sid: str,
    status: str,
    error_code: str = None,
    error_message: str = None,
):
    try:
        report = WhatsAppCampaignReport.objects.get(message_sid=message_sid)
        report.update_status(status, error_code, error_message)

        print(f"Updated campaign message {message_sid} status to {status}")

    except WhatsAppCampaignReport.DoesNotExist:
        print(f"No campaign report found for message SID {message_sid}")
    except Exception as e:
        print(f"Error updating campaign message status: {str(e)}")
