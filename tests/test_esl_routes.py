import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image

os.environ.setdefault("AUTH_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

import app as command
from hanshow_integration import PushTarget


class EslRouteTests(unittest.TestCase):
    def setUp(self):
        command.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = command.app.test_client()
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        self.user = {"id": 1, "name": "Test", "email": "test@example.com", "role": "staff"}
        self.target = PushTarget("lumina-a", "Lab Lumina BF", "SKU-1", 1600, 1200)

    def test_esl_page_uses_friendly_target_without_provider_identifiers(self):
        files = [{"name": "vehicle.png"}]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=files),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "get_push_jobs", return_value=[]),
        ):
            response = self.client.get("/esl")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Shyft Command", response.data)
        self.assertIn(b"Vehicle Hangers", response.data)
        self.assertIn(b"Showroom Display 1", response.data)
        self.assertIn(b"13.3&quot; Lumina", response.data)
        self.assertIn(b"1600 \xc3\x97 1200", response.data)
        self.assertIn(b"Manage display", response.data)
        self.assertIn(b'href="/esl/lumina-a"', response.data)
        self.assertIn(b"LIVE", response.data)
        self.assertNotIn(b"Available Media", response.data)
        self.assertNotIn(b"Lab Lumina BF", response.data)
        self.assertNotIn(b"SKU-1", response.data)
        self.assertNotIn(b"Hanshow", response.data)

    def test_esl_page_exposes_supported_lumina_and_nebular_profiles(self):
        targets = [
            self.target,
            PushTarget("lumina-b", "Lab Lumina C0", "SKU-2", 1600, 1200),
            PushTarget("nebular", "Lab Nebular", "SKU-3", 672, 960),
            PushTarget("unsupported", "Odd Size Device", "SKU-4", 800, 480),
        ]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=[{"name": "vehicle.png"}]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "targets_from_environment", return_value=targets),
            patch.object(command, "get_push_jobs", return_value=[]),
        ):
            response = self.client.get("/esl")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Showroom Display 1", response.data)
        self.assertIn(b"Showroom Display 2", response.data)
        self.assertIn(b"Showroom Display 3", response.data)
        self.assertIn(b"9.7&quot; Nebular Pro", response.data)
        self.assertNotIn(b"Showroom Display 4", response.data)
        self.assertNotIn(b"Odd Size Device", response.data)

    def test_nebular_workspace_reports_9_7_inch_profile(self):
        target = PushTarget("nebular-a", "Nebular A", "SKU-N1", 672, 960)
        workspace = command.esl_target_workspace(target, [])
        self.assertEqual(workspace["model"], '9.7" Nebular Pro')
        self.assertEqual((workspace["width"], workspace["height"]), (672, 960))

    def test_compatible_media_is_accepted_for_lumina_and_nebular(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "source.png")
            Image.new("RGB", (1200, 1200), "white").save(path)
            nebular = PushTarget("nebular", "Nebular", "SKU-N", 672, 960)
            with (
                patch.object(command, "existing_source_path", return_value=path),
                patch.object(command, "get_media_catalog", return_value={}),
            ):
                self.assertTrue(command.esl_media_compatibility("source.png", self.target)["compatible"])
                self.assertTrue(command.esl_media_compatibility("source.png", nebular)["compatible"])

    def test_incompatible_aspect_ratio_and_wrong_family_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "banner.png")
            Image.new("RGB", (4000, 200), "white").save(path)
            with (
                patch.object(command, "existing_source_path", return_value=path),
                patch.object(command, "get_media_catalog", return_value={}),
            ):
                result = command.esl_media_compatibility("banner.png", self.target)
            self.assertFalse(result["compatible"])
            self.assertIn("aspect ratio", result["reason"])

            with (
                patch.object(command, "existing_source_path", return_value=path),
                patch.object(command, "get_media_catalog", return_value={
                    "banner.png": {"esl_profiles": ["nebular_9_7"]}
                }),
            ):
                result = command.esl_media_compatibility("banner.png", self.target)
            self.assertFalse(result["compatible"])
            self.assertIn("different display family", result["reason"])

    def test_corrupt_media_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "broken.png")
            with open(path, "wb") as output:
                output.write(b"not-an-image")
            with (
                patch.object(command, "existing_source_path", return_value=path),
                patch.object(command, "get_media_catalog", return_value={}),
            ):
                result = command.esl_media_compatibility("broken.png", self.target)
        self.assertFalse(result["compatible"])
        self.assertIn("corrupt or unreadable", result["reason"])

    def test_final_payload_gate_accepts_exact_lumina_and_nebular_pngs(self):
        for target in (
            self.target,
            PushTarget("nebular", "Nebular", "SKU-N", 672, 960),
        ):
            payload = BytesIO()
            Image.new("1", (target.width, target.height), 1).save(payload, "PNG")
            command.validate_rendered_esl_payload(payload.getvalue(), target)

    def test_final_payload_gate_rejects_wrong_dimensions(self):
        payload = BytesIO()
        Image.new("1", (672, 960), 1).save(payload, "PNG")
        with self.assertRaisesRegex(ValueError, "invalid"):
            command.validate_rendered_esl_payload(payload.getvalue(), self.target)

    def test_latest_accepted_push_becomes_live_for_only_its_target(self):
        second = PushTarget("lumina-b", "Lab Lumina C0", "SKU-2", 1600, 1200)
        jobs = [
            {
                "status": "accepted",
                "asset": "older.png",
                "updated_at": "2026-08-20T01:00:00Z",
                "targets": [{"id": "lumina-a"}],
            },
            {
                "status": "failed",
                "asset": "failed.png",
                "updated_at": "2026-08-20T02:00:00Z",
                "targets": [{"id": "lumina-a"}],
            },
            {
                "status": "accepted",
                "asset": "newer.png",
                "updated_at": "2026-08-20T03:00:00Z",
                "targets": [{"id": "lumina-a"}],
            },
        ]
        state = command.esl_live_state(jobs, [self.target, second])
        self.assertEqual(state["lumina-a"]["asset"], "newer.png")
        self.assertNotIn("lumina-b", state)

    def test_live_state_uses_timestamp_per_target_and_survives_history_hiding(self):
        jobs = [
            {
                "id": "new",
                "status": "accepted",
                "asset": "new.png",
                "updated_at": "2026-08-21T03:00:00Z",
                "history_deleted_at": "2026-08-21T04:00:00Z",
                "targets": [{"id": "lumina-a"}],
            },
            {
                "id": "old",
                "status": "accepted",
                "asset": "old.png",
                "updated_at": "2026-08-21T01:00:00Z",
                "targets": [{"id": "lumina-a"}],
            },
        ]
        state = command.esl_live_state(jobs, [self.target])
        self.assertEqual(state["lumina-a"]["asset"], "new.png")

    def test_vehicle_hanger_cards_link_to_independent_target_workspaces(self):
        targets = [
            PushTarget("38-BF-F1-8C", "Lumina BF", "SHYFT-EAGLE-MK2-BF", 1600, 1200),
            PushTarget("38-C0-53-8C", "Lumina C0", "SHYFT-EAGLE-MK2-C0", 1600, 1200),
        ]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=[{"name": "vehicle.png", "thumb_url": "/thumb", "normalised_url": "/ready"}]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "targets_from_environment", return_value=targets),
            patch.object(command, "get_push_jobs", return_value=[]),
        ):
            response = self.client.get("/esl")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/esl/38-BF-F1-8C"', response.data)
        self.assertIn(b'href="/esl/38-C0-53-8C"', response.data)
        self.assertEqual(response.data.count(b'data-device-card data-search-text="Showroom Display'), 2)
        self.assertIn(b"Search displays", response.data)
        self.assertIn(b"repeat(auto-fill, minmax(240px, 1fr))", response.data)
        self.assertNotIn(b"Stage selected media", response.data)
        self.assertNotIn(b"window.confirm(\"Push", response.data)

    def test_display_workspace_has_device_context_live_staged_preview_and_back_navigation(self):
        file = {
            "name": "candidate.png", "thumb_url": "/thumb", "normalised_url": "/ready",
            "original_name": "candidate.pdf", "original_url": "/original.pdf", "lcd_url": "/lcd", "eink_url": "/eink",
        }
        live_file = {
            "name": "live.png", "thumb_url": "/live-thumb", "normalised_url": "/live-ready",
            "original_url": "/live-original", "lcd_url": "/live-lcd", "eink_url": "/live-eink",
        }
        jobs = [{
            "status": "accepted", "asset": "live.png", "updated_at": "2026-08-21T01:00:00Z",
            "batch_no": "batch-1", "targets": [{"id": "lumina-a", "label": "Showroom Display 1"}],
        }]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[live_file, file]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=jobs),
            patch.object(command, "get_esl_staged_asset", return_value="candidate.png"),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
        ):
            response = self.client.get("/esl/lumina-a")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div class="workspace-nav"><a href="/esl">\xe2\x86\x90 Vehicle Hangers</a><span>Showroom Display 1</span></div>', response.data)
        self.assertIn(b"Showroom Display 1", response.data)
        self.assertIn(b"live.png", response.data)
        self.assertIn(b"candidate.png", response.data)
        self.assertIn(b"LIVE S-ROOM 1", response.data)
        self.assertIn(b"STAGED S-ROOM 1", response.data)
        self.assertIn(b"onclick=\"openPreview(this)\"", response.data)
        self.assertIn(b"data-staged-thumbnail", response.data)
        self.assertEqual(response.data.count(b'>Stage</button>'), 2)
        self.assertEqual(response.data.count(b'<span class="enlarge-hint">click to enlarge</span>'), 2)
        self.assertNotIn(b"Stage for Showroom Display", response.data)
        self.assertNotIn(b"Stage selected media", response.data)
        self.assertNotIn(b"confirm('PUSH", response.data)
        self.assertIn(b'<section class="device-shell">', response.data)
        self.assertIn(b'<div class="device-actions">', response.data)
        self.assertIn(b'onclick="previewStagedEsl()"', response.data)
        self.assertIn(b'onclick="pushStagedEsl()"', response.data)
        self.assertIn(b"Push to Showroom Display 1?", response.data)
        self.assertIn(b'class="confirmation-cancel" type="button"', response.data)
        self.assertIn(b"Final rendered preview for Showroom Display 1", response.data)
        self.assertIn(b'data-original-name="candidate.pdf"', response.data)
        self.assertIn(b"Original source:", response.data)
        self.assertIn(b"Chrome's PDF viewer", response.data)
        self.assertIn(b"I have reviewed this preview and am happy to push the image as shown.", response.data)
        self.assertIn(b'id="confirmationRenderMode"', response.data)
        self.assertIn(b'onchange="updateEslRenderMode(this.value)"', response.data)
        self.assertIn(b"B&W uses monochrome dithering", response.data)
        self.assertIn(b'name="preview_acknowledged"', response.data)
        self.assertIn(b'id="confirmedPushButton" class="push" disabled>PUSH</button>', response.data)
        workspace_markup = response.get_data(as_text=True).split('<section>')[-1].split('</section>')[0]
        self.assertNotIn("workspace-state-row", workspace_markup)
        live_panel = response.get_data(as_text=True).split('<aside class="live-panel">', 1)[1].split("</aside>", 1)[0]
        self.assertNotIn("STAGED", live_panel)

    def test_display_workspace_disables_push_when_nothing_is_staged(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=[]),
            patch.object(command, "get_esl_staged_asset", return_value=None),
        ):
            response = self.client.get("/esl/lumina-a")
        self.assertIn(b'onclick="pushStagedEsl()"', response.data)
        self.assertIn(b'disabled>PUSH</button>', response.data)

    def test_staging_another_asset_replaces_only_that_displays_staged_state(self):
        with (
            patch.object(command, "get_esl_staging", return_value={"lumina-a": "first.png", "lumina-b": "other.png"}),
            patch.object(command, "save_json") as save,
        ):
            command.set_esl_staged_asset("lumina-a", "second.png")
        saved = save.call_args.args[1]
        self.assertEqual(saved["lumina-a"], "second.png")
        self.assertEqual(saved["lumina-b"], "other.png")

    def test_workspace_filename_display_is_limited_to_nineteen_characters(self):
        file = {
            "name": "12345678901234567890.png", "thumb_url": "/thumb", "normalised_url": "/ready",
            "original_url": "/original", "lcd_url": "/lcd", "eink_url": "/eink",
        }
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[file]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=[]),
            patch.object(command, "get_esl_staged_asset", return_value=None),
        ):
            response = self.client.get("/esl/lumina-a")
        self.assertIn(b'>1234567890123456...</p>', response.data)
        self.assertIn(b'title="12345678901234567890.png"', response.data)

    def test_staging_route_targets_only_the_active_display(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "render_for_screen", return_value=(BytesIO(b"rendered"), "image/png", "png")),
            patch.object(command, "validate_rendered_esl_payload"),
            patch.object(command, "set_esl_staged_asset") as stage,
        ):
            response = self.client.post(
                "/esl/lumina-a/stage",
                data={"csrf_token": "csrf", "file": "candidate.png"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        stage.assert_called_once_with("lumina-a", "candidate.png")

    def test_server_side_stage_blocks_incompatible_media(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": False, "reason": "Wrong family."}),
            patch.object(command, "render_for_screen") as render,
            patch.object(command, "set_esl_staged_asset") as stage,
        ):
            response = self.client.post(
                "/esl/lumina-a/stage",
                data={"csrf_token": "csrf", "file": "candidate.png"},
                follow_redirects=True,
            )
        self.assertIn(b"This media cannot be staged", response.data)
        render.assert_not_called()
        stage.assert_not_called()

    def test_workspace_marks_incompatible_media_and_disables_stage(self):
        file = {
            "name": "wrong.png", "thumb_url": "/thumb", "normalised_url": "/ready",
            "original_url": "/original", "lcd_url": "/lcd", "eink_url": "/eink",
        }
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[file]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=[]),
            patch.object(command, "get_esl_staged_asset", return_value=None),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": False, "reason": "Wrong family."}),
        ):
            response = self.client.get("/esl/lumina-a")
        self.assertIn(b"is-incompatible", response.data)
        self.assertIn(b"Wrong family.", response.data)
        self.assertRegex(response.get_data(as_text=True), r'<button class="eink" disabled')

    def test_navigation_orders_vehicle_hangers_next_to_devices_and_renames_media(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "get_push_jobs", return_value=[]),
        ):
            response = self.client.get("/esl")
        body = response.get_data(as_text=True)
        self.assertLess(body.index(">Devices</a>"), body.index(">Vehicle Hangers</a>"))
        self.assertLess(body.index(">Vehicle Hangers</a>"), body.index(">Media</a>"))
        self.assertLess(body.index(">Media</a>"), body.index(">Settings</a>"))
        self.assertNotIn(">Content</a>", body)

    def test_context_upload_joins_shared_catalog_and_returns_to_vehicle_hangers(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "original_upload_path", return_value="/tmp/not-written.png"),
            patch.object(command, "get_media_catalog", return_value={}),
            patch.object(command, "normalised_source_image"),
            patch.object(command, "save_media_catalog") as save_catalog,
            patch("werkzeug.datastructures.FileStorage.save"),
            patch("os.path.exists", return_value=False),
        ):
            response = self.client.post(
                "/upload",
                data={
                    "csrf_token": "csrf",
                    "next": "/esl",
                    "file": (BytesIO(b"image-bytes"), "new-vehicle-art.png"),
                },
                content_type="multipart/form-data",
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/esl")
        catalog = save_catalog.call_args.args[0]
        self.assertIn("new-vehicle-art.png", catalog)

    def test_activity_delete_only_hides_history_entry(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "hide_push_job_from_history", return_value=True) as hide,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/activity/job-1/delete",
                data={"csrf_token": "csrf"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/esl")
        hide.assert_called_once_with("job-1")
        submit.assert_not_called()

    def test_activity_delete_returns_to_individual_workspace(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "hide_push_job_from_history", return_value=True) as hide,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/activity/job-1/delete",
                data={"csrf_token": "csrf", "next": "/esl/lumina-a"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        hide.assert_called_once_with("job-1")
        submit.assert_not_called()

    def test_hidden_activity_is_removed_from_main_and_individual_views(self):
        jobs = [{
            "id": "hidden", "asset": "hidden-activity.png", "status": "failed",
            "status_label": "Failed", "created_at": "2026-08-25T00:00:00Z",
            "targets": [{"id": "lumina-a", "label": "Showroom Display 1"}],
            "events": [], "history_deleted_at": "2026-08-25T00:01:00Z",
        }]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=jobs),
            patch.object(command, "get_esl_staged_asset", return_value=None),
        ):
            main = self.client.get("/esl")
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=jobs),
            patch.object(command, "get_esl_staged_asset", return_value=None),
        ):
            individual = self.client.get("/esl/lumina-a")
        self.assertNotIn(b"hidden-activity.png", main.data)
        self.assertNotIn(b"hidden-activity.png", individual.data)

    def test_individual_activity_rows_have_delete_controls(self):
        jobs = [{
            "id": "job-1", "asset": "vehicle.png", "status": "accepted",
            "status_label": "Update sent", "created_at": "2026-08-25T00:00:00Z",
            "targets": [{"id": "lumina-a", "label": "Showroom Display 1"}], "events": [],
        }]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "get_push_jobs", return_value=jobs),
            patch.object(command, "get_esl_staged_asset", return_value=None),
        ):
            response = self.client.get("/esl/lumina-a")
        self.assertIn(b'action="/esl/activity/job-1/delete"', response.data)
        self.assertIn(b'name="next" value="/esl/lumina-a"', response.data)
        self.assertIn(b'>Delete</button>', response.data)
        self.assertIn(b'id="activitySelectAll"', response.data)
        self.assertIn(b'id="activityBulkDelete"', response.data)
        self.assertIn(b'class="job-check" form="activityBulkDeleteForm"', response.data)

    def test_bulk_activity_delete_returns_to_individual_workspace(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "hide_push_jobs_from_history", return_value=2) as hide,
        ):
            response = self.client.post(
                "/esl/activity/delete",
                data={"csrf_token": "csrf", "job_ids": ["job-1", "job-2"], "next": "/esl/lumina-a"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        hide.assert_called_once_with(["job-1", "job-2"])

    def test_media_deletion_stays_in_media_and_never_pushes(self):
        for filename in ("first.png", "second.png", "third.png"):
            with (
                patch.object(command, "current_user", return_value=self.user),
                patch.object(command, "get_media_catalog", return_value={filename: {"original": filename}}),
                patch.object(command, "save_media_catalog"),
                patch.object(command, "clear_file_references", return_value=[]),
                patch("os.path.exists", return_value=True),
                patch("os.remove") as remove,
                patch.object(command, "submit_esl_push") as submit,
            ):
                response = self.client.post(
                    "/delete",
                    data={"csrf_token": "csrf", "file": filename, "next": "/media"},
                    follow_redirects=False,
                )
            self.assertEqual(response.location, "/media")
            self.assertTrue(remove.called)
            submit.assert_not_called()

    def test_activity_deletion_does_not_delete_media(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "hide_push_job_from_history", return_value=True),
            patch("os.remove") as remove,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/activity/job-1/delete",
                data={"csrf_token": "csrf", "next": "/esl"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl")
        remove.assert_not_called()
        submit.assert_not_called()

    def test_activity_bulk_delete_hides_only_selected_history_entries(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "hide_push_jobs_from_history", return_value=2) as hide,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/activity/delete",
                data={"csrf_token": "csrf", "job_ids": ["job-1", "job-3"]},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/esl")
        hide.assert_called_once_with(["job-1", "job-3"])
        submit.assert_not_called()

    def test_activity_page_exposes_bulk_selection_controls(self):
        jobs = [{
            "id": "job-1",
            "asset": "vehicle.png",
            "status": "accepted",
            "status_label": "Update sent",
            "created_at": "2026-08-21T01:00:00Z",
            "targets": [{"label": "Showroom Display 1"}],
            "events": [],
        }]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "get_push_jobs", return_value=jobs),
        ):
            response = self.client.get("/esl")
        self.assertIn(b'id="activitySelectAll"', response.data)
        self.assertIn(b'id="activityBulkDelete"', response.data)
        self.assertIn(b'name="job_ids" value="job-1"', response.data)

    def test_fit_to_screen_preserves_aspect_ratio_with_letterboxing(self):
        source = Image.new("RGB", (1200, 400), "red")
        with patch.object(command, "load_source_image", return_value=source):
            rendered = command.fit_to_screen("unused.png", (1600, 1200), (255, 255, 255))
        self.assertEqual(rendered.size, (1600, 1200))
        self.assertEqual(rendered.getpixel((800, 100)), (255, 255, 255))
        self.assertEqual(rendered.getpixel((800, 600)), (255, 0, 0))

    def test_lumina_six_colour_profile_is_deterministic_and_palette_limited(self):
        source = Image.new("RGB", (600, 100))
        colours = list(command.LUMINA_SIX_COLOUR_PALETTE)
        for index, colour in enumerate(colours):
            for x in range(index * 100, (index + 1) * 100):
                for y in range(100):
                    source.putpixel((x, y), colour)
        device = {
            "screens": {
                "eink": {
                    "type": "eink",
                    "width": 1600,
                    "height": 1200,
                    "render_profile": "lumina_six_colour",
                }
            }
        }
        with (
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "existing_source_path", return_value="source.png"),
            patch.object(command, "load_source_image", return_value=source),
        ):
            first, mimetype, extension = command.render_for_screen("source.png", "eink", device)
            second, _mimetype, _extension = command.render_for_screen("source.png", "eink", device)
        self.assertEqual(first.getvalue(), second.getvalue())
        rendered = Image.open(BytesIO(first.getvalue()))
        self.assertEqual(rendered.size, (1600, 1200))
        self.assertEqual(rendered.mode, "P")
        self.assertEqual(rendered.format, "PNG")
        self.assertEqual(mimetype, "image/png")
        self.assertEqual(extension, "png")
        actual_colours = set(rendered.convert("RGB").getdata())
        self.assertEqual(actual_colours, set(colours))

    def test_nebular_six_colour_profile_uses_target_resolution_and_palette(self):
        source = Image.new("RGB", (1200, 800), (0, 255, 0))
        device = {
            "screens": {
                "eink": {
                    "type": "eink",
                    "width": 672,
                    "height": 960,
                    "render_profile": "six_colour_eink",
                }
            }
        }
        with (
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "existing_source_path", return_value="source.png"),
            patch.object(command, "load_source_image", return_value=source),
        ):
            output, mimetype, extension = command.render_for_screen("source.png", "eink", device)
        rendered = Image.open(BytesIO(output.getvalue()))
        self.assertEqual(rendered.size, (672, 960))
        self.assertEqual(rendered.mode, "P")
        self.assertEqual(mimetype, "image/png")
        self.assertEqual(extension, "png")
        self.assertLessEqual(set(rendered.convert("RGB").getdata()), set(command.SIX_COLOUR_EINK_PALETTE))

    def test_operator_can_choose_bw_or_six_colour_rendering_for_same_target(self):
        target = PushTarget("nebular", "Nebular", "SKU-N", 672, 960, render_profile="six_colour_eink")
        bw = command.esl_render_device(target, "bw")["screens"]["eink"]
        colour = command.esl_render_device(target, "six_colour")["screens"]["eink"]
        self.assertEqual((bw["width"], bw["height"]), (672, 960))
        self.assertEqual((colour["width"], colour["height"]), (672, 960))
        self.assertEqual(bw["render_profile"], "monochrome_eink")
        self.assertEqual(colour["render_profile"], "six_colour_eink")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            command.esl_render_device(target, "unapproved")

    def test_preview_acknowledgement_is_required_only_above_six_source_colours(self):
        target = PushTarget("nebular", "Nebular", "SKU-N", 672, 960, render_profile="six_colour_eink")
        six_colours = Image.new("RGB", (6, 1))
        for x, colour in enumerate(command.SIX_COLOUR_EINK_PALETTE):
            six_colours.putpixel((x, 0), colour)
        seven_colours = Image.new("RGB", (7, 1))
        for x in range(7):
            seven_colours.putpixel((x, 0), (x, x, x))
        with (
            patch.object(command, "existing_source_path", return_value="source.png"),
            patch.object(command, "load_source_image", return_value=six_colours),
        ):
            self.assertFalse(command.esl_media_requires_preview_acknowledgement("source.png", target))
        with (
            patch.object(command, "existing_source_path", return_value="source.png"),
            patch.object(command, "load_source_image", return_value=seven_colours),
        ):
            self.assertTrue(command.esl_media_requires_preview_acknowledgement("source.png", target))
        monochrome = PushTarget("mono", "Mono", "SKU-M", 672, 960, render_profile="monochrome_eink")
        self.assertFalse(command.esl_media_requires_preview_acknowledgement("source.png", monochrome))

    def test_material_colour_detection_ignores_jpeg_noise_but_flags_photos(self):
        target = PushTarget("nebular", "Nebular", "SKU-N", 672, 960, render_profile="six_colour_eink")
        with tempfile.TemporaryDirectory() as directory:
            artwork_path = os.path.join(directory, "artwork.jpg")
            artwork = Image.new("RGB", (300, 300), "black")
            for x in range(100, 200):
                for y in range(300):
                    artwork.putpixel((x, y), (255, 255, 255))
            for x in range(200, 300):
                for y in range(300):
                    artwork.putpixel((x, y), (0, 0, 255))
            artwork.save(artwork_path, "JPEG", quality=85)
            gradient_path = os.path.join(directory, "photo.jpg")
            gradient = Image.new("RGB", (256, 256))
            for x in range(256):
                for y in range(256):
                    gradient.putpixel((x, y), (x, y, (x + y) // 2))
            gradient.save(gradient_path, "JPEG", quality=90)
            with patch.object(command, "existing_source_path", return_value=artwork_path):
                self.assertFalse(command.esl_media_requires_preview_acknowledgement("artwork.jpg", target))
            with patch.object(command, "existing_source_path", return_value=gradient_path):
                self.assertTrue(command.esl_media_requires_preview_acknowledgement("photo.jpg", target))

    def test_monochrome_profile_remains_available(self):
        source = Image.new("RGB", (1600, 1200), (255, 0, 0))
        device = {
            "screens": {
                "eink": {
                    "type": "eink",
                    "width": 1600,
                    "height": 1200,
                    "render_profile": "monochrome_eink",
                }
            }
        }
        with (
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "existing_source_path", return_value="source.png"),
            patch.object(command, "load_source_image", return_value=source),
        ):
            rendered = command.render_screen_image("source.png", "eink", device)
        self.assertEqual(rendered.mode, "1")

    def test_default_profile_preserves_legacy_device_content_id(self):
        legacy_device = {
            "screens": {
                "eink": {"type": "eink", "width": 800, "height": 480, "color": False}
            }
        }
        explicit_monochrome = {
            "screens": {
                "eink": {
                    "type": "eink",
                    "width": 800,
                    "height": 480,
                    "color": False,
                    "render_profile": "monochrome_eink",
                }
            }
        }
        lumina_device = {
            "screens": {
                "eink": {
                    "type": "eink",
                    "width": 800,
                    "height": 480,
                    "color": False,
                    "render_profile": "lumina_six_colour",
                }
            }
        }
        with patch.object(command, "source_version", return_value="unchanged-source"):
            legacy_id = command.screen_content_id("live.png", "eink", legacy_device)
            monochrome_id = command.screen_content_id("live.png", "eink", explicit_monochrome)
            lumina_id = command.screen_content_id("live.png", "eink", lumina_device)
        self.assertEqual(legacy_id, monochrome_id)
        self.assertNotEqual(legacy_id, lumina_id)

    def test_esl_preview_uses_existing_renderer_at_target_dimensions(self):
        rendered = BytesIO(b"preview-png")
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "render_for_screen", return_value=(rendered, "image/png", "png")) as render,
        ):
            response = self.client.get("/esl/preview/lumina-a/vehicle.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"preview-png")
        render_device = render.call_args.args[2]
        self.assertEqual(render_device["screens"]["eink"]["width"], 1600)
        self.assertEqual(render_device["screens"]["eink"]["height"], 1200)

    def test_push_renders_for_target_and_reports_acceptance_not_completion(self):
        result = {
            "batch_no": "SHYFTED-B1",
            "provider_status": "accepted",
            "physical_display_confirmed": False,
            "result_code": 1001,
            "target_ids": ["lab"],
        }
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "record_push_job") as record,
            patch.object(command, "update_push_job") as update,
            patch.object(command, "render_for_screen", return_value=(BytesIO(b"rendered-png"), "image/png", "png")) as render,
            patch.object(command, "validate_rendered_esl_payload"),
            patch.object(command, "submit_esl_push", return_value=result) as submit,
            patch.object(command, "clear_esl_staged_asset") as clear_staged,
        ):
            response = self.client.post(
                "/esl/push",
                data={"csrf_token": "csrf", "file": "vehicle.png", "target_id": "lumina-a", "render_mode": "bw"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/esl/lumina-a")
        self.assertEqual(record.call_args.args[0]["targets"], [{"id": "lumina-a", "label": "Showroom Display 1"}])
        render_device = render.call_args.args[2]
        self.assertEqual(render_device["screens"]["eink"]["width"], 1600)
        self.assertEqual(render_device["screens"]["eink"]["render_profile"], "monochrome_eink")
        submit.assert_called_once()
        submitted_target = submit.call_args.args[1][0]
        self.assertEqual(submit.call_args.args[0], b"rendered-png")
        self.assertEqual(submitted_target.id, self.target.id)
        self.assertEqual(submitted_target.sku, self.target.sku)
        self.assertEqual(submitted_target.label, "Showroom Display 1")
        final_update = update.call_args_list[-1].kwargs
        self.assertEqual(final_update["status"], "accepted")
        self.assertEqual(final_update["status_label"], "Update sent")
        self.assertFalse(final_update["physical_display_confirmed"])
        clear_staged.assert_called_once_with("lumina-a", "vehicle.png")

    def test_push_failure_is_translated_for_customer(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "record_push_job"),
            patch.object(command, "update_push_job") as update,
            patch.object(command, "render_for_screen", return_value=(BytesIO(b"rendered-png"), "image/png", "png")),
            patch.object(command, "validate_rendered_esl_payload"),
            patch.object(command, "submit_esl_push", side_effect=command.HanshowError("resultCode=9999 provider detail")),
            patch.object(command, "clear_esl_staged_asset") as clear_staged,
        ):
            response = self.client.post(
                "/esl/push",
                data={"csrf_token": "csrf", "file": "vehicle.png", "target_id": "lumina-a", "preview_acknowledged": "yes"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        final_update = update.call_args_list[-1].kwargs
        self.assertEqual(final_update["status"], "failed")
        self.assertEqual(final_update["status_label"], "Failed")
        self.assertNotIn("resultCode", final_update["error"])
        clear_staged.assert_not_called()

    def test_final_payload_validation_blocks_submit_when_route_is_bypassed(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "record_push_job"),
            patch.object(command, "update_push_job") as update,
            patch.object(command, "render_for_screen", return_value=(BytesIO(b"not-a-valid-png"), "image/png", "png")),
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/push",
                data={"csrf_token": "csrf", "file": "vehicle.png", "target_id": "lumina-a", "preview_acknowledged": "yes"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        self.assertEqual(update.call_args_list[-1].kwargs["status"], "failed")
        submit.assert_not_called()

    def test_workspace_push_uses_only_active_targets_server_side_staged_asset(self):
        result = {"batch_no": "B2", "physical_display_confirmed": False}
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "get_esl_staged_asset", return_value="staged.png"),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "targets_from_environment", return_value=[self.target]),
            patch.object(command, "record_push_job") as record,
            patch.object(command, "update_push_job"),
            patch.object(command, "render_for_screen", return_value=(BytesIO(b"rendered"), "image/png", "png")),
            patch.object(command, "validate_rendered_esl_payload"),
            patch.object(command, "submit_esl_push", return_value=result),
            patch.object(command, "clear_esl_staged_asset") as clear,
        ):
            response = self.client.post(
                "/esl/lumina-a/push",
                data={"csrf_token": "csrf", "file": "wrong-target.png", "target_id": "other", "preview_acknowledged": "yes"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        self.assertEqual(record.call_args.args[0]["asset"], "staged.png")
        self.assertEqual(record.call_args.args[0]["targets"][0]["id"], "lumina-a")
        clear.assert_called_once_with("lumina-a", "staged.png")

    def test_push_requires_rendered_preview_acknowledgement_server_side(self):
        colour_target = PushTarget(
            "lumina-a", "Lab Lumina BF", "SKU-1", 1600, 1200,
            render_profile="six_colour_eink",
        )
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "get_esl_staged_asset", return_value="photo.png"),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "targets_from_environment", return_value=[colour_target]),
            patch.object(command, "esl_media_compatibility", return_value={"compatible": True, "reason": "Ready."}),
            patch.object(command, "esl_media_requires_preview_acknowledgement", return_value=True),
            patch.object(command, "record_push_job") as record,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/lumina-a/push",
                data={"csrf_token": "csrf"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        record.assert_not_called()
        submit.assert_not_called()

    def test_push_rejects_unapproved_render_treatment_server_side(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "record_push_job") as record,
            patch.object(command, "submit_esl_push") as submit,
        ):
            response = self.client.post(
                "/esl/lumina-a/push",
                data={"csrf_token": "csrf", "render_mode": "full_colour"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/esl/lumina-a")
        record.assert_not_called()
        submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
