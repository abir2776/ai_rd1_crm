import json
import os
from datetime import datetime, timedelta

import pytz
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import OpenAI
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_calendar_service():
    """Initialize Google Calendar service with service account"""
    try:
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_json:
            raise Exception("Service account credentials not configured")

        creds_data = json.loads(creds_json)

        credentials = service_account.Credentials.from_service_account_info(
            creds_data, scopes=["https://www.googleapis.com/auth/calendar"]
        )

        service = build("calendar", "v3", credentials=credentials)
        return service
    except Exception as e:
        raise Exception(f"Failed to initialize Google Calendar: {str(e)}")


def get_busy_times(service, days_ahead=7):
    """
    Get busy times from Google Calendar using freebusy query
    """
    try:
        # Define time range
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        body = {"timeMin": time_min, "timeMax": time_max, "items": [{"id": "primary"}]}

        events_result = service.freebusy().query(body=body).execute()
        busy_times = events_result["calendars"]["primary"]["busy"]

        return busy_times
    except Exception as e:
        print(f"Error fetching busy times: {str(e)}")
        return []


def get_available_slots(days_ahead=7, slot_duration_minutes=60):
    """
    Get available time slots from Google Calendar
    Checks actual calendar availability and returns free slots
    """
    try:
        service = get_calendar_service()
        busy_times = get_busy_times(service, days_ahead)

        # Convert busy times to datetime objects
        busy_periods = []
        for busy in busy_times:
            start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
            busy_periods.append((start, end))

        # Define working hours (customize as needed)
        WORK_START_HOUR = 9  # 9 AM
        WORK_END_HOUR = 17  # 5 PM

        available_slots = []
        start_date = datetime.now(pytz.UTC) + timedelta(
            hours=1
        )  # Start from 1 hour from now

        # Generate slots for the next N days
        for day_offset in range(days_ahead):
            current_day = start_date + timedelta(days=day_offset)

            # Skip weekends
            if current_day.weekday() >= 5:
                continue

            # Set to start of working hours
            slot_time = current_day.replace(
                hour=WORK_START_HOUR, minute=0, second=0, microsecond=0
            )

            # Generate slots throughout the day
            while slot_time.hour < WORK_END_HOUR:
                slot_end = slot_time + timedelta(minutes=slot_duration_minutes)

                # Check if this slot is free (not overlapping with busy times)
                is_free = True
                for busy_start, busy_end in busy_periods:
                    # Check for any overlap
                    if slot_time < busy_end and slot_end > busy_start:
                        is_free = False
                        break

                # Add slot if it's free and in the future
                if is_free and slot_time > datetime.now(pytz.UTC):
                    available_slots.append(
                        {
                            "datetime": slot_time.isoformat(),
                            "display": slot_time.strftime("%A, %B %d, %Y at %I:%M %p"),
                            "date": slot_time.strftime("%Y-%m-%d"),
                            "time": slot_time.strftime("%I:%M %p"),
                        }
                    )

                # Move to next slot (30-minute intervals)
                slot_time += timedelta(minutes=30)

                # Stop if we have enough slots
                if len(available_slots) >= 15:
                    break

            if len(available_slots) >= 15:
                break

        return available_slots[:15]  # Return first 15 available slots

    except Exception as e:
        print(f"Error getting available slots: {str(e)}")
        # Return fallback slots if calendar access fails
        return get_fallback_slots(days_ahead)


def get_fallback_slots(days_ahead=7):
    """
    Fallback slots if Google Calendar is not accessible
    """
    slots = []
    start_date = datetime.now(pytz.UTC) + timedelta(days=1)

    for i in range(days_ahead):
        date = start_date + timedelta(days=i)
        if date.weekday() < 5:  # Monday to Friday
            for hour in [10, 14, 16]:
                slot_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slots.append(
                    {
                        "datetime": slot_time.isoformat(),
                        "display": slot_time.strftime("%A, %B %d, %Y at %I:%M %p"),
                        "date": slot_time.strftime("%Y-%m-%d"),
                        "time": slot_time.strftime("%I:%M %p"),
                    }
                )

    return slots[:10]


def create_calendar_event(summary, description, start_time, end_time, attendee_email):
    """
    Create a Google Calendar event
    """
    try:
        service = get_calendar_service()

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC",
            },
            "attendees": [{"email": attendee_email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meeting-{datetime.now().timestamp()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 30},
                ],
            },
        }

        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all",  # Send email notifications
            )
            .execute()
        )

        return {
            "success": True,
            "event_link": event.get("htmlLink"),
            "meeting_link": event.get("hangoutLink"),
            "event_id": event.get("id"),
            "message": "Meeting scheduled successfully!",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to schedule meeting. Please try again.",
        }


# Function calling definitions for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_available_meeting_slots",
            "description": "Get available time slots from Google Calendar for scheduling a meeting. This checks real calendar availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 7)",
                        "default": 7,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_meeting",
            "description": "Schedule a meeting with a user on Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_email": {
                        "type": "string",
                        "description": "The email address of the user",
                    },
                    "user_name": {
                        "type": "string",
                        "description": "The name of the user",
                    },
                    "meeting_datetime": {
                        "type": "string",
                        "description": "The ISO datetime string for the meeting start time",
                    },
                    "user_interest": {
                        "type": "string",
                        "description": "What the user is interested in discussing",
                    },
                },
                "required": ["user_email", "user_name", "meeting_datetime"],
            },
        },
    },
]


class AIRecruiterChatView(APIView):
    permission_classes = [AllowAny]

    def handle_function_call(self, function_name, arguments):
        """Handle function calls from OpenAI"""
        if function_name == "get_available_meeting_slots":
            days_ahead = arguments.get("days_ahead", 7)
            slots = get_available_slots(days_ahead)

            if not slots:
                return {
                    "available_slots": [],
                    "message": "No available slots found. Please contact us directly.",
                }

            return {
                "available_slots": slots,
                "message": f"Found {len(slots)} available time slots from Google Calendar",
            }

        elif function_name == "schedule_meeting":
            user_email = arguments.get("user_email")
            user_name = arguments.get("user_name")
            meeting_datetime = arguments.get("meeting_datetime")
            user_interest = arguments.get("user_interest", "Product Demo")

            # Calculate end time (1 hour meeting)
            start_dt = datetime.fromisoformat(meeting_datetime.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(hours=1)

            # Create calendar event
            result = create_calendar_event(
                summary=f"Meeting with {user_name} - {user_interest}",
                description=f"Meeting scheduled with {user_name} ({user_email}) to discuss: {user_interest}\n\nScheduled via RecruiterAI platform.",
                start_time=start_dt.isoformat(),
                end_time=end_dt.isoformat(),
                attendee_email=user_email,
            )

            return result

        return {"error": "Unknown function"}

    def post(self, request):
        try:
            messages = request.data.get("messages", [])

            if not messages or not isinstance(messages, list):
                return Response(
                    {"error": "messages must be a list of message objects"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            system_instruction = (
                "You are RecruiterAI — a professional assistant for a recruitment automation platform. "
                "You understand and explain tools like AI WhatsApp Recruiter, AI Phone Call Recruiter, "
                "AI CV Formatter, AI GDPR Compliance, and AWR Compliance. "
                "You always respond clearly, concisely, and professionally, staying focused on recruitment automation. "
                "Never make up new features. Continue conversations naturally using context from prior messages.\n\n"
                "MEETING SCHEDULING:\n"
                "- When a user expresses interest in our products/services or wants to schedule a meeting, "
                "offer to show them available time slots from our Google Calendar.\n"
                "- Before scheduling, ALWAYS collect: user's full name and email address.\n"
                "- Use the get_available_meeting_slots function to fetch real-time available slots from Google Calendar.\n"
                "- Present the available slots in a clear, organized manner.\n"
                "- Once the user selects a time slot and provides their details, use the schedule_meeting function.\n"
                "- After successful scheduling, confirm the meeting details and inform them they'll receive a "
                "calendar invite via email with a Google Meet link.\n"
                "- Be friendly, professional, and helpful throughout the scheduling process.\n"
                "- If no slots are available, politely suggest alternative contact methods."
            )

            full_messages = [
                {"role": "system", "content": system_instruction}
            ] + messages

            # Initial API call with function calling
            completion = client.chat.completions.create(
                model="gpt-4o", messages=full_messages, tools=tools, tool_choice="auto"
            )

            response_message = completion.choices[0].message
            tool_calls = response_message.tool_calls

            # Handle function calls if any
            if tool_calls:
                # Add assistant's response to messages
                full_messages.append(response_message)

                # Process each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the function
                    function_response = self.handle_function_call(
                        function_name, function_args
                    )

                    # Add function response to messages
                    full_messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_response),
                        }
                    )

                # Get final response from OpenAI
                second_completion = client.chat.completions.create(
                    model="gpt-4o", messages=full_messages
                )

                final_message = second_completion.choices[0].message.content

                return Response(
                    {"reply": final_message or "No response generated."},
                    status=status.HTTP_200_OK,
                )

            # No function call needed, return direct response
            ai_message = response_message.content

            return Response(
                {"reply": ai_message or "No response generated."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
