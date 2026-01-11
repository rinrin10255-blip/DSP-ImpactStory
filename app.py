import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader


from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from werkzeug.utils import secure_filename
from models import db, Project, Paper, Draft

from models import db, Project, Paper, Draft

ALLOWED_EXTENSIONS = {"pdf"}

# PDF text extraction utility
def extract_pdf_raw_text(pdf_path: str, max_pages: int = None) -> str:
    reader = PdfReader(pdf_path)
    texts = []
    end = len(reader.pages) if max_pages is None else min(len(reader.pages), max_pages)
    for i in range(end):
        page_text = reader.pages[i].extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            texts.append(page_text)
    return "\n\n".join(texts).strip()

# PyMuPDF
#def extract_pdf_raw_text(pdf_path: str, max_chars: int = 120000) -> str:
    doc = fitz.open(pdf_path)
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
        if sum(len(x) for x in parts) >= max_chars:
            break
    doc.close()
    text = "\n".join(parts).strip()
    return text[:max_chars]

#def build_extracted_json_from_raw(raw: str) -> dict:
    raw_clean = (raw or "").strip()

    # naive "abstract" finder
    lower = raw_clean.lower()
    abstract = ""
    idx = lower.find("abstract")
    if idx != -1:
        abstract = raw_clean[idx: idx + 2000].strip()
    else:
        abstract = raw_clean[:1200].strip()

    # basic placeholders (stable keys)
    return {
        "what_about": abstract[:800],
        "methods": "",
        "key_insights": "",
        "results": "",
        "impact_outcomes": "",
        "limitations": "",
    }

def build_extracted_json_from_raw(raw: str) -> dict:
    raw_clean = (raw or "").strip()
    lower = raw_clean.lower()

    # naive abstract finder
    abstract = ""
    idx = lower.find("abstract")
    if idx != -1:
        abstract = raw_clean[idx: idx + 2000].strip()
    else:
        abstract = raw_clean[:1200].strip()

    return {
        "what_about": abstract[:800],
        "methods": "",
        "key_insights": "",
        "results": "",
        "impact_outcomes": "",
        "limitations": ""
    }

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Timezone helper (for UI display)
    LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

    def to_local(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(LOCAL_TZ)

    app.jinja_env.globals["to_local"] = to_local

    # DB
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///impact_poc.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Uploads
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ---------------------------
    # Home / Overview (S6)
    # ---------------------------
    @app.get("/")
    def home():
        return redirect(url_for("projects"))

    @app.get("/projects")
    def projects():
        items = Project.query.order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=items)

    # ---------------------------
    # S1 Upload
    # ---------------------------
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
            title = os.path.splitext(filename)[0]

        # Create project + paper + empty draft
        p = Project(title=title, status="todo")
        db.session.add(p)
        db.session.flush()  # get p.id

        paper = Paper(
            project_id=p.id,
            filename=filename,
            filepath=stored_name,
        )
        
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

    # ---------------------------
    # S2 Project detail (UI page)
    # ---------------------------
    @app.get("/projects/<int:project_id>")
    def project_detail(project_id: int):
        proj = Project.query.get_or_404(project_id)

        # draft fields
        fields = {}
        if proj.draft and proj.draft.fields_json:
            try:
                fields = json.loads(proj.draft.fields_json)
            except json.JSONDecodeError:
                fields = {}

        # extraction preview
        extracted_raw = None
        extracted_json = {}

        if proj.paper:
        # raw text (for display / debug)
            extracted_raw = proj.paper.extracted_raw

        # structured json (for preview / autofill)
            if proj.paper.extracted_json:
                try:
                    extracted_json = json.loads(proj.paper.extracted_json)
                except json.JSONDecodeError:
                    extracted_json = {}

        return render_template(
            "project_detail.html",
            project=proj,
            paper=proj.paper,
            fields=fields,
            extracted_raw=extracted_raw,
            extracted_json=extracted_json,
        )

    # ---------------------------
    # PDF view / download
    # ---------------------------
    @app.get("/papers/<int:project_id>/view")
    def view_paper(project_id: int):
        proj = Project.query.get_or_404(project_id)
        if not proj.paper:
            flash("No paper found for this project.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=proj.paper.filepath,
            as_attachment=False,
            mimetype="application/pdf",
        )

    @app.get("/papers/<int:project_id>/download")
    def download_paper(project_id: int):
        proj = Project.query.get_or_404(project_id)
        if not proj.paper:
            flash("No paper found for this project.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=proj.paper.filepath,
            as_attachment=True,
            download_name=proj.paper.filename,
        )

    # ---------------------------
    #S3 Real Extraction: PDF -> raw text + extracted_json
    # ---------------------------
    @app.post("/projects/<int:project_id>/extract")
    def project_extract(project_id: int):
        proj = Project.query.get_or_404(project_id)
        if not proj.paper:
            flash("No paper uploaded.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], proj.paper.filepath)
        try:
            raw = extract_pdf_raw_text(pdf_path)
        except Exception as e:
            flash(f"PDF extraction failed: {e}", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))
        proj.paper.extracted_raw = raw

        extracted = build_extracted_json_from_raw(raw)
        proj.paper.extracted_json = json.dumps(extracted, ensure_ascii=False)

        proj.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Extraction completed (raw text + JSON).", "success")
        return redirect(url_for("project_detail", project_id=proj.id))

    # ---------------------------
    # S4 Auto-fill (merge extraction -> draft)
    # ---------------------------
    # S4 Stable Auto-fill: extracted_json -> draft fields
    @app.post("/projects/<int:project_id>/autofill")
    def project_autofill(project_id: int):
        proj = Project.query.get_or_404(project_id)

        if not proj.paper or not proj.paper.extracted_json:
            flash("No extracted JSON found. Please run extraction first.", "warning")
            return redirect(url_for("project_detail", project_id=proj.id))
        try:
            extraction = json.loads(proj.paper.extracted_json)
        except json.JSONDecodeError:
            flash("Extracted JSON is invalid. Please run extraction again.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))
        # Ensure draft exists
        draft = proj.draft
        if not draft:
            draft = Draft(project_id=proj.id, fields_json="{}")
            db.session.add(draft)
        allowed_keys = {"what_about", "methods", "key_insights", "results", "impact_outcomes", "limitations"}

        try:
            current = json.loads(draft.fields_json) if draft.fields_json else {}
        except json.JSONDecodeError:
            current = {}

        # Only fill keys that exist and are non-empty in extraction
        for k in allowed_keys:
            v = extraction.get(k, "")
            if isinstance(v, str) and v.strip():
                current[k] = v.strip()
        draft.fields_json = json.dumps(current, ensure_ascii=False)
        proj.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Auto-fill completed from extracted JSON.", "success")
        return redirect(url_for("project_detail", project_id=proj.id))

    # ---------------------------
    # S5 Review & Edit (save manual edits)
    # ---------------------------
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

    # ---------------------------
    # Progress tracking (status)
    # ---------------------------
    @app.post("/projects/<int:project_id>/status")
    def project_status(project_id: int):
        proj = Project.query.get_or_404(project_id)
        new_status = (request.form.get("status") or "").strip()

        if new_status not in {"todo", "in_progress", "done"}:
            flash("Invalid status.", "danger")
            return redirect(url_for("project_detail", project_id=proj.id))

        proj.status = new_status
        proj.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Status updated.", "success")
        return redirect(url_for("project_detail", project_id=proj.id))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
