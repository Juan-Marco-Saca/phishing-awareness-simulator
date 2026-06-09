from flask import Flask, render_template, request, redirect, url_for
from database import init_db, log_event, get_results
from email_sender import send_simulation_email

app = Flask(__name__)

init_db()


@app.route("/")
def dashboard():
    results = get_results()
    return render_template("dashboard.html", results=results)


@app.route("/campaign", methods=["GET", "POST"])
def campaign():
    if request.method == "POST":
        template = request.form.get("template")
        targets_raw = request.form.get("targets")

        targets = [
            email.strip()
            for email in targets_raw.splitlines()
            if email.strip()
        ]

        for email in targets:
            send_simulation_email(email, template)

        return redirect(url_for("dashboard"))

    return render_template("campaign.html")


@app.route("/track")
def track_open():
    email = request.args.get("email", "unknown")
    log_event(email, "email_opened")
    return "", 204


@app.route("/login")
def fake_login():
    email = request.args.get("email", "unknown")
    log_event(email, "clicked_link")
    return render_template("landing.html", email=email)


@app.route("/training")
def training():
    email = request.args.get("email", "unknown")
    log_event(email, "viewed_training")
    return render_template("training.html", email=email)


if __name__ == "__main__":
    app.run(debug=True)