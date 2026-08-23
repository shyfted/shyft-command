import base64
import json
import os
import unittest
from unittest.mock import patch

from hanshow_integration import (
    HanshowClient,
    HanshowConfig,
    HanshowError,
    PushTarget,
    build_integration_payload,
    submit,
    targets_from_environment,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return next(self.responses)


class HanshowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.config = HanshowConfig("https://example.test", "client", "secret", "ausnz", "017")
        self.target = PushTarget("lab", "Lab ESL", "SKU-1", 960, 672)

    def test_payload_preserves_rendered_bytes_in_rsrv_blob(self):
        rendered = b"\x89PNG\r\n\x1a\nrendered"
        payload = build_integration_payload(self.config, "B1", "SKU-1", rendered)
        self.assertEqual(base64.b64decode(payload["items"][0]["rsrvBlob"]), rendered)
        self.assertEqual(payload["items"][0]["sku"], "SKU-1")

    def test_submit_uses_proven_auth_and_acceptance_contract(self):
        accepted = {"resultCode": 1001, "result": "succeed", "message": "succeed", "data": "INTEGRATION_CODE_SUCCESS"}
        transport = FakeTransport([
            (200, b'{"access_token":"token","token_type":"Bearer"}'),
            (200, json.dumps(accepted).encode()),
        ])
        result = submit(b"\x89PNG\r\n\x1a\nrendered", [self.target], HanshowClient(self.config, transport))
        self.assertEqual(result["provider_status"], "accepted")
        self.assertFalse(result["physical_display_confirmed"])
        self.assertEqual(transport.requests[0].full_url, "https://example.test/proxy/token")
        self.assertEqual(transport.requests[1].full_url, "https://example.test/proxy/integration/ausnz/017")

    def test_non_documented_success_shape_is_a_failure(self):
        transport = FakeTransport([(200, b'{"resultCode":1001,"result":"succeed","data":"other"}')])
        payload = build_integration_payload(self.config, "B1", "SKU-1", b"image")
        with self.assertRaises(HanshowError):
            HanshowClient(self.config, transport).integrate("token", payload)

    def test_current_release_rejects_multiple_targets_before_network(self):
        transport = FakeTransport([])
        with self.assertRaisesRegex(ValueError, "Exactly one"):
            submit(b"image", [self.target, self.target], HanshowClient(self.config, transport))
        self.assertEqual(transport.requests, [])

    def test_targets_are_server_side_and_validated(self):
        value = '[{"id":"lab","label":"Lab ESL","sku":"SKU-1","width":960,"height":672}]'
        with patch.dict(os.environ, {"SHYFT_ESL_TARGETS": value}):
            self.assertEqual(targets_from_environment(), [self.target])
        with patch.dict(os.environ, {"SHYFT_ESL_TARGETS": "{}"}):
            with self.assertRaisesRegex(HanshowError, "must be a list"):
                targets_from_environment()

    def test_targets_accept_only_known_render_profiles(self):
        value = '[{"id":"lumina","label":"Lumina","sku":"SKU-1","width":1600,"height":1200,"render_profile":"lumina_six_colour"}]'
        with patch.dict(os.environ, {"SHYFT_ESL_TARGETS": value}):
            self.assertEqual(targets_from_environment()[0].render_profile, "lumina_six_colour")
        invalid = '[{"id":"lumina","label":"Lumina","sku":"SKU-1","width":1600,"height":1200,"render_profile":"unknown"}]'
        with patch.dict(os.environ, {"SHYFT_ESL_TARGETS": invalid}):
            with self.assertRaisesRegex(HanshowError, "invalid"):
                targets_from_environment()


if __name__ == "__main__":
    unittest.main()
