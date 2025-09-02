from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    section = db.Column(db.String(20), nullable=False, index=True)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret_code = db.Column(db.String(10), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("Session", backref=db.backref("attendance_records", lazy=True, cascade="all, delete-orphan"))
    student = db.relationship("Student", backref=db.backref("attendance_entries", lazy=True, cascade="all, delete-orphan"))


def init_db():
    db.create_all()
    # Ensure a default admin exists
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin", password_hash=generate_password_hash("admin123"))
        db.session.add(admin)
        db.session.commit()
