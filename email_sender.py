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


TEMPLATES = {

    "password": {
        "subject": "Action Required: Account Password Expiring Soon",
        "body": """
<html>
<body style="font-family: Arial, sans-serif;">

<h2 style="color:#0078d4;">IT Help Desk</h2>

<p>Hello,</p>

<p>
Our system shows that your university account password is scheduled to expire soon.
</p>

<p>
To avoid interruption of email, Canvas, and campus services, please review your account status.
</p>

<p>
<a href="{link}"
style="
background:#0078d4;
color:white;
padding:12px 24px;
text-decoration:none;
border-radius:5px;
display:inline-block;">
Review Account Status
</a>
</p>

<p>
Thank you,<br>
IT Help Desk
</p>

</body>
</html>
"""
    },

    "parking": {
        "subject": "Parking Permit Update Required",
        "body": """
<html>
<body style="font-family: Arial, sans-serif;">

<h2 style="color:#0078d4;">Campus Parking Services</h2>

<p>Hello,</p>

<p>
Our records show that your parking permit information may be incomplete for the current semester.
</p>

<p>
Please review your account below.
</p>

<p>
<a href="{link}"
style="
background:#28a745;
color:white;
padding:12px 24px;
text-decoration:none;
border-radius:5px;
display:inline-block;">
Review Parking Account
</a>
</p>

<p>
Thank you,<br>
Campus Parking Services
</p>

</body>
</html>
"""
    },

    "package": {
        "subject": "Package Delivery Notice",
        "body": """
<html>
<body style="font-family: Arial, sans-serif;">

<h2 style="color:#0078d4;">Mail Services</h2>

<p>Hello,</p>

<p>
A package delivery attempt was made, but additional confirmation is needed before the item can be released.
</p>

<p>
<a href="{link}"
style="
background:#fd7e14;
color:white;
padding:12px 24px;
text-decoration:none;
border-radius:5px;
display:inline-block;">
View Delivery Notice
</a>
</p>

<p>
Thank you,<br>
Mail Services
</p>

</body>
</html>
"""
    },

    "payroll": {
        "subject": "Direct Deposit Verification Needed",
        "body": """
<html>
<body style="font-family: Arial, sans-serif;">

<h2 style="color:#0078d4;">Human Resources</h2>

<p>Hello,</p>

<p>
Your direct deposit information requires verification before the next processing period.
</p>

<p>
<a href="{link}"
style="
background:#6f42c1;
color:white;
padding:12px 24px;
text-decoration:none;
border-radius:5px;
display:inline-block;">
Review Payroll Profile
</a>
</p>

<p>
Thank you,<br>
Human Resources
</p>

</body>
</html>
"""
    },

    "storage": {
        "subject": "OneDrive Storage Limit Warning",
        "body": """
<html>
<body style="font-family: Arial, sans-serif;">

<h2 style="color:#0078d4;">Microsoft 365 Support</h2>

<p>Hello,</p>

<p>
Your OneDrive storage is approaching its allocated capacity.
</p>

<p>
Please review your current storage usage.
</p>

<p>
<a href="{link}"
style="
background:#0d6efd;
color:white;
padding:12px 24px;
text-decoration:none;
border-radius:5px;
display:inline-block;">
Review Storage Usage
</a>
</p>

<p>
Thank you,<br>
Microsoft 365 Support
</p>

</body>
</html>
"""
    }

}

TEMPLATE_SENDERS = {
    "password": "IT Help Desk",
    "parking": "Campus Parking Services",
    "package": "Mail Services",
    "payroll": "Human Resources",
    "storage": "Microsoft 365 Support"
}

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
