import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import MAX_CV_BYTES, create_app


class FormSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = str(self.root / "test.db")
        self.upload_dir = self.root / "uploads"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database,
                "UPLOAD_FOLDER": str(self.upload_dir),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def form_data(self, **overrides):
        data = {
            "full_name": "Ana Pérez",
            "email": "ana@example.com",
            "phone": "5551234567",
            "area": "Ingeniería Civil",
        }
        data.update(overrides)
        return data

    def test_form_submission_is_saved_to_sqlite_without_cv(self):
        response = self.client.post("/", data=self.form_data())

        self.assertEqual(response.status_code, 201)
        self.assertIn(b"Folio: 1", response.data)
        with closing(sqlite3.connect(self.database)) as db:
            saved = db.execute(
                """
                SELECT full_name, email, phone, area, message, cv_path, cv_original_name
                FROM submissions
                """
            ).fetchone()
        self.assertEqual(
            saved,
            (
                "Ana Pérez",
                "ana@example.com",
                "5551234567",
                "Ingeniería Civil",
                "",
                None,
                None,
            ),
        )

    def test_pdf_is_saved_outside_database_and_path_is_recorded(self):
        data = self.form_data(
            cv_file=(io.BytesIO(b"%PDF-1.4\ncontenido de prueba"), "mi-cv.pdf")
        )
        response = self.client.post("/", data=data)

        self.assertEqual(response.status_code, 201)
        with closing(sqlite3.connect(self.database)) as db:
            cv_path, original_name = db.execute(
                "SELECT cv_path, cv_original_name FROM submissions"
            ).fetchone()
        saved_file = self.root / cv_path
        self.assertTrue(saved_file.is_file())
        self.assertEqual(saved_file.read_bytes(), b"%PDF-1.4\ncontenido de prueba")
        self.assertEqual(original_name, "mi-cv.pdf")

    def test_invalid_email_is_not_saved(self):
        response = self.client.post("/", data=self.form_data(email="no-es-correo"))

        self.assertEqual(response.status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            count = db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_submission_requires_one_valid_career(self):
        missing = self.client.post("/", data=self.form_data(area=""))
        unknown = self.client.post("/", data=self.form_data(area="Otra carrera"))

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(unknown.status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            count = db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_non_pdf_and_invalid_pdf_are_rejected(self):
        non_pdf = self.form_data(cv_file=(io.BytesIO(b"contenido"), "cv.txt"))
        invalid_pdf = self.form_data(cv_file=(io.BytesIO(b"no es pdf"), "cv.pdf"))

        self.assertEqual(self.client.post("/", data=non_pdf).status_code, 400)
        self.assertEqual(self.client.post("/", data=invalid_pdf).status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            count = db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_pdf_over_size_limit_is_rejected(self):
        content = b"%PDF-" + b"x" * MAX_CV_BYTES
        response = self.client.post(
            "/",
            data=self.form_data(cv_file=(io.BytesIO(content), "large.pdf")),
        )

        self.assertEqual(response.status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            count = db.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_existing_database_is_migrated_without_losing_rows(self):
        old_database = self.root / "old.db"
        with closing(sqlite3.connect(old_database)) as db:
            db.execute(
                """
                CREATE TABLE submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    area TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                "INSERT INTO submissions (full_name, email, area, message) "
                "VALUES (?, ?, ?, ?)",
                ("Luis García", "luis@example.com", "Derecho", "Registro anterior"),
            )
            db.commit()

        create_app(
            {
                "TESTING": True,
                "DATABASE": str(old_database),
                "UPLOAD_FOLDER": str(self.root / "old-uploads"),
            }
        )

        with closing(sqlite3.connect(old_database)) as db:
            row = db.execute(
                "SELECT full_name, message, cv_path, cv_original_name FROM submissions"
            ).fetchone()
        self.assertEqual(row, ("Luis García", "Registro anterior", None, None))


if __name__ == "__main__":
    unittest.main()
