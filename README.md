# Phishing Awareness Simulator

## Overview

The Phishing Awareness Simulator is a Flask-based cybersecurity training platform designed to demonstrate how phishing campaigns work in a controlled educational environment. The application allows administrators to create simulated phishing campaigns, track user interactions, and provide cybersecurity awareness training after a user clicks a simulated phishing link.

This project was developed as part of a cybersecurity course to help users recognize phishing attempts and understand common social engineering techniques.

---

## Features

### Campaign Management

* Create phishing awareness campaigns
* Select from multiple email templates
* Send simulations to target email addresses
* Track campaign activity

### Email Templates

* Password Expiration Notice
* Parking Permit Update
* Package Delivery Notification
* Direct Deposit Verification
* OneDrive Storage Warning

### User Tracking

* Records when a user clicks a simulated phishing link
* Logs training completion events
* Displays activity through an administrator dashboard

### Awareness Training

* Interactive phishing awareness page
* Educational content about phishing attacks
* Security best practices
* Knowledge assessment quiz

---

## Technologies Used

* Python 3
* Flask
* SQLite
* HTML
* CSS
* Jinja2 Templates
* SMTP (Email Delivery)
* Render (Deployment)

---

## Project Structure

```text
Phishing Campaign/
│
├── app.py
├── database.py
├── email_sender.py
├── requirements.txt
├── .gitignore
│
├── templates/
│   ├── dashboard.html
│   ├── campaign.html
│   ├── landing.html
│   └── training.html
│
└── phishing_simulator.db
```

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/phishing-awareness-simulator.git
cd phishing-awareness-simulator
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file:

```env
SENDER_EMAIL=your_email@gmail.com
APP_PASSWORD=your_gmail_app_password
BASE_URL=http://127.0.0.1:5000
ADMIN_PASSWORD=replace-with-a-long-unique-password
COLLECT_REQUEST_DETAILS=true
```

### Run the Application

```bash
python app.py
```

The application will be available at:

```text
http://127.0.0.1:5000
```

---

## Educational Purpose

This project is intended solely for cybersecurity awareness training, education, and authorized demonstrations.

No passwords or sensitive credentials are collected. The simulator is designed to teach users how phishing attacks work and how to identify suspicious emails.

---

## Future Improvements

* PostgreSQL integration
* Training completion certificates
* Additional email templates
* User groups and campaign scheduling
* Persistent cloud database support

## Telemetry and reporting

### Verify tracking from the dashboard

To remove a campaign, open its participant detail page and expand **Delete
campaign**. Confirm the checkbox and choose **Delete campaign permanently**.
This removes the campaign, its participants and recorded events together, and
invalidates its tracking links. Other campaigns and legacy events are retained.
Already-sent emails are not recalled. Deletion requires administrator sign-in.

After restarting the server, open the dashboard and choose **Test tracking**.
It opens the participant flow in a new tab under a separate campaign named
**Tracking test (no email sent)**. Enter dummy text and submit, then return to the
dashboard. Activity updates every 10 seconds, or use **Refresh now**. This check
saves actual test events in the database and does not send an email.

The collection status cards show whether IP/device collection is enabled, the
number of browser events, and how many have an IP. Recent activity displays
field-filled indicators, elapsed time, scores and reporting channels in plain
language. Email-send and manually entered report events are explicitly marked
as having no participant browser request. A successful email send alone does
not generate a participant IP; a recipient must visit their tracked link.

The participant landing page now resembles a password-change screen. It records
`password_form_viewed`, `password_form_started` (first input), and
`password_change_submitted` (button activation). The dashboard counts unique
recipients at each step. Interaction metadata includes elapsed milliseconds since
page load and booleans indicating whether current/new/confirmation fields were
filled. Timing and field states are client-reported estimates; submission is not
proof of a valid password or an actual account change. Repeated visits count as
separate events but not additional unique participants.

Password text is never included in telemetry requests. Inputs have no form or
name attributes, and JavaScript clears them before recording submission. The
server rejects unexpected interaction fields instead of storing arbitrary data.
After submission the page reveals the simulation and links to training. Existing
IP/browser/device telemetry is attached to these events when
`COLLECT_REQUEST_DETAILS=true`. Local testing normally records `127.0.0.1`.

New campaigns record a campaign name, template and content-derived template version,
with a random tracking token for each recipient. Email addresses are kept in the
database for administration, but are no longer embedded in tracking links. Tokens
attribute activity to the intended recipient; forwarded links do not prove who visited.

The dashboard shows send attempts, SMTP acceptance/failure, estimated opens, link
requests, training views, quiz submissions, training completion, and phishing reports.
Expand an event's details to see quiz answers, score, missed question IDs and attempt
number, reporting channel, or send error type. No usernames, passwords or credential
form contents are collected. Quiz completion requires a server-graded score of 5/5;
completion is recorded once per recipient/campaign, while repeat attempts are retained.
The training preview grades answers without saving participant events.

Campaign summaries count unique recipients separately from raw click requests.
Click/report rates use SMTP-accepted recipients (not verified delivery). Completion
rate uses training viewers because this app does not assign training separately.
Average quiz score includes every attempt. Time to first report starts at campaign
creation. Historical events remain visible as legacy/unattributed and are excluded
from new campaign rates; missing historic data cannot be reconstructed.

To record a report received by email, phone, in person, or a mail client's reporting
button, use **Record a phishing report** on the dashboard. Choose the participant,
campaign and channel, and optionally enter the original report time in UTC. This is
manual administrator entry, not a mailbox integration. A report before any recorded
click counts as reporting before clicking, including participants who never clicked.

IP address, User-Agent (up to 512 characters), and estimated browser/OS/device are
enabled by default. Add `COLLECT_REQUEST_DETAILS=false` to `.env` to disable their
storage for future events. This does not delete previously recorded details or alter
hosting/access logs. IP comes from the direct connection, so behind a reverse proxy
it may be the proxy's address; untrusted forwarded headers are not used.
User-Agent automation hints remain available with details disabled. They are only
heuristics: unflagged requests are not confirmed human clicks.

Open tracking uses a 1-pixel image and is approximate: image blocking, caching and
automated fetching affect results. The app does not currently collect bounce or
confirmed-delivery notifications. SMTP send success means acceptance by the server.
Application logs report send failures, database failures and HTTP 5xx responses using
event context/error types, without logging submitted quiz bodies or credential values.

The SQLite schema is upgraded automatically on startup, preserving old events.
Back up `phishing_simulator.db` before deploying. Old email-address tracking links
are no longer accepted; send a new campaign to obtain token-based links.
`DATABASE_PATH` can select another database file (in `.env` or the process environment).
Run `python -m unittest discover -s tests -v` for isolated tests; SMTP is mocked and
tests do not send emails. Debug mode is off unless `FLASK_DEBUG=1` is set.

The administrator dashboard, campaign creation and manual report entry require HTTP
Basic authentication. Set a long unique `ADMIN_PASSWORD` in `.env`, restart the app,
and sign in with username `admin`. Administration stays disabled until it is set.
Participant links and the training preview do not require the administrator password.
Use HTTPS when deployed so the password and participant telemetry are encrypted in
transit. Cross-site browser submissions to administrative routes are rejected.

---

## Author

Juan Marco Saca

Cybersecurity Course Project
Tomas Bata University (Exchange program with St. Mary's University)
