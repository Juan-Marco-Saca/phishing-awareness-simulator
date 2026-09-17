import os
import hashlib
from html import escape
import smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")


from scenarios import SCENARIOS, email_html

TEMPLATES = {key: {'subject': value['subject'], 'body': email_html(value)} for key, value in SCENARIOS.items()}
TEMPLATE_SENDERS = {key: value['brand'] for key, value in SCENARIOS.items()}


def template_version(template_name):
    template = TEMPLATES[template_name]
    return hashlib.sha256((template['subject'] + template['body']).encode()).hexdigest()[:12]


def send_simulation_email(target_email, template_name, token):
    if not SENDER_EMAIL or not APP_PASSWORD:
        raise ValueError("Missing SENDER_EMAIL or APP_PASSWORD environment variables.")

    template = TEMPLATES.get(template_name)
    sender_name = TEMPLATE_SENDERS.get(template_name)

    if not template:
        raise ValueError("Invalid template selected.")

    link = f"{BASE_URL.rstrip('/')}/login?token={token}"

    subject = template["subject"]
    body = template["body"].format(link=escape(link, quote=True))
    pixel = f"{BASE_URL.rstrip('/')}/track?token={token}"
    body = body.replace('</body>', f'<img src="{escape(pixel, quote=True)}" width="1" height="1" alt=""></body>')

    message = MIMEMultipart()
    message["From"] = f"{sender_name}"
    message["To"] = target_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        refused = server.send_message(message, from_addr=SENDER_EMAIL, to_addrs=[target_email])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
