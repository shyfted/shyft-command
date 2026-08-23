import os
import unittest
from unittest.mock import patch

os.environ.setdefault("AUTH_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

import app as command


class DeviceWorkflowTests(unittest.TestCase):
    def setUp(self):
        command.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = command.app.test_client()
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        self.user = {"id": 1, "name": "Test", "email": "test@example.com", "role": "staff"}

    @staticmethod
    def card(index):
        return {
            "id": f"device-{index}", "name": f"Device {index}", "status": "online",
            "last_seen": "2026-08-23T01:00:00Z", "battery": None,
            "screens": {"lcd": {}, "eink": {}},
            "lcd": {"file": None, "thumb_url": None},
            "eink": {"file": None, "thumb_url": None},
        }

    def test_device_cards_open_dedicated_workspaces_and_scale_search_is_present(self):
        cards = [self.card(index) for index in range(100)]
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "list_uploads", return_value=[]),
            patch.object(command, "device_cards", return_value=cards),
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/device/device-0"', response.data)
        self.assertIn(b'href="/device/device-99"', response.data)
        self.assertEqual(response.data.count(b"data-device-card data-search-text=\"Device"), 100)
        self.assertIn(b"Search devices", response.data)

    def test_device_workspace_has_breadcrumb_back_live_and_staged_context(self):
        workspace = {
            "id": "franky", "name": "Franky", "status": "online", "last_seen": "now",
            "battery": "90%", "hostname": "franky", "client_version": "3",
            "screens": {"lcd": {}, "eink": {}},
            "live": {"lcd": "live-lcd.png", "eink": "live-eink.png"},
            "selection": {"lcd": "next-lcd.png", "eink": None},
            "lcd": {"file": "live-lcd.png", "thumb_url": "/live-lcd"},
            "eink": {"file": "live-eink.png", "thumb_url": "/live-eink"},
            "selected_lcd": {"file": "next-lcd.png", "thumb_url": "/next-lcd"},
            "selected_eink": {"file": None, "thumb_url": None},
        }
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "device_view_model", return_value=workspace),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "list_uploads", return_value=[]),
        ):
            response = self.client.get("/device/franky")
        self.assertIn(b'<div class="workspace-nav"><a href="/">\xe2\x86\x90 Devices</a><span>Franky</span></div>', response.data)
        self.assertRegex(response.get_data(as_text=True), r'<button class="push"[^>]*>PUSH</button>')
        self.assertIn(b"live-lcd.png", response.data)
        self.assertIn(b"live-eink.png", response.data)
        self.assertNotIn(b"confirm('PUSH", response.data)

    def test_selecting_franky_content_does_not_touch_petey(self):
        device = {"name": "Franky", "screens": {"lcd": {}}}
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "get_device", return_value=device),
            patch.object(command, "upload_exists", return_value=True),
            patch.object(command, "set_device_selection") as select,
        ):
            response = self.client.post(
                "/device/franky/select_lcd",
                data={"csrf_token": "csrf", "file": "next.png"},
                follow_redirects=False,
            )
        self.assertEqual(response.location, "/device/franky")
        select.assert_called_once_with("franky", lcd="next.png")

    def test_media_settings_and_auth_routes_remain_available(self):
        with (
            patch.object(command, "current_user", return_value=self.user),
            patch.object(command, "device_cards", return_value=[]),
            patch.object(command, "list_uploads", return_value=[]),
        ):
            self.assertEqual(self.client.get("/media").status_code, 200)
            self.assertEqual(self.client.get("/settings").status_code, 200)
        anonymous = command.app.test_client()
        self.assertEqual(anonymous.get("/media").status_code, 302)


if __name__ == "__main__":
    unittest.main()
