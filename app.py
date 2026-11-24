import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from flask import Flask, current_app, g, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

MAX_CV_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_CV_BYTES + 128 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    area TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cv_path TEXT,
    cv_original_name TEXT
)
"""

CAREER_GROUPS = {
    "Ingenierías": (
        "Ingeniería Civil",
        "Ingeniería en Computación",
        "Ingeniería Eléctrica Electrónica",
        "Ingeniería Industrial",
        "Ingeniería Mecánica",
    ),
    "Ciencias Sociales": (
        "Comunicación y Periodismo",
        "Derecho",
        "Economía",
        "Planificación para el Desarrollo Agropecuario",
        "Relaciones Internacionales",
        "Sociología",
    ),
    "Humanidades y Artes": (
        "Arquitectura",
        "Diseño Industrial",
        "Pedagogía",
    ),
}
CAREERS = {career for careers in CAREER_GROUPS.values() for career in careers}

FIELD_LIMITS = {
    "full_name": 120,
    "email": 254,
    "phone": 30,
    "area": 120,
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.environ.get(
            "DATABASE_PATH",
            str(Path(app.instance_path) / "formulario.db"),
        ),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        CV_MAX_BYTES=MAX_CV_BYTES,
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
    )
    if test_config:
        app.config.update(test_config)

    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as db:
        db.execute(SCHEMA)
        columns = {
            row[1]
            for row in db.execute("PRAGMA table_info(submissions)").fetchall()
        }
        for column in ("cv_path", "cv_original_name"):
            if column not in columns:
                db.execute(f"ALTER TABLE submissions ADD COLUMN {column} TEXT")
        db.commit()
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_request(_error):
        return render_template(
            "index.html",
            error="El archivo supera el límite permitido de 5 MB.",
            values={"area": ""},
            career_groups=CAREER_GROUPS,
        ), 413

    @app.route("/", methods=["GET", "POST"])
    def index():
        error = None
        values = {field: "" for field in FIELD_LIMITS}

        if request.method == "POST":
            values = {
                field: request.form.get(field, "").strip()
                for field in FIELD_LIMITS
            }
            if any(not values[field] for field in ("full_name", "email", "area")):
                error = "Completa todos los campos obligatorios."
            elif values["area"] not in CAREERS:
                error = "Selecciona una carrera de la lista."
            elif any(
                len(values[field]) > limit
                for field, limit in FIELD_LIMITS.items()
            ):
                error = "Uno o más campos superan el límite permitido."
            elif "@" not in values["email"] or "." not in values["email"].rsplit("@", 1)[-1]:
                error = "Escribe un correo electrónico válido."

            uploaded_cv = request.files.get("cv_file")
            original_name = None
            saved_path = None
            if error is None and uploaded_cv and uploaded_cv.filename:
                safe_name = secure_filename(uploaded_cv.filename)
                if Path(safe_name).suffix.lower() != ".pdf":
                    error = "Adjunta tu CV en formato PDF."
                else:
                    uploaded_cv.stream.seek(0, os.SEEK_END)
                    file_size = uploaded_cv.stream.tell()
                    uploaded_cv.stream.seek(0)
                    if file_size > current_app.config["CV_MAX_BYTES"]:
                        error = "El archivo supera el límite permitido de 5 MB."
                    elif uploaded_cv.stream.read(5) != b"%PDF-":
                        error = "El archivo no parece ser un PDF válido."
                    uploaded_cv.stream.seek(0)

                    if error is None:
                        original_name = safe_name
                        if len(original_name) > 255:
                            original_name = f"{Path(original_name).stem[:250]}.pdf"
                        stored_name = f"{uuid4().hex}.pdf"
                        saved_path = Path(current_app.config["UPLOAD_FOLDER"]) / stored_name
                        try:
                            uploaded_cv.save(saved_path)
                        except OSError:
                            saved_path.unlink(missing_ok=True)
                            raise

            if error is None:
                try:
                    cursor = get_db().execute(
                        """
                        INSERT INTO submissions (
                            full_name, email, phone, area, message,
                            cv_path, cv_original_name
                        )
                        VALUES (?, ?, ?, ?, '', ?, ?)
                        """,
                        (
                            values["full_name"],
                            values["email"],
                            values["phone"],
                            values["area"],
                            str(Path("uploads") / saved_path.name) if saved_path else None,
                            original_name,
                        ),
                    )
                    get_db().commit()
                except sqlite3.Error:
                    if saved_path is not None:
                        saved_path.unlink(missing_ok=True)
                    raise
                return render_template(
                    "index.html",
                    submission_id=cursor.lastrowid,
                    career_groups=CAREER_GROUPS,
                    values=values,
                ), 201

        return render_template(
            "index.html",
            error=error,
            values=values,
            career_groups=CAREER_GROUPS,
        ), (
            400 if error else 200
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(port=8000, debug=os.environ.get("FLASK_DEBUG") == "1")
