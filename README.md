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
* Campaign statistics dashboard
* Training completion certificates
* Additional email templates
* User groups and campaign scheduling
* Persistent cloud database support

---

## Author

Juan Marco Saca

Cybersecurity Course Project
University of Texas at Brownsville
