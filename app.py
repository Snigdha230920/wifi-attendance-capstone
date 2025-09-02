import csv
import io
import os
import random
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session as flask_session, send_file
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, Student, Admin, Session as AttnSession, Attendance, init_db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

db.init_app(app)
with app.app_context():
    init_db()


# -----------------------
# Helpers
# -----------------------
def admin_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not flask_session.get("admin_user"):
            flash("Please log in as admin to continue.", "warning")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return wrapper


def get_active_session():
    return AttnSession.query.filter_by(active=True).order_by(AttnSession.start_time.desc()).first()


# -----------------------
# Student Panel
# -----------------------
@app.route("/", methods=["GET", "POST"])
def student_portal():
    active_session = get_active_session()
    message = None
    status = None  # "success" | "warning" | "danger"

    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip().upper()
        code = request.form.get("secret_code", "").strip()

        if not active_session or not active_session.active:
            message = "No active attendance session right now."
            status = "warning"
        elif code != active_session.secret_code:
            message = "Invalid secret code. Please try again."
            status = "danger"
        else:
            student = Student.query.filter_by(roll_no=roll_no).first()
            if not student:
                message = "Unregistered student. Contact your faculty."
                status = "danger"
            else:
                already = Attendance.query.filter_by(session_id=active_session.id, student_id=student.id).first()
                if already:
                    message = f"Hi {student.name}, your attendance is already recorded."
                    status = "info"
                else:
                    rec = Attendance(session_id=active_session.id, student_id=student.id, timestamp=datetime.utcnow())
                    db.session.add(rec)
                    db.session.commit()
                    message = f"Thanks {student.name}! Your attendance is recorded."
                    status = "success"

    return render_template("student.html", active_session=active_session, message=message, status=status)


# -----------------------
# Admin Panel (login + dashboard)
# -----------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    # Handle login inline (when not authenticated)
    if request.method == "POST" and request.form.get("form_type") == "login":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            flask_session["admin_user"] = username
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "danger")

    # Handle start session
    if request.method == "POST" and request.form.get("form_type") == "start_session":
        if not flask_session.get("admin_user"):
            flash("Please log in first.", "warning")
            return redirect(url_for("admin_dashboard"))
        active = get_active_session()
        if active:
            flash("A session is already active. Stop it before starting a new one.", "warning")
        else:
            secret = f"{random.randint(100000, 999999)}"
            new_sess = AttnSession(secret_code=secret, active=True, start_time=datetime.utcnow())
            db.session.add(new_sess)
            db.session.commit()
            flash(f"Session started. Secret code: {secret}", "success")
        return redirect(url_for("admin_dashboard"))

    # Handle stop session
    if request.method == "POST" and request.form.get("form_type") == "stop_session":
        if not flask_session.get("admin_user"):
            flash("Please log in first.", "warning")
            return redirect(url_for("admin_dashboard"))
        active = get_active_session()
        if not active:
            flash("No active session to stop.", "info")
        else:
            active.active = False
            active.end_time = datetime.utcnow()
            db.session.commit()
            flash("Session stopped.", "success")
        return redirect(url_for("admin_dashboard"))

    # Handle password change
    if request.method == "POST" and request.form.get("form_type") == "change_password":
        if not flask_session.get("admin_user"):
            flash("Please log in first.", "warning")
            return redirect(url_for("admin_dashboard"))
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        admin = Admin.query.filter_by(username=flask_session["admin_user"]).first()
        if not admin or not check_password_hash(admin.password_hash, current_pw):
            flash("Current password is incorrect.", "danger")
        elif len(new_pw) < 6:
            flash("New password must be at least 6 characters.", "warning")
        else:
            admin.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash("Password updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    # Prepare dashboard data
    active_session = get_active_session()
    sections = ["CSE-A", "CSE-B", "CSE-C"]
    return render_template(
        "admin_dashboard.html",
        is_logged_in=bool(flask_session.get("admin_user")),
        active_session=active_session,
        sections=sections
    )


@app.route("/logout")
def logout():
    flask_session.pop("admin_user", None)
    flash("Logged out.", "info")
    return redirect(url_for("admin_dashboard"))


# -----------------------
# Live Attendance APIs
# -----------------------
@app.route("/api/live_attendance")
def api_live_attendance():
    section = request.args.get("section", "CSE-A")
    active_session = get_active_session()
    data = []
    students = Student.query.filter_by(section=section).order_by(Student.roll_no.asc()).all()
    present_ids = set()

    if active_session:
        rows = Attendance.query.filter_by(session_id=active_session.id).all()
        present_ids = {r.student_id for r in rows}

    for s in students:
        data.append({
            "roll_no": s.roll_no,
            "name": s.name,
            "present": s.id in present_ids
        })
    return jsonify({"section": section, "students": data, "active": bool(active_session)})


# -----------------------
# CSV Export (current session)
# -----------------------
@app.route("/export_csv")
@admin_login_required
def export_csv():
    active_session = get_active_session()
    if not active_session:
        flash("No active session. Start a session to export live attendance.", "warning")
        return redirect(url_for("admin_dashboard"))

    # Build a status map
    rows = Attendance.query.filter_by(session_id=active_session.id).all()
    present_ids = {r.student_id: r.timestamp for r in rows}

    students = Student.query.order_by(Student.section.asc(), Student.roll_no.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["roll_no", "name", "section", "status", "timestamp_utc"])

    for s in students:
        if s.id in present_ids:
            writer.writerow([s.roll_no, s.name, s.section, "Present", present_ids[s.id].isoformat()])
        else:
            writer.writerow([s.roll_no, s.name, s.section, "Absent", ""])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"attendance_session_{active_session.id}.csv"
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)


# -----------------------
# Dev convenience
# -----------------------
@app.route("/healthz")
def healthz():
    return {"ok": True, "time": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    app.run(debug=True)
