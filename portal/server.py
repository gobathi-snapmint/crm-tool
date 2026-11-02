#!/usr/bin/env python3
"""
Snapmint CRM Campaign Calendar Portal - local proxy & pipeline server.

Run with zero dependencies (Python 3.9+ standard library only):
    python3 portal/server.py

What it does
1. Serves the portal UI at http://127.0.0.1:8000 (bound to loopback only).
2. Holds every vendor credential server-side (env vars) - the browser never sees keys.
3. Runs the deterministic 2-step WhatsApp pipeline:
     Step 1  validate -> submit template to WSP / Meta Graph -> receive status via signed webhook
     Step 2  stage the APPROVED template for WebEngage (registration packet + human confirm)
4. Verifies SMS DLT templates (human enters DLT ID + approved text; we SHA-256 lock it).
5. Hosts the single Content Agent (Claude Sonnet on Bedrock ap-south-1) - optional,
   needs `pip install anthropic`; without it a deterministic stub is used.

Governance enforced here (not just in the UI):
- No endpoint can launch a campaign. The pipeline stops at "staged in WebEngage".
- Content Agent input is PII-scrubbed before it leaves this process.
- Bedrock model IDs that route cross-region (global./apac./us./eu.) are rejected.

Modes (env PIPELINE_MODE):
  simulate (default)  WSP + Meta are simulated; the simulated Meta webhook is HMAC-signed
                      and goes through the same verification code as a real one.
  live                Calls Meta Graph API (WSP_PROVIDER=meta_cloud) or a WSP endpoint
                      (WSP_PROVIDER=trustsignal / route_mobile) configured by env.
"""

import base64
import hashlib
import hmac
import http.server
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PORTAL_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "pipeline_state.json")

# ---------------------------------------------------------------------------
# Configuration (all secrets come from the environment, never from the browser)
# ---------------------------------------------------------------------------
CFG = {
    "mode": os.environ.get("PIPELINE_MODE", "simulate"),
    "wsp_provider": os.environ.get("WSP_PROVIDER", "trustsignal"),  # trustsignal | route_mobile | meta_cloud
    # Meta Cloud API (documented contract: POST /{WABA_ID}/message_templates)
    "meta_graph_version": os.environ.get("META_GRAPH_VERSION", "v23.0"),
    "meta_waba_id": os.environ.get("META_WABA_ID", ""),
    "meta_app_id": os.environ.get("META_APP_ID", ""),
    "meta_token": os.environ.get("META_SYSTEM_USER_TOKEN", ""),
    "meta_app_secret": os.environ.get("META_APP_SECRET", "local-sim-app-secret"),
    "meta_verify_token": os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "local-sim-verify-token"),
    # WSP template API - URL/auth are configurable because neither TrustSignal nor
    # Route Mobile publishes its WhatsApp template-management contract publicly.
    "wsp_template_url": os.environ.get("WSP_TEMPLATE_URL", ""),
    "wsp_api_key": os.environ.get("WSP_API_KEY", ""),
    "wsp_auth_style": os.environ.get("WSP_AUTH_STYLE", "bearer"),  # bearer | header | query
    "wsp_webhook_secret": os.environ.get("WSP_WEBHOOK_SECRET", ""),
    # WebEngage - no public template API; optional private endpoint if WebEngage provides one
    "we_license_code": os.environ.get("WEBENGAGE_LICENSE_CODE", ""),
    "we_template_api_url": os.environ.get("WEBENGAGE_TEMPLATE_API_URL", ""),
    "we_api_key": os.environ.get("WEBENGAGE_API_KEY", ""),
    "we_wsp_name": os.environ.get("WEBENGAGE_WSP_NAME", "TrustSignal (Private WSP)"),
    # Content Agent
    "bedrock_region": os.environ.get("BEDROCK_REGION", "ap-south-1"),
    "bedrock_model": os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-5-5"),
    "agent_enabled": os.environ.get("CONTENT_AGENT_ENABLED", "0") == "1",
    "sim_approval_seconds": float(os.environ.get("SIM_APPROVAL_SECONDS", "6")),
}

STATE_LOCK = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"templates": {}, "dlt": {}, "audit": []}


def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def audit(state, event, **fields):
    state["audit"].append({"at": now_iso(), "event": event, **fields})
    state["audit"] = state["audit"][-500:]


# ---------------------------------------------------------------------------
# Deterministic validation (Meta WhatsApp template rules + Snapmint policy)
# ---------------------------------------------------------------------------
VAR_RE = re.compile(r"\{\{(\d+)\}\}")
NAME_RE = re.compile(r"^[a-z0-9_]{1,512}$")
PROMO_WORDS = re.compile(r"\b(offer|cashback|discount|sale|deal|free|% off|limited time|hurry|upgrade|exclusive)\b", re.I)

PII_PATTERNS = [
    ("phone", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("aadhaar", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
]


def find_pii(text):
    hits = []
    for label, pat in PII_PATTERNS:
        if pat.search(text or ""):
            hits.append(label)
    return hits


def scrub_pii(text):
    out = text or ""
    for label, pat in PII_PATTERNS:
        out = pat.sub(f"[{label.upper()}_REDACTED]", out)
    return out


def validate_whatsapp(t):
    """Return {ok, errors[], warnings[]} for a WhatsApp template spec."""
    errors, warnings = [], []
    name = t.get("template_name", "")
    body = t.get("body", "")
    category = t.get("category", "")
    cta = t.get("cta_text", "")
    url = t.get("target_url", "")
    banner = t.get("banner_url", "")
    examples = t.get("body_examples") or []

    if not NAME_RE.match(name):
        errors.append("Template name must be lowercase letters, digits and underscores only (Meta rule).")
    if category not in ("MARKETING", "UTILITY"):
        errors.append("Category must be MARKETING or UTILITY.")
    if not body.strip():
        errors.append("Body (Comms B) is empty.")
    if len(body) > 1024:
        errors.append(f"Body is {len(body)} chars; Meta limit is 1024.")

    nums = [int(n) for n in VAR_RE.findall(body)]
    distinct = sorted(set(nums))
    if distinct and distinct != list(range(1, len(distinct) + 1)):
        errors.append(f"Variables must be sequential from {{{{1}}}} with no gaps; found {distinct}.")
    stripped = body.strip()
    if VAR_RE.match(stripped) or re.search(r"\{\{\d+\}\}$", stripped):
        errors.append("Body must not start or end with a variable (Meta rejects these).")
    elif re.search(r"\{\{\d+\}\}[.!?]$", stripped):
        warnings.append("Body ends with a variable followed only by punctuation; add closing words to avoid rejection.")
    if distinct and len(examples) < len(distinct):
        errors.append(f"Provide one sample value per variable ({len(distinct)} needed, {len(examples)} given).")
    if distinct and len(stripped.split()) < 3 * len(distinct):
        warnings.append("High variable-to-text ratio; Meta often rejects templates that are mostly variables.")
    if re.search(r"\{\{[^0-9}]+\}\}", body):
        errors.append("Only numbered variables like {{1}} are allowed.")

    if cta:
        if len(cta) > 25:
            errors.append(f"CTA text is {len(cta)} chars; Meta limit is 25.")
        if not url:
            errors.append("CTA button needs a Target URL.")
    if url:
        if not url.startswith("https://"):
            errors.append("Target URL must be https://.")
        if len(url) > 2000:
            errors.append("Target URL exceeds 2000 chars.")
        if "{{" in url and not url.endswith("{{1}}"):
            errors.append("A dynamic URL may contain only one variable, {{1}}, at the very end.")
    if banner:
        if not banner.startswith("https://"):
            errors.append("Banner URL must be https:// so Meta/WSP can fetch it.")
        if not re.search(r"\.(png|jpe?g)(\?.*)?$", banner, re.I):
            warnings.append("Header image should be PNG or JPEG (max 5 MB).")

    if category == "UTILITY" and PROMO_WORDS.search(body):
        warnings.append("UTILITY body contains promotional words; Meta may re-categorise it as MARKETING (higher price).")
    pii = find_pii(body + " " + url)
    if pii:
        errors.append(f"Template text looks like it contains customer PII ({', '.join(pii)}). Use variables instead.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def build_meta_payload(t, header_handle=None):
    """Meta Graph API template payload (also what most WSPs forward 1:1)."""
    body = t["body"]
    components = []
    if t.get("banner_url"):
        components.append({
            "type": "HEADER",
            "format": "IMAGE",
            # Meta needs a resumable-upload handle; WSPs usually accept the public URL.
            "example": {"header_handle": [header_handle or t["banner_url"]]},
        })
    body_comp = {"type": "BODY", "text": body}
    if VAR_RE.search(body):
        body_comp["example"] = {"body_text": [list(t.get("body_examples") or [])]}
    components.append(body_comp)
    if t.get("footer"):
        components.append({"type": "FOOTER", "text": t["footer"][:60]})
    if t.get("cta_text") and t.get("target_url"):
        btn = {"type": "URL", "text": t["cta_text"], "url": t["target_url"]}
        if t["target_url"].endswith("{{1}}"):
            btn["example"] = [t["target_url"].replace("{{1}}", t.get("url_example_suffix") or "sample123")]
        components.append({"type": "BUTTONS", "buttons": [btn]})
    return {
        "name": t["template_name"],
        "language": t.get("language", "en"),
        "category": t["category"],
        "components": components,
    }


# ---------------------------------------------------------------------------
# HTTP helpers for outbound calls
# ---------------------------------------------------------------------------
def http_json(method, url, payload=None, headers=None, raw_body=None, timeout=30):
    data = raw_body if raw_body is not None else (json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"raw": text}
    except urllib.error.URLError as e:
        return 502, {"error": f"Upstream unreachable: {e.reason}"}


def meta_upload_header_image(image_url):
    """Meta Resumable Upload API -> header_handle. Live meta_cloud mode only."""
    with urllib.request.urlopen(image_url, timeout=30) as r:
        blob = r.read()
        ctype = r.headers.get_content_type() or "image/png"
    v, app_id, tok = CFG["meta_graph_version"], CFG["meta_app_id"], CFG["meta_token"]
    q = urllib.parse.urlencode({"file_length": len(blob), "file_type": ctype, "access_token": tok})
    status, sess = http_json("POST", f"https://graph.facebook.com/{v}/{app_id}/uploads?{q}")
    if status != 200 or "id" not in sess:
        raise RuntimeError(f"Upload session failed: {sess}")
    req = urllib.request.Request(f"https://graph.facebook.com/{v}/{sess['id']}", data=blob, method="POST")
    req.add_header("Authorization", f"OAuth {tok}")
    req.add_header("file_offset", "0")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["h"]


def wsp_auth(url):
    key = CFG["wsp_api_key"]
    if CFG["wsp_auth_style"] == "query":
        sep = "&" if "?" in url else "?"
        return url + sep + urllib.parse.urlencode({"api_key": key}), {}
    if CFG["wsp_auth_style"] == "header":
        return url, {"X-API-Key": key}
    return url, {"Authorization": f"Bearer {key}"}


# ---------------------------------------------------------------------------
# Webhook handling (Meta format; WSP relays normally forward the same shape)
# ---------------------------------------------------------------------------
def sign_body(raw, secret):
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def verify_signature(raw, header_value, secrets):
    if not header_value:
        return False
    for s in secrets:
        if s and hmac.compare_digest(sign_body(raw, s), header_value.strip()):
            return True
    return False


def apply_template_webhook(payload):
    """Apply message_template_status_update / template_category_update events."""
    applied = []
    with STATE_LOCK:
        state = load_state()
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                field, v = change.get("field"), change.get("value", {})
                name = v.get("message_template_name")
                rec = state["templates"].get(name)
                if not rec:
                    continue
                if field == "message_template_status_update":
                    rec["status"] = v.get("event", rec["status"])  # APPROVED | REJECTED | PAUSED | DISABLED ...
                    rec["reason"] = v.get("reason")
                    rec["meta_template_id"] = v.get("message_template_id", rec.get("meta_template_id"))
                elif field == "template_category_update":
                    rec["category"] = v.get("new_category", rec["category"])
                    rec["reason"] = f"Meta re-categorised from {v.get('previous_category')} to {v.get('new_category')}"
                rec["updated_at"] = now_iso()
                rec.setdefault("history", []).append({"at": now_iso(), "field": field, "value": v})
                audit(state, "webhook", template=name, field=field, value=v.get("event") or v.get("new_category"))
                applied.append(name)
        save_state(state)
    return applied


def simulate_meta_review(template_name, waba_id):
    """Simulated Meta review: POSTs a signed webhook to ourselves after a delay."""
    def fire():
        with STATE_LOCK:
            rec = load_state()["templates"].get(template_name, {})
        validation = validate_whatsapp(rec.get("spec", {}))
        event = "APPROVED" if validation["ok"] else "REJECTED"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": waba_id or "SIM_WABA_ID",
                "time": int(time.time()),
                "changes": [{
                    "field": "message_template_status_update",
                    "value": {
                        "event": event,
                        "message_template_id": rec.get("meta_template_id"),
                        "message_template_name": template_name,
                        "message_template_language": rec.get("spec", {}).get("language", "en"),
                        "reason": "NONE" if event == "APPROVED" else "INVALID_FORMAT",
                    },
                }],
            }],
        }
        raw = json.dumps(payload).encode()
        http_json("POST", f"http://127.0.0.1:{PORT}/webhooks/whatsapp", raw_body=raw,
                  headers={"X-Hub-Signature-256": sign_body(raw, CFG["meta_app_secret"])})
    threading.Timer(CFG["sim_approval_seconds"], fire).start()


# ---------------------------------------------------------------------------
# Step 1 - submit template for approval
# ---------------------------------------------------------------------------
def submit_template(spec):
    validation = validate_whatsapp(spec)
    if not validation["ok"]:
        return 422, {"status": "VALIDATION_FAILED", "validation": validation}

    name = spec["template_name"]
    with STATE_LOCK:
        state = load_state()
        existing = state["templates"].get(name)
        if existing and existing["status"] in ("PENDING", "APPROVED"):
            # Idempotency: Meta rejects duplicate names; never double-submit.
            return 409, {"status": "ALREADY_SUBMITTED", "template": existing}

    provider, mode = CFG["wsp_provider"], CFG["mode"]
    request_payload = build_meta_payload(spec)
    upstream = {"mode": mode, "provider": provider}

    if mode == "simulate":
        meta_id = str(abs(hash(name)) % 10**15)
        upstream.update({"http_status": 200, "response": {"id": meta_id, "status": "PENDING", "category": spec["category"]}})
    elif provider == "meta_cloud":
        if not (CFG["meta_waba_id"] and CFG["meta_token"]):
            return 400, {"status": "CONFIG_MISSING", "error": "Set META_WABA_ID and META_SYSTEM_USER_TOKEN."}
        if spec.get("banner_url"):
            try:
                request_payload = build_meta_payload(spec, meta_upload_header_image(spec["banner_url"]))
            except Exception as e:  # noqa: BLE001 - surface upstream failure to the user
                return 502, {"status": "HEADER_UPLOAD_FAILED", "error": str(e)}
        url = f"https://graph.facebook.com/{CFG['meta_graph_version']}/{CFG['meta_waba_id']}/message_templates"
        code, resp = http_json("POST", url, request_payload, {"Authorization": f"Bearer {CFG['meta_token']}"})
        upstream.update({"http_status": code, "response": resp})
        if code != 200:
            return code, {"status": "UPSTREAM_ERROR", "upstream": upstream}
        meta_id = resp.get("id")
    else:
        if not (CFG["wsp_template_url"] and CFG["wsp_api_key"]):
            return 400, {"status": "CONFIG_MISSING",
                         "error": "Set WSP_TEMPLATE_URL and WSP_API_KEY (contract from TrustSignal/Route Mobile account team)."}
        url, headers = wsp_auth(CFG["wsp_template_url"])
        code, resp = http_json("POST", url, {"waba_id": CFG["meta_waba_id"], **request_payload}, headers)
        upstream.update({"http_status": code, "response": resp})
        if code not in (200, 201, 202):
            return code, {"status": "UPSTREAM_ERROR", "upstream": upstream}
        meta_id = resp.get("id") or resp.get("template_id") or (resp.get("data") or {}).get("template_id")

    with STATE_LOCK:
        state = load_state()
        state["templates"][name] = {
            "template_name": name,
            "status": "PENDING",
            "category": spec["category"],
            "provider": provider,
            "meta_template_id": meta_id,
            "spec": spec,
            "submitted_at": now_iso(),
            "updated_at": now_iso(),
            "webengage": None,
            "history": [],
        }
        audit(state, "submitted", template=name, provider=provider, mode=mode)
        save_state(state)

    if mode == "simulate":
        simulate_meta_review(name, CFG["meta_waba_id"])

    return 200, {"status": "PENDING", "template_name": name, "meta_template_id": meta_id,
                 "request_payload": request_payload, "upstream": upstream, "validation": validation}


# ---------------------------------------------------------------------------
# Step 2 - stage approved template for WebEngage
# ---------------------------------------------------------------------------
def webengage_packet(rec):
    spec = rec["spec"]
    return {
        "wsp": CFG["we_wsp_name"],
        "template_name": rec["template_name"],
        "template_text": spec["body"],
        "template_language": spec.get("language", "en"),
        "template_namespace": f"{spec.get('namespace', 'snapmint')}:{rec['template_name']}",
        "category": rec["category"],
        "header": {"type": "IMAGE", "url": spec.get("banner_url")} if spec.get("banner_url") else None,
        "button": {"type": "URL", "text": spec.get("cta_text"), "url": spec.get("target_url")} if spec.get("cta_text") else None,
        "variable_count": len(set(VAR_RE.findall(spec["body"]))),
    }


def stage_webengage(name):
    with STATE_LOCK:
        rec = load_state()["templates"].get(name)
    if not rec:
        return 404, {"error": f"Unknown template {name}"}
    if rec["status"] != "APPROVED":
        return 409, {"error": f"Template is {rec['status']}; only APPROVED templates can go to WebEngage."}

    packet = webengage_packet(rec)
    result = {"packet": packet, "mode": "manual"}

    if CFG["we_template_api_url"] and CFG["we_api_key"] and CFG["mode"] == "live":
        url = CFG["we_template_api_url"].replace("{license_code}", CFG["we_license_code"])
        code, resp = http_json("POST", url, packet, {"Authorization": f"Bearer {CFG['we_api_key']}"})
        result.update({"mode": "api", "http_status": code, "response": resp})
        if code not in (200, 201):
            return code, {"status": "UPSTREAM_ERROR", **result}
        we_status, we_id = "WE_SYNCED", resp.get("id") or resp.get("templateId")
    else:
        we_status, we_id = "WE_AWAITING_MANUAL_ADD", None

    with STATE_LOCK:
        state = load_state()
        state["templates"][name]["webengage"] = {"status": we_status, "id": we_id, "staged_at": now_iso()}
        audit(state, "webengage_staged", template=name, mode=result["mode"])
        save_state(state)
    return 200, {"status": we_status, "webengage_template_id": we_id, **result}


def confirm_webengage(name, reference, confirmed_by):
    with STATE_LOCK:
        state = load_state()
        rec = state["templates"].get(name)
        if not rec or not rec.get("webengage"):
            return 409, {"error": "Stage the template for WebEngage first."}
        rec["webengage"].update({"status": "WE_SYNCED", "id": reference or rec["webengage"].get("id"),
                                 "confirmed_by": confirmed_by, "confirmed_at": now_iso()})
        audit(state, "webengage_confirmed", template=name, by=confirmed_by)
        save_state(state)
        return 200, {"status": "WE_SYNCED", "webengage": rec["webengage"]}


# ---------------------------------------------------------------------------
# SMS / DLT verification (no automation of DLT portals - human registers there)
# ---------------------------------------------------------------------------
def normalise_dlt(text):
    """Map portal variables {{n}} to DLT {#var#}, collapse whitespace."""
    t = VAR_RE.sub("{#var#}", text or "")
    return re.sub(r"\s+", " ", t).strip()


def dlt_hash(text):
    return hashlib.sha256(normalise_dlt(text).encode("utf-8")).hexdigest()


def dlt_register(d):
    errors = []
    if not re.fullmatch(r"\d{19}", d.get("dlt_template_id", "")):
        errors.append("DLT Template ID should be the 19-digit ID shown on the DLT portal.")
    if not re.fullmatch(r"[A-Z]{6}", d.get("sender_header", "")):
        errors.append("Sender header should be 6 uppercase letters (e.g. SNAPMT).")
    if d.get("pe_id") and not re.fullmatch(r"\d{15,19}", d["pe_id"]):
        errors.append("PE (Entity) ID looks malformed.")
    if not d.get("approved_text"):
        errors.append("Paste the exact approved template text from the DLT portal.")
    if errors:
        return 422, {"ok": False, "errors": errors}
    rec = {
        "dlt_template_id": d["dlt_template_id"],
        "sender_header": d["sender_header"],
        "pe_id": d.get("pe_id"),
        "approved_text": d["approved_text"],
        "sha256": dlt_hash(d["approved_text"]),
        "registered_by": d.get("registered_by", "unknown"),
        "registered_at": now_iso(),
    }
    with STATE_LOCK:
        state = load_state()
        state["dlt"][d["dlt_template_id"]] = rec
        audit(state, "dlt_registered", dlt_template_id=d["dlt_template_id"], by=rec["registered_by"])
        save_state(state)
    return 200, {"ok": True, "record": rec}


def dlt_verify(d):
    with STATE_LOCK:
        rec = load_state()["dlt"].get(d.get("dlt_template_id", ""))
    if not rec:
        return 404, {"ok": False, "errors": ["DLT Template ID not registered in the portal yet."]}
    current = dlt_hash(d.get("message_text", ""))
    warnings = []
    if re.search(r"https?://", d.get("message_text", "")):
        warnings.append("SMS contains a URL - TRAI requires the exact URL/domain to be whitelisted on the DLT template.")
    match = hmac.compare_digest(current, rec["sha256"])
    return 200, {
        "ok": match,
        "current_sha256": current,
        "approved_sha256": rec["sha256"],
        "normalised_text": normalise_dlt(d.get("message_text", "")),
        "approved_text": normalise_dlt(rec["approved_text"]),
        "warnings": warnings,
        "errors": [] if match else ["Message text differs from the DLT-approved text; operator scrubbing will block it."],
    }


# ---------------------------------------------------------------------------
# Content Agent (the ONLY AI component)
# ---------------------------------------------------------------------------
AGENT_SYSTEM = """You are Snapmint's CRM Content Agent. You draft campaign copy for an Indian BNPL/fintech brand.
Rules:
- You receive only aggregate segment descriptions. Never invent or request personal data.
- WhatsApp body uses numbered variables: {{1}} = customer first name, {{2}} = amount/EMI value. Do not start or end the body with a variable.
- Body <= 600 characters, CTA text <= 25 characters, plain friendly English (light Hinglish allowed).
- No guaranteed-approval claims, no misleading interest-rate claims, no urgency that is untrue. RBI fair-practice tone.
- template_name: lowercase letters, digits and underscores only.
- template_category: UTILITY only for transactional reminders about an existing loan/order; otherwise MARKETING.
Respond with a single JSON object and nothing else, with keys:
comms_a, comms_b, template_name, template_category, cta_text, sms_text, push_title, push_body, rationale"""

ALLOWED_AGENT_KEYS = {"comms_a", "comms_b", "template_name", "template_category", "cta_text",
                      "sms_text", "push_title", "push_body", "rationale"}


def agent_stub(brief):
    product, segment = brief["product"], brief["segment"]
    slug = re.sub(r"[^a-z0-9]+", "_", f"{product}_{segment}".lower()).strip("_")[:60]
    utility = "repayment" in product.lower()
    return {
        "comms_a": f"{product}: made easy with Snapmint",
        "comms_b": ("Hi {{1}}, your EMI of {{2}} is due soon. Pay on time to keep your Snapmint limit active."
                    if utility else
                    "Hi {{1}}, your pick is still waiting! Complete checkout with Snapmint and pay in easy EMIs of {{2}}. "
                    + (brief.get("guidance") or "")).strip(),
        "template_name": f"{slug}_v1",
        "template_category": "UTILITY" if utility else "MARKETING",
        "cta_text": "Pay EMI Now" if utility else "Complete Order",
        "sms_text": "Dear Customer, complete your Snapmint order in easy EMIs. {#var#} -Snapmint",
        "push_title": "Your cart misses you",
        "push_body": "Finish checkout in easy EMIs with Snapmint.",
        "rationale": "Deterministic stub (Content Agent not enabled).",
    }


def run_content_agent(brief):
    """Calls Claude Sonnet on Bedrock in ap-south-1 via the Anthropic SDK's Bedrock client."""
    model = CFG["bedrock_model"]
    if re.match(r"^(global|apac|us|eu|jp|au)\.", model):
        raise ValueError(f"{model} is a cross-region inference profile; data residency requires an in-region model ID.")
    if not CFG["bedrock_region"].startswith("ap-south-"):
        raise ValueError("BEDROCK_REGION must be an India region (ap-south-1).")

    from anthropic import AnthropicBedrockMantle  # optional dependency, imported lazily

    client = AnthropicBedrockMantle(aws_region=CFG["bedrock_region"])  # AWS creds from the default boto chain
    user = (f"Product: {brief['product']}\nSegment (aggregate): {brief['segment']}\n"
            f"Channel: {brief.get('channel', 'WhatsApp')}\nMarketer guidance: {brief.get('guidance') or 'none'}")
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=AGENT_SYSTEM,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Content Agent declined this brief; edit the guidance and retry.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise RuntimeError("Content Agent did not return JSON.")
    data = json.loads(match.group(0))
    return {k: v for k, v in data.items() if k in ALLOWED_AGENT_KEYS}


def generate_campaign(brief):
    clean = {
        "product": scrub_pii(str(brief.get("product", ""))[:100]),
        "segment": scrub_pii(str(brief.get("segment", ""))[:100]),
        "channel": str(brief.get("channel", "WhatsApp"))[:20],
        "guidance": scrub_pii(str(brief.get("guidance", ""))[:500]),
    }
    redacted = find_pii(" ".join(str(brief.get(k, "")) for k in ("product", "segment", "guidance")))
    source = "stub"
    if CFG["agent_enabled"]:
        try:
            out = run_content_agent(clean)
            source = f"bedrock:{CFG['bedrock_region']}:{CFG['bedrock_model']}"
        except ImportError:
            return 500, {"error": "Install the Anthropic SDK (pip install anthropic) to enable the Content Agent."}
        except Exception as e:  # noqa: BLE001
            return 502, {"error": str(e)}
    else:
        out = agent_stub(clean)
    # Deterministic post-checks on the agent's draft - the agent never self-approves.
    check = validate_whatsapp({
        "template_name": out.get("template_name", ""), "category": out.get("template_category", ""),
        "body": out.get("comms_b", ""), "cta_text": out.get("cta_text", ""),
        "target_url": "https://snapmint.com/", "body_examples": ["Rahul", "Rs.3,166", "x", "y"],
    })
    return 200, {"draft": out, "source": source, "pii_redacted": redacted, "validation": check,
                 "brief_sent": clean}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class CRMPortalHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PORTAL_DIR, **kwargs)

    def log_message(self, fmt, *args):
        if "/api/templates/status" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def send_json(self, code, obj):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_raw(self):
        return self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))

    def read_json(self, raw=None):
        raw = self.read_raw() if raw is None else raw
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path.startswith("/data/"):
            return self.send_json(404, {"error": "not found"})  # never serve state files

        if parsed.path == "/api/config":
            return self.send_json(200, {
                "mode": CFG["mode"],
                "wsp_provider": CFG["wsp_provider"],
                "meta_configured": bool(CFG["meta_waba_id"] and CFG["meta_token"]),
                "wsp_configured": bool(CFG["wsp_template_url"] and CFG["wsp_api_key"]),
                "webengage_api_configured": bool(CFG["we_template_api_url"] and CFG["we_api_key"]),
                "webengage_wsp_name": CFG["we_wsp_name"],
                "agent_enabled": CFG["agent_enabled"],
                "bedrock_region": CFG["bedrock_region"],
                "bedrock_model": CFG["bedrock_model"],
            })

        if parsed.path == "/api/templates/status":
            name = (qs.get("name") or [""])[0]
            with STATE_LOCK:
                rec = load_state()["templates"].get(name)
            if not rec:
                return self.send_json(404, {"status": "UNKNOWN"})
            return self.send_json(200, {k: v for k, v in rec.items() if k != "spec"})

        if parsed.path == "/api/audit":
            with STATE_LOCK:
                return self.send_json(200, load_state()["audit"][-100:])

        if parsed.path == "/webhooks/whatsapp":
            # Meta subscription handshake
            if (qs.get("hub.mode") or [""])[0] == "subscribe" and \
                    hmac.compare_digest((qs.get("hub.verify_token") or [""])[0], CFG["meta_verify_token"]):
                body = (qs.get("hub.challenge") or [""])[0].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body)
                return
            return self.send_json(403, {"error": "verification failed"})

        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/webhooks/whatsapp":
            raw = self.read_raw()
            sig = self.headers.get("X-Hub-Signature-256")
            if not verify_signature(raw, sig, [CFG["meta_app_secret"], CFG["wsp_webhook_secret"]]):
                return self.send_json(401, {"error": "invalid signature"})
            payload = self.read_json(raw)
            if payload is None:
                return self.send_json(400, {"error": "bad json"})
            return self.send_json(200, {"applied": apply_template_webhook(payload)})

        body = self.read_json()
        if body is None:
            return self.send_json(400, {"error": "Request body must be JSON."})

        if path == "/api/templates/validate":
            return self.send_json(200, validate_whatsapp(body))
        if path == "/api/templates/preview-payload":
            return self.send_json(200, build_meta_payload(body))
        if path == "/api/templates/submit":
            return self.send_json(*submit_template(body))
        if path == "/api/templates/reset":
            # Simulation helper: forget a template so it can be resubmitted after a rejection.
            with STATE_LOCK:
                state = load_state()
                rec = state["templates"].get(body.get("template_name"))
                if rec and (CFG["mode"] == "simulate" or rec["status"] in ("REJECTED", "DISABLED")):
                    state["templates"].pop(body["template_name"])
                    audit(state, "reset", template=body["template_name"])
                    save_state(state)
                    return self.send_json(200, {"ok": True})
            return self.send_json(409, {"ok": False, "error": "Only rejected templates can be reset in live mode."})
        if path == "/api/webengage/stage":
            return self.send_json(*stage_webengage(body.get("template_name", "")))
        if path == "/api/webengage/confirm":
            return self.send_json(*confirm_webengage(body.get("template_name", ""),
                                                     body.get("webengage_reference", ""),
                                                     body.get("confirmed_by", "unknown")))
        if path == "/api/sms/dlt-register":
            return self.send_json(*dlt_register(body))
        if path == "/api/sms/dlt-verify":
            return self.send_json(*dlt_verify(body))
        if path == "/api/agent/generate-campaign":
            return self.send_json(*generate_campaign(body))

        # Explicitly no launch endpoint: campaign launch is a human action in WebEngage.
        return self.send_json(404, {"error": f"No such endpoint {path}"})


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    with Server((HOST, PORT), CRMPortalHandler) as httpd:
        print("=" * 64)
        print(f"Snapmint CRM Calendar Portal  ->  http://{HOST}:{PORT}")
        print(f"Pipeline mode: {CFG['mode']}   WSP provider: {CFG['wsp_provider']}")
        print(f"Content Agent: {'Bedrock ' + CFG['bedrock_region'] if CFG['agent_enabled'] else 'stub (set CONTENT_AGENT_ENABLED=1)'}")
        print("No endpoint can launch campaigns - launch stays a human action in WebEngage.")
        print("=" * 64)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
