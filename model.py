from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="todo")  # todo, in_progress, done
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    paper = db.relationship("Paper", backref="project", uselist=False, cascade="all, delete-orphan")
    draft = db.relationship("Draft", backref="project", uselist=False, cascade="all, delete-orphan")


class Paper(db.Model):
    __tablename__ = "papers"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    filename = db.Column(db.String(400), nullable=False)
    filepath = db.Column(db.String(600), nullable=False)
    extracted_text = db.Column(db.Text, nullable=True)


class Draft(db.Model):
    __tablename__ = "drafts"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, unique=True)
    fields_json = db.Column(db.Text, nullable=False, default="{}")  # store template fields as JSON string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
