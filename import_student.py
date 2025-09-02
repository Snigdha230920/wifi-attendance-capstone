import csv
from models import db, Student
from app import app  # uses the same app & db config

def import_students(csv_path="students.csv"):
    with app.app_context():
        # wipe existing students (optional; comment out if you want to keep)
        Student.query.delete()
        db.session.commit()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = Student(
                    roll_no=row["roll_no"].strip().upper(),
                    name=row["name"].strip(),
                    section=row["section"].strip().upper()
                )
                db.session.add(s)
            db.session.commit()
        print("Students imported/updated successfully.")

if __name__ == "__main__":
    import_students()
