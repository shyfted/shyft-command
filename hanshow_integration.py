"""Hanshow delivery adapter used by Shyft Command.

The HTTP contract intentionally mirrors the proven client under
``devices/hanshow/integration``.  Product-facing code calls ``submit`` with a
rendered asset and targets; this module owns all Hanshow-specific details.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable


class HanshowError(RuntimeError):
    """A safe-to-display Hanshow request or response failure."""


@dataclass(frozen=True)
class HanshowConfig:
    base_url: str
    client_id: str
    client_secret: str
    customer_code: str
    store_code: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name in ("base_url", "client_id", "client_secret", "customer_code", "store_code"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class PushTarget:
    id: str
    label: str
    sku: str
    width: int
    height: int
    rotation: int = 0
    render_profile: str = "monochrome_eink"


Transport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _default_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        raise HanshowError(f"Display service connection failed: {error.reason}") from error


def config_from_environment() -> HanshowConfig:
    return HanshowConfig(
        base_url=os.environ.get("HANSHOW_BASE_URL", "https://ausnz-tst-allstar.hanshowcloud.net"),
        client_id=os.environ.get("HANSHOW_CLIENT_ID", "guest"),
        client_secret=os.environ.get("HANSHOW_CLIENT_SECRET", ""),
        customer_code=os.environ.get("HANSHOW_CUSTOMER_CODE", "ausnz"),
        store_code=os.environ.get("HANSHOW_STORE_CODE", "017"),
        timeout_seconds=float(os.environ.get("HANSHOW_TIMEOUT_SECONDS", "30")),
    )


def targets_from_environment() -> list[PushTarget]:
    raw = os.environ.get("SHYFT_ESL_TARGETS", "[]")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HanshowError("ESL target configuration is invalid") from error
    if not isinstance(values, list):
        raise HanshowError("ESL target configuration must be a list")

    targets = []
    seen = set()
    seen_skus = set()
    for value in values:
        try:
            target = PushTarget(
                id=str(value["id"]).strip(),
                label=str(value["label"]).strip(),
                sku=str(value["sku"]).strip(),
                width=int(value["width"]),
                height=int(value["height"]),
                rotation=int(value.get("rotation", 0)) % 360,
                render_profile=str(value.get("render_profile", "monochrome_eink")).strip(),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HanshowError("ESL target configuration is invalid") from error
        if (
            not target.id
            or not target.label
            or not target.sku
            or target.width <= 0
            or target.height <= 0
            or target.render_profile not in {"monochrome_eink", "lumina_six_colour", "six_colour_eink"}
        ):
            raise HanshowError("ESL target configuration is invalid")
        if target.id in seen:
            raise HanshowError("ESL target identifiers must be unique")
        sku_key = target.sku.casefold()
        if sku_key in seen_skus:
            raise HanshowError(
                f"ESL target configuration is unsafe: article SKU {target.sku} is assigned to more than one display"
            )
        seen.add(target.id)
        seen_skus.add(sku_key)
        targets.append(target)
    return targets


def build_integration_payload(config: HanshowConfig, batch_no: str, sku: str, image: bytes) -> dict[str, Any]:
    if not batch_no or not sku or not image:
        raise ValueError("batch_no, sku and rendered image are required")
    return {
        "storeCode": config.store_code,
        "customerStoreCode": config.customer_code,
        "batchNo": batch_no,
        "items": [{"sku": sku, "rsrvBlob": base64.b64encode(image).decode("ascii")}],
    }


class HanshowClient:
    def __init__(self, config: HanshowConfig, transport: Transport = _default_transport):
        self.config = config
        self._transport = transport

    def _json_request(self, path: str, authorization: str, payload=None) -> tuple[int, dict[str, Any]]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": authorization, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}{path}",
            data=body if body is not None else b"",
            headers=headers,
            method="POST",
        )
        status, raw = self._transport(request, self.config.timeout_seconds)
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HanshowError(f"Display service returned an invalid response (HTTP {status})") from error
        if not isinstance(response, dict):
            raise HanshowError(f"Display service returned an invalid response (HTTP {status})")
        return status, response

    def obtain_access_token(self) -> str:
        credentials = f"{self.config.client_id}:{self.config.client_secret}".encode("utf-8")
        basic = base64.b64encode(credentials).decode("ascii")
        status, response = self._json_request("/proxy/token", f"Basic {basic}")
        token = response.get("access_token")
        if status != 200 or not isinstance(token, str) or not token or response.get("token_type") != "Bearer":
            raise HanshowError(self._failure_message("authentication", status, response))
        return token

    def integrate(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("storeCode") != self.config.store_code:
            raise ValueError("payload storeCode does not match configured store code")
        if payload.get("customerStoreCode") != self.config.customer_code:
            raise ValueError("payload customerStoreCode does not match configured customer code")
        path = f"/proxy/integration/{self.config.customer_code}/{self.config.store_code}"
        status, response = self._json_request(path, f"Bearer {token}", payload)
        accepted = (
            status == 200
            and response.get("resultCode") == 1001
            and response.get("result") == "succeed"
            and response.get("data") == "INTEGRATION_CODE_SUCCESS"
        )
        if not accepted:
            raise HanshowError(self._failure_message("submission", status, response))
        return response

    @staticmethod
    def _failure_message(operation: str, status: int, response: dict[str, Any]) -> str:
        return "; ".join([
            f"Display service {operation} failed (HTTP {status})",
            f"resultCode={response.get('resultCode', 'missing')}",
            f"result={response.get('result', 'missing')}",
            f"message={response.get('message', 'missing')}",
        ])


def submit(rendered_image: bytes, targets: list[PushTarget], client: HanshowClient | None = None) -> dict[str, Any]:
    """Submit a push job. Current UI supplies exactly one target."""
    if len(targets) != 1:
        raise ValueError("Exactly one ESL target is supported in this release")
    target = targets[0]
    client = client or HanshowClient(config_from_environment())
    batch_no = f"SHYFTED-{uuid.uuid4().hex[:20].upper()}"
    payload = build_integration_payload(client.config, batch_no, target.sku, rendered_image)
    token = client.obtain_access_token()
    response = client.integrate(token, payload)
    return {
        "batch_no": batch_no,
        "provider_status": "accepted",
        "physical_display_confirmed": False,
        "result_code": response["resultCode"],
        "target_ids": [target.id],
    }
