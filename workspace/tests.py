import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import Project, Skill
from workspace.services.state import ensure_settings


class PixelVaultApiTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.user = User.objects.create_user(username="builder", password="test-password-123")
        ensure_settings(self.user)
        self.client.force_login(self.user)

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_state_round_trip(self):
        response = self.client.get(reverse("api_state"))
        self.assertEqual(response.status_code, 200)
        state = response.json()
        state["ideas"] = [{
            "id": "idea_test",
            "title": "Test idea",
            "description": "Django-backed",
            "contentType": "note",
            "content": "",
            "status": "inbox",
            "priority": "medium",
            "goal": "",
            "audience": "",
            "sourceUrl": "",
            "tags": ["test"],
            "projectId": "",
            "nextAction": "",
            "pinned": False,
            "created": "2026-08-19",
            "updated": "2026-08-19",
        }]
        saved = self.client.put(reverse("api_state"), data=state, content_type="application/json")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["ideas"][0]["title"], "Test idea")

    def test_health_requires_login_and_works(self):
        response = self.client.get(reverse("api_health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["backend"], "django")

        self.client.logout()
        response = self.client.get(reverse("api_health"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_backup_download(self):
        response = self.client.get(reverse("backup_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_state_rejects_invalid_json(self):
        response = self.client.put(reverse("api_state"), data="{broken", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid workspace data")

    @mock.patch("workspace.views.MAX_STATE_BYTES", 10)
    def test_state_rejects_oversized_payload(self):
        response = self.client.put(reverse("api_state"), data=json.dumps({"data": "x" * 30}), content_type="application/json")
        self.assertEqual(response.status_code, 413)

    def test_skill_upload_download_and_type_validation(self):
        skill = Skill.objects.create(owner=self.user, name="Reviewer", description="Reviews UI")
        bad = SimpleUploadedFile("bad.exe", b"nope", content_type="application/octet-stream")
        response = self.client.post(reverse("skill_upload", args=[skill.pk]), {"file": bad})
        self.assertEqual(response.status_code, 400)

        upload = SimpleUploadedFile("review.skill.md", b"# Review\n", content_type="text/markdown")
        response = self.client.post(reverse("skill_upload", args=[skill.pk]), {"file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "# Review\n")

        response = self.client.get(reverse("skill_download", args=[skill.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"# Review\n")
        self.assertIn("review.skill.md", response["Content-Disposition"])

    def test_report_downloads_have_expected_formats(self):
        png = self.client.get(reverse("report_png"))
        self.assertEqual(png.status_code, 200)
        self.assertTrue(png.content.startswith(b"\x89PNG"))

        pdf = self.client.get(reverse("report_pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))


class ProjectFilesystemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="files", password="test-password-123")
        self.settings = ensure_settings(self.user)
        self.client.force_login(self.user)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index.html").write_text("<h1>Safe preview</h1>", encoding="utf-8")
        (self.root / "notes.md").write_text("# Notes", encoding="utf-8")
        (self.root / ".env").write_text("SECRET=hidden", encoding="utf-8")
        (self.root / "credentials.json").write_text('{"token":"hidden"}', encoding="utf-8")
        (self.root / "local.sqlite3").write_bytes(b"private")
        (self.root / ".git").mkdir()
        self.project = Project.objects.create(owner=self.user, title="Local site", local_path=str(self.root), is_web=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tree_hides_dotfiles_credentials_and_databases(self):
        response = self.client.get(reverse("project_tree", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        names = {entry["name"] for entry in response.json()["entries"]}
        self.assertIn("index.html", names)
        self.assertIn("notes.md", names)
        self.assertNotIn(".env", names)
        self.assertNotIn(".git", names)
        self.assertNotIn("credentials.json", names)
        self.assertNotIn("local.sqlite3", names)

    def test_file_preview_blocks_protected_and_traversal_paths(self):
        response = self.client.get(reverse("project_file", args=[self.project.pk]), {"path": "notes.md"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "# Notes")

        response = self.client.get(reverse("project_file", args=[self.project.pk]), {"path": ".env"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("project_file", args=[self.project.pk]), {"path": "../outside.txt"})
        self.assertEqual(response.status_code, 403)

    def test_static_preview_is_sandboxed_and_never_cached(self):
        response = self.client.get(reverse("project_preview", args=[self.project.pk, "index.html"]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("sandbox allow-scripts", response["Content-Security-Policy"])
        self.assertNotIn("allow-same-origin", response["Content-Security-Policy"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(b"".join(response.streaming_content), b"<h1>Safe preview</h1>")

        response = self.client.get(reverse("project_preview", args=[self.project.pk, ".env"]))
        self.assertEqual(response.status_code, 404)

    def test_workspace_root_boundary_is_enforced(self):
        with tempfile.TemporaryDirectory() as other:
            self.settings.workspace_root = other
            self.settings.save(update_fields=["workspace_root"])
            response = self.client.get(reverse("project_tree", args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)


class FirstRunSetupTests(TestCase):
    def test_login_routes_to_setup_when_database_has_no_user(self):
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("first_run_setup"))

    def test_setup_creates_and_logs_in_first_user(self):
        response = self.client.post(reverse("first_run_setup"), {
            "username": "first-user",
            "display_name": "First Builder",
            "workspace_name": "First Vault",
            "password1": "A-strong-test-password-2026",
            "password2": "A-strong-test-password-2026",
        })
        self.assertRedirects(response, reverse("app"))
        user = User.objects.get(username="first-user")
        self.assertEqual(user.pixelvault_settings.display_name, "First Builder")


class LoginPageTests(TestCase):
    def test_login_uses_the_polished_versioned_interface(self):
        User.objects.create_user(username="existing-owner", password="test-password-123")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WELCOME")
        self.assertContains(response, "login-submit")
        self.assertContains(response, "login-password-toggle")
        self.assertContains(response, f"?v={settings.PIXELVAULT_VERSION}")
