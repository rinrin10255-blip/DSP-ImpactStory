import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename

from models import db, Project, Paper, Draft

# Safety boundary
ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret-change-me"  

    LOCAL_TZ = ZoneInfo("Europe/Amsterdam") 

    def to_local(dt):
        if dt is None:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(LOCAL_TZ)

    app.jinja_env.globals["to_local"] = to_local

    # Basic config
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///impact_poc.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Home page navigation
    @app.get("/")
    def home():
        return redirect(url_for("projects"))

    # S6 Overview
    @app.get("/projects")
    def projects():
        items = Project.query.order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=items)

    #upload page
    @app.get("/upload")
    def upload_get():
        return render_template("upload.html")

    @app.post("/upload")
    def upload_post():
        file = request.files.get("paper")
        title = (request.form.get("title") or "").strip()

        if not file or file.filename == "":
            flash("Please choose a PDF file.", "danger")
            return redirect(url_for("upload_get"))

        if not allowed_file(file.filename):
            flash("Only PDF files are allowed for now.", "danger")
            return redirect(url_for("upload_get"))

        filename = secure_filename(file.filename)
        # Avoid collisions
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        stored_name = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        file.save(filepath)

        if not title:
            # default title from filename 
            title = os.path.splitext(filename)[0]

        # Create project, paper, draft
        p = Project(title=title, status="todo")
        db.session.add(p)
        db.session.flush()  # get p.id

        paper = Paper(project_id=p.id, filename=filename, filepath=stored_name)
        db.session.add(paper)

        initial_fields = {
            "what_about": "",
            "methods": "",
            "key_insights": "",
            "results": "",
            "impact_outcomes": "",
            "limitations": "",
        }
        draft = Draft(project_id=p.id, fields_json=json.dumps(initial_fields, ensure_ascii=False))
        db.session.add(draft)

        db.session.commit()

        flash("Uploaded and project created.", "success")
        return redirect(url_for("project_detail", project_id=p.id))

    # View the PDF online
    @app.get("/papers/<int:project_id>/view")
    def view_paper(project_id: int):
        proj = Project.query.get_or_404(project_id)
        if not proj.paper:
            flash("No paper found for this project.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        # inline
        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=proj.paper.filepath,
            as_attachment=False,          
            mimetype="application/pdf"    
        )

    # 核心！S4 auto-fill extraction
    @app.get("/projects/<int:project_id>")
    def project_detail(project_id: int):
        proj = Project.query.get_or_404(project_id)
        draft = proj.draft
        fields = {}
        try:
            fields = json.loads(draft.fields_json) if draft else {}
        except json.JSONDecodeError:
            fields = {}

        return render_template("project_detail.html", project=proj, paper=proj.paper, fields=fields)

    # S5 Review & Edit
    @app.post("/projects/<int:project_id>/save")
    def project_save(project_id: int):
        proj = Project.query.get_or_404(project_id)
        draft = proj.draft
        if not draft:
            draft = Draft(project_id=proj.id, fields_json="{}")
            db.session.add(draft)

        fields = {
            "what_about": (request.form.get("what_about") or "").strip(),
            "methods": (request.form.get("methods") or "").strip(),
            "key_insights": (request.form.get("key_insights") or "").strip(),
            "results": (request.form.get("results") or "").strip(),
            "impact_outcomes": (request.form.get("impact_outcomes") or "").strip(),
            "limitations": (request.form.get("limitations") or "").strip(),
        }
        draft.fields_json = json.dumps(fields, ensure_ascii=False)
        proj.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Draft saved.", "success")
        return redirect(url_for("project_detail", project_id=proj.id))

    # Progress tracking
    @app.post("/projects/<int:project_id>/status")
    def project_status(project_id: int):
        proj = Project.query.get_or_404(project_id)
        new_status = (request.form.get("status") or "").strip()

        if new_status not in {"todo", "in_progress", "done"}:
            flash("Invalid status.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        proj.status = new_status
        db.session.commit()
        flash("Status updated.", "success")
        return redirect(url_for("project_detail", project_id=proj.id))

    @app.get("/papers/<int:project_id>/download")
    def download_paper(project_id: int):
        proj = Project.query.get_or_404(project_id)
        if not proj.paper:
            flash("No paper found for this project.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        # send stored file
        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=proj.paper.filepath,
            as_attachment=True,
            download_name=proj.paper.filename,
        )

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
