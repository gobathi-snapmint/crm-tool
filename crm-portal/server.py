#!/usr/bin/env python3
"""
Snapmint CRM Calendar Portal - backend (Python 3.9+ standard library only).

    python3 crm-portal/server.py      ->  http://127.0.0.1:8000

The calendar is the CRM team's day-level plan (nov_mkp_calendar_full_view_PLAN_v1.3.csv):
one row per date x segment x channel. Every WhatsApp row is linked to a WhatsApp template;
rows with the same creative share one template, so 332 WA rows become ~19 templates.

    Fill calendar -> Lock -> templates are queued and sent to the vendor ONE BY ONE
                  -> vendor status via webhook or polling
                  -> APPROVED in the SAME category we asked for?
                        yes -> WebEngage step (API if an endpoint is configured, else "Add in WebEngage")
                        no / rejected -> Needs edit -> marketer edits -> Resubmit -> queue again

Nothing here can launch a campaign; launch stays a human action inside WebEngage.
"""

import csv
import hashlib
import hmac
import http.server
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DATA = os.path.join(HERE, "data")
CAL_FILE = os.path.join(DATA, "calendar.json")
SETTINGS_FILE = os.path.join(DATA, "settings.json")
AUDIT_FILE = os.path.join(DATA, "audit.jsonl")
SEED_FILE = os.path.join(os.path.dirname(HERE), "nov_mkp_calendar_full_view_PLAN_v1.3.csv")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

LOCK = threading.RLock()
QUEUE_WAKE = threading.Event()
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
COLS = [  # (row key, sheet column) in sheet order
    ("day", "Day"), ("date", "Date"), ("product", "Product"), ("segment", "Segment Name \n(don't add link here)"),
    ("naming", "Naming Structure"), ("exclude", "Segments to Exclude"), ("start_age", "Start Age"),
    ("end_age", "End Age"), ("gender", "Gender"), ("location", "Location"), ("campaign_type", "Campaign Type"),
    ("channel", "Channel"), ("exp", "EXP"), ("comms_a", "Comms A"), ("comms_b", "Comms B"), ("time", "Time"),
    ("banner_url", "Banner_Url"), ("comments", "Comments"), ("size", "Size"),
]
ROW_KEYS = [k for k, _ in COLS]
# WhatsApp whitelisting columns - one per field of the template-create request (Meta format, which WSPs relay)
WA_COLS = [
    ("template_name", "WA Template Name"), ("vendor", "WA Vendor"), ("waba_id", "WA WABA ID"),
    ("sender_number", "WA Sender Number"), ("language", "WA Language"), ("category", "WA Category"),
    ("header_type", "WA Header Type"), ("header_media_url", "WA Header Media URL"), ("header_text", "WA Header Text"),
    ("body", "WA Body"), ("body_samples", "WA Body Samples"), ("footer", "WA Footer"),
    ("button_type", "WA Button Type"), ("button_text", "WA Button Text"), ("button_url", "WA Button URL"),
    ("button_url_sample", "WA Button URL Sample"), ("url_variable", "WebEngage URL Variable"),
    ("body_variables", "WebEngage Body Variables"), ("status", "WA Status"),
    ("approved_category", "WA Approved Category"), ("vendor_template_id", "WA Vendor Template ID"),
    ("webengage_template_id", "WebEngage Template ID"),
]
TEMPLATE_EDITABLE = {"vendor", "sender_number", "template_name", "language", "category", "header_type",
                     "header_media_url", "header_text", "body", "body_samples", "footer", "button_type",
                     "button_text", "button_url", "button_url_sample", "url_variable", "body_variables"}
EDITABLE_STATES = {"DRAFT", "REJECTED", "CATEGORY_CHANGED", "PAUSED", "ERROR"}
NEEDS_EDIT = {"REJECTED", "CATEGORY_CHANGED", "PAUSED", "ERROR"}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj, private=False):
    os.makedirs(DATA, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    if private:
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def audit(event, **fields):
    os.makedirs(DATA, exist_ok=True)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now_iso(), "event": event, **fields}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Settings (vendor + WebEngage credentials live only here, never in the browser)
# ---------------------------------------------------------------------------
WSP_DEFAULT = {"type": "wsp", "create_url": "", "status_url": "", "api_key": "", "auth_style": "bearer",
               "waba_id": "", "sender_number": "", "webhook_secret": "", "id_path": "id",
               "status_path": "status", "category_path": "category", "reason_path": "rejected_reason"}
DEFAULT_SETTINGS = {
    "mode": "simulate",  # simulate | live
    "year": 2026,
    "poll_seconds": 30,
    "submit_gap_seconds": 2,  # pause between two vendor calls while the queue runs
    "default_vendor": "TrustSignal",
    "vendors": {
        "TrustSignal": dict(WSP_DEFAULT),
        "Route Mobile": dict(WSP_DEFAULT),
        "Meta Cloud API": {"type": "meta", "waba_id": "", "sender_number": "", "app_id": "", "api_key": "",
                           "graph_version": "v23.0", "webhook_secret": "", "verify_token": ""},
    },
    "webengage": {"license_code": "", "api_key": "", "data_center": "in", "template_api_url": "",
                  "wsp_name": "TrustSignal"},
}
SECRET_KEYS = {"api_key", "webhook_secret", "verify_token"}


def load_settings():
    s = read_json(SETTINGS_FILE, {})
    merged = json.loads(json.dumps(DEFAULT_SETTINGS))
    for k, v in s.items():
        if k == "vendors" and isinstance(v, dict):
            for name, conf in v.items():
                merged["vendors"].setdefault(name, dict(WSP_DEFAULT)).update(conf)
        elif k == "webengage" and isinstance(v, dict):
            merged["webengage"].update(v)
        else:
            merged[k] = v
    return merged


def redact(settings):
    out = json.loads(json.dumps(settings))
    for conf in list(out["vendors"].values()) + [out["webengage"]]:
        for k in SECRET_KEYS:
            if k in conf:
                conf[k] = "••••" + conf[k][-4:] if conf[k] else ""
    return out


def save_settings(update):
    with LOCK:
        cur = load_settings()
        for k in ("mode", "year", "poll_seconds", "submit_gap_seconds", "default_vendor"):
            if k in update:
                cur[k] = update[k]
        for name, conf in (update.get("vendors") or {}).items():
            dst = cur["vendors"].setdefault(name, dict(WSP_DEFAULT))
            for f, v in conf.items():
                if f in SECRET_KEYS and isinstance(v, str) and v.startswith("••••"):
                    continue  # unchanged redacted value
                dst[f] = v
        for f, v in (update.get("webengage") or {}).items():
            if f in SECRET_KEYS and isinstance(v, str) and v.startswith("••••"):
                continue
            cur["webengage"][f] = v
        write_json(SETTINGS_FILE, cur, private=True)
        audit("settings_updated", keys=sorted(update.keys()))
        return cur


def requirements(settings):
    """What is needed (and what is missing) for the live approval -> WebEngage flow."""
    out = []
    for name, c in settings["vendors"].items():
        if c.get("type") == "meta":
            items = [("WABA ID", bool(c.get("waba_id"))), ("Sender number (registered on the WABA)", bool(c.get("sender_number"))),
                     ("System User access token (whatsapp_business_management)", bool(c.get("api_key"))),
                     ("App ID (header image upload)", bool(c.get("app_id"))),
                     ("App Secret (webhook signature)", bool(c.get("webhook_secret")))]
        else:
            items = [("Template create endpoint URL", bool(c.get("create_url"))),
                     ("Template status endpoint URL", bool(c.get("status_url"))),
                     ("API key / token", bool(c.get("api_key"))), ("WABA ID / account ID", bool(c.get("waba_id"))),
                     ("Sender number (WABA number)", bool(c.get("sender_number"))),
                     ("Webhook signing secret (optional, polling works without)", bool(c.get("webhook_secret")))]
        out.append({"system": name, "items": [{"label": l, "ok": ok} for l, ok in items]})
    w = settings["webengage"]
    out.append({"system": "WebEngage", "items": [
        {"label": "License code", "ok": bool(w.get("license_code"))},
        {"label": "REST API key", "ok": bool(w.get("api_key"))},
        {"label": "Template endpoint (not in public docs - ask WebEngage)", "ok": bool(w.get("template_api_url"))},
        {"label": "WSP name exactly as integrated in WebEngage", "ok": bool(w.get("wsp_name"))},
    ]})
    return out


# ---------------------------------------------------------------------------
# Calendar + template library
# ---------------------------------------------------------------------------
def num(v, default=0.0):
    try:
        return float(str(v).replace(",", "").strip() or default)
    except ValueError:
        return default


def is_whatsapp(row):
    return str(row.get("channel", "")).lower().startswith(("wa", "whatsapp"))


def category_for(channel):
    return "MARKETING" if "market" in channel.lower() else "UTILITY"


DYN_RE = re.compile(r"\{\{.*\}\}")


def split_brief(text):
    """Comments -> tag / visual / copy / CTA / LP  ('[Tag] Static Visual: … Copy: '…' CTA: … | LP: …')."""
    t = text or ""
    tags = re.findall(r"\[([^\]]+)\]", re.match(r"^(\s*\[[^\]]*\]\s*)*", t).group(0))
    body = t[re.match(r"^(\s*\[[^\]]*\]\s*)*", t).end():]
    visual = re.search(r"Static Visual:\s*(.*?)(?:\s*Copy:|$)", body, re.S)
    copy = re.search(r"Copy:\s*'(.*?)'\s*(?:CTA:|$)", body, re.S) or re.search(r"Copy:\s*(.*?)\s*(?:CTA:|$)", body, re.S)
    cta = re.search(r"CTA:\s*(.*?)\s*(?:\|\s*LP:|$)", body, re.S)
    lp = re.search(r"LP:\s*(\S+.*?)\s*(?:\(.*\))?$", body, re.S)
    clean = lambda m: m.group(1).strip().replace("\\'", "'") if m else ""
    return {"tags": tags, "visual": clean(visual), "copy": clean(copy), "cta": clean(cta), "lp": clean(lp)}


def landing_to_button(url):
    """Calendar LP -> WhatsApp button URL. A WebEngage expression becomes the dynamic suffix {{1}}."""
    u = (url or "").strip()
    m = DYN_RE.search(u)
    if not m:
        return {"button_url": u, "button_url_sample": "", "url_variable": ""}
    expr = m.group(0)
    default = re.search(r'or\s+"([^"]+)"', expr)
    return {"button_url": u[:m.start()] + "{{1}}", "button_url_sample": u[:m.start()] + (default.group(1) if default else "sample"),
            "url_variable": expr}


def content_key(row):
    b = split_brief(row.get("comments"))
    return hashlib.sha1("|".join([b["copy"], b["cta"], b["lp"], row.get("banner_url", ""),
                                  category_for(row.get("channel", ""))]).encode()).hexdigest()[:12]


def slug(text, words=4):
    w = [x for x in re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split() if x not in ("the", "a", "and", "on", "your", "in")]
    return "_".join(w[:words]) or "message"


def default_template(row, cal, settings, names):
    b = split_brief(row.get("comments"))
    btn = landing_to_button(b["lp"])
    vendor = settings.get("default_vendor") or "TrustSignal"
    vconf = settings["vendors"].get(vendor, {})
    cat = category_for(row.get("channel", ""))
    base = f"{MONTHS[cal['month'] - 1].lower()}{str(cal['year'])[-2:]}_{(row.get('product') or 'mkp').lower()}_" \
           f"{slug(b['cta'] or b['copy'], 3)}_{'util' if cat == 'UTILITY' else 'mktg'}"
    name, n = base + "_v1", 2
    while name in names:
        name, n = f"{base}{n}_v1", n + 1
    names.add(name)
    return {
        "id": uuid.uuid4().hex[:12], "key": content_key(row), "version": 1,
        "tags": b["tags"], "visual_brief": b["visual"], "source_copy": b["copy"], "source_cta": b["cta"], "source_lp": b["lp"],
        "template_name": name, "vendor": vendor, "waba_id": vconf.get("waba_id", ""),
        "sender_number": vconf.get("sender_number", ""), "language": "en", "category": cat,
        "header_type": "IMAGE" if row.get("banner_url") else "NONE", "header_media_url": row.get("banner_url", ""),
        "header_text": "", "body": b["copy"], "body_samples": "", "footer": "Snapmint",
        "button_type": "URL" if b["cta"] else "NONE", "button_text": b["cta"][:25], **btn, "body_variables": "",
        "status": "DRAFT", "vendor_template_id": "", "approved_category": "", "reason": "",
        "webengage_template_id": "", "webengage_packet": None, "queued_at": "", "submitted_at": "",
        "decided_at": "", "pushed_at": "", "attempts": 0, "history": [],
    }


def empty_calendar():
    return {"name": "", "year": 2026, "month": 11, "headers": [c for _, c in COLS], "rows": [],
            "templates": [], "locked": False, "locked_at": "", "locked_by": "", "imported_at": ""}


def load_calendar():
    cal = read_json(CAL_FILE, None)
    if not isinstance(cal, dict):
        return empty_calendar()
    if "templates" not in cal or any("wa" in r or "days" in r for r in cal.get("rows", [])[:5]):
        # data/ from the older framework-sheet portal: keep a copy, start fresh
        os.replace(CAL_FILE, CAL_FILE + f".old-{int(time.time())}")
        audit("calendar_migrated", reason="old portal format; backed up and reset")
        return empty_calendar()
    for k, v in empty_calendar().items():
        cal.setdefault(k, v)
    return cal


def save_calendar(cal):
    write_json(CAL_FILE, cal)


def link_templates(cal, settings):
    """Give every WhatsApp row a template (shared by content) and drop unused drafts."""
    by_key = {t["key"]: t for t in cal["templates"]}
    names = {t["template_name"] for t in cal["templates"]}
    for r in cal["rows"]:
        if not is_whatsapp(r):
            r["template_id"] = ""
            continue
        k = content_key(r)
        t = by_key.get(k)
        if not t:
            t = default_template(r, cal, settings, names)
            cal["templates"].append(t)
            by_key[k] = t
        r["template_id"] = t["id"]
    used = {r["template_id"] for r in cal["rows"] if r.get("template_id")}
    cal["templates"] = [t for t in cal["templates"] if t["id"] in used or t["status"] != "DRAFT"]


def date_sort(r):
    m = re.match(r"(\d{1,2})", str(r.get("date", "")))
    t = re.match(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([AP]M)?", str(r.get("time", "")).strip(), re.I)
    mins = 0
    if t:
        h = int(t.group(1)) % 12 + (12 if (t.group(3) or "").upper() == "PM" else 0)
        mins = h * 60 + int(t.group(2))
    return (int(m.group(1)) if m else 99, mins)


def template_usage(cal):
    use = {}
    for r in cal["rows"]:
        if r.get("template_id"):
            u = use.setdefault(r["template_id"], {"rows": 0, "audience": 0, "segments": set(), "dates": set(), "first": None})
            u["rows"] += 1
            u["audience"] += int(num(r.get("size")))
            u["segments"].add(r.get("segment", ""))
            u["dates"].add(r.get("date", ""))
            if u["first"] is None or date_sort(r) < date_sort(u["first"]):
                u["first"] = r
    return use


def public_calendar(cal):
    """Calendar for the UI: templates carry how they are used in the calendar."""
    use = template_usage(cal)
    out = dict(cal)
    tpls = []
    for t in cal["templates"]:
        u = use.get(t["id"])
        t = dict(t)
        t["usage"] = {"rows": u["rows"], "audience": u["audience"], "segments": sorted(u["segments"]),
                      "dates": sorted(u["dates"], key=lambda d: date_sort({"date": d})),
                      "first_send": f"{u['first'].get('date')} {u['first'].get('time')}".strip()} if u else \
            {"rows": 0, "audience": 0, "segments": [], "dates": [], "first_send": ""}
        t["validation"] = validate(t)
        tpls.append(t)
    out["templates"] = tpls
    return out


def parse_sheet(text):
    reader = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not reader:
        raise ValueError("Empty CSV")
    head = reader[0]
    norm = lambda h: re.sub(r"\s+", " ", h).strip().lower()
    idx = {}
    for i, h in enumerate(head):
        n = norm(h)
        for key, col in COLS:
            if n == norm(col) or (key == "segment" and n.startswith("segment name")):
                idx.setdefault(key, i)
    missing = [col.split("\n")[0].strip() for key, col in COLS if key not in idx and key in ("date", "segment", "channel", "comments", "size")]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    rows, month = [], None
    for rec in reader[1:]:
        if not any(x.strip() for x in rec):
            continue
        rec = rec + [""] * (len(head) - len(rec))
        row = {"id": uuid.uuid4().hex[:12]}
        for key in ROW_KEYS:
            row[key] = rec[idx[key]] if key in idx else ""
        m = re.fullmatch(r"\d{1,2}-([A-Za-z]{3})", row["date"].strip())
        if m and month is None:
            month = MONTHS.index(m.group(1).title()) + 1
        rows.append(row)
    return head, rows, month or 11


def import_sheet(text, name):
    settings = load_settings()
    head, rows, month = parse_sheet(text)
    with LOCK:
        old = load_calendar()
        if old.get("locked"):
            raise ValueError("The calendar is locked. Unlock it before importing a new version.")
        cal = {"name": name, "year": settings["year"], "month": month, "headers": head, "rows": rows,
               "templates": old.get("templates", []), "locked": False, "locked_at": "", "locked_by": "",
               "imported_at": now_iso()}
        link_templates(cal, settings)
        save_calendar(cal)
        audit("calendar_imported", name=name, rows=len(rows), templates=len(cal["templates"]))
    return public_calendar(cal)


def export_sheet(with_wa):
    cal = load_calendar()
    tpl = {t["id"]: t for t in cal["templates"]}
    head = cal.get("headers") or [c for _, c in COLS]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(head[:len(COLS)] + ([l for _, l in WA_COLS] if with_wa else []))
    for r in cal["rows"]:
        line = [r.get(k, "") for k in ROW_KEYS]
        if with_wa:
            t = tpl.get(r.get("template_id")) or {}
            line += [t.get(k, "") for k, _ in WA_COLS]
        w.writerow(line)
    return out.getvalue(), cal


# ---------------------------------------------------------------------------
# Template validation & payload (Meta rules - every WSP forwards to Meta)
# ---------------------------------------------------------------------------
VAR_RE = re.compile(r"\{\{(\d+)\}\}")
PROMO_RE = re.compile(r"\b(offer|offers|discount|cashback|sale|deal|deals|price drop|free|exclusive|limited|hurry|save|"
                      r"gift|voucher|festive|explore|0 down payment|no-cost|lowest|grab|coupon|selling fast|"
                      r"special|claim|upgrade|cheaper|interest-free|0% emi)\b", re.I)
PII_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)|[\w.+-]+@[\w-]+\.[\w.-]+")


def samples_of(t):
    return [s.strip() for s in str(t.get("body_samples") or "").split("|") if s.strip()]


def validate(t):
    errors, warnings = [], []
    name, body = t.get("template_name", ""), t.get("body", "")
    if not re.fullmatch(r"[a-z0-9_]{1,512}", name or ""):
        errors.append("Template name: lowercase letters, digits and underscores only.")
    if t.get("category") not in ("UTILITY", "MARKETING"):
        errors.append("Category must be UTILITY or MARKETING.")
    if not t.get("vendor"):
        errors.append("Choose the WhatsApp vendor.")
    if not re.fullmatch(r"[a-z]{2}(_[A-Z]{2})?", t.get("language") or ""):
        errors.append("Language must be a Meta code like en or en_US.")
    if not body.strip():
        errors.append("Body text is empty.")
    if len(body) > 1024:
        errors.append(f"Body is {len(body)} characters (Meta limit 1024).")
    nums = sorted({int(n) for n in VAR_RE.findall(body)})
    if nums and nums != list(range(1, len(nums) + 1)):
        errors.append(f"Body variables must run {{{{1}}}}, {{{{2}}}}… without gaps (found {nums}).")
    s = body.strip()
    if nums and (VAR_RE.match(s) or re.search(r"\{\{\d+\}\}$", s)):
        errors.append("Body cannot start or end with a variable.")
    if nums and len(samples_of(t)) < len(nums):
        errors.append(f"Add a sample value for each body variable ({len(nums)} needed), separated by |.")
    if re.search(r"\{\{[^}0-9]", body):
        errors.append("Body has a non-numbered variable; use {{1}}, {{2}}…")
    ht = t.get("header_type") or "NONE"
    if ht == "IMAGE":
        url = t.get("header_media_url") or ""
        if not url.startswith("https://"):
            errors.append("Header image needs a public https:// URL (the banner). Or set header type to None.")
        elif not re.search(r"\.(png|jpe?g)(\?.*)?$", url, re.I):
            warnings.append("Header image should be PNG or JPEG, max 5 MB.")
    elif ht == "TEXT":
        if not (t.get("header_text") or "").strip():
            errors.append("Header text is empty.")
        elif len(t["header_text"]) > 60:
            errors.append("Header text is longer than 60 characters.")
    if (t.get("button_type") or "NONE") == "URL":
        if not t.get("button_text"):
            errors.append("Button text is empty.")
        elif len(t["button_text"]) > 25:
            errors.append("Button text is longer than 25 characters.")
        url = t.get("button_url", "")
        if not url.startswith("https://"):
            errors.append("Button URL must start with https:// (app deeplinks like snapmint:// are not allowed on WhatsApp).")
        if "{{" in url and not url.endswith("{{1}}"):
            errors.append("A dynamic button URL can only have {{1}} at the very end.")
        if url.endswith("{{1}}") and not t.get("button_url_sample"):
            errors.append("Dynamic button URL needs a full sample URL.")
        if url.endswith("{{1}}") and not t.get("url_variable"):
            warnings.append("Dynamic button URL has no WebEngage value for {{1}}.")
    elif (t.get("button_type") or "NONE") == "QUICK_REPLY" and not t.get("button_text"):
        errors.append("Quick-reply button text is empty.")
    mapped = [x for x in str(t.get("body_variables") or "").split("|") if x.strip()]
    if nums and len(mapped) < len(nums):
        warnings.append("Map each body variable to a WebEngage value (e.g. {{user.first_name}}), otherwise it has "
                        "to be mapped in WebEngage before launch.")
    if len(t.get("footer") or "") > 60:
        errors.append("Footer is longer than 60 characters.")
    if PII_RE.search(body):
        errors.append("Body seems to contain a phone number or email; use a variable instead.")
    promo = PROMO_RE.search(" ".join([body, t.get("button_text") or "", t.get("header_text") or ""]))
    if t.get("category") == "UTILITY" and promo:
        warnings.append(f"Promotional wording ('{promo.group(0)}') in a UTILITY template - Meta will likely approve it as "
                        "MARKETING, and then it is NOT added to WebEngage.")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def meta_payload(t, header_handle=None):
    comps = []
    ht = t.get("header_type") or "NONE"
    if ht == "IMAGE":
        comps.append({"type": "HEADER", "format": "IMAGE", "example": {"header_handle": [header_handle or t.get("header_media_url")]}})
    elif ht == "TEXT":
        comps.append({"type": "HEADER", "format": "TEXT", "text": t.get("header_text", "")})
    body = {"type": "BODY", "text": t["body"]}
    if VAR_RE.search(t["body"]):
        body["example"] = {"body_text": [samples_of(t)]}
    comps.append(body)
    if t.get("footer"):
        comps.append({"type": "FOOTER", "text": t["footer"]})
    bt = t.get("button_type") or "NONE"
    if bt == "URL":
        btn = {"type": "URL", "text": t["button_text"], "url": t["button_url"]}
        if t["button_url"].endswith("{{1}}"):
            btn["example"] = [t["button_url_sample"]]
        comps.append({"type": "BUTTONS", "buttons": [btn]})
    elif bt == "QUICK_REPLY":
        comps.append({"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": t["button_text"]}]})
    return {"name": t["template_name"], "language": t.get("language") or "en", "category": t["category"],
            "parameter_format": "POSITIONAL", "components": comps}


def vendor_payload(t, settings):
    """The exact JSON body the portal sends to the template's vendor."""
    conf = settings["vendors"].get(t.get("vendor"), {})
    if conf.get("type") == "meta":
        return meta_payload(t)
    return {"waba_id": t.get("waba_id") or conf.get("waba_id", ""),
            "phone_number": t.get("sender_number") or conf.get("sender_number", ""), **meta_payload(t)}


def webengage_packet(t, settings):
    w = settings["webengage"]
    variables = {str(i): v for i, v in enumerate([x.strip() for x in str(t.get("body_variables") or "").split("|") if x.strip()], 1)}
    ht = t.get("header_type") or "NONE"
    return {
        "licenseCode": w.get("license_code"),
        "channel": "WHATSAPP",
        "wsp": w.get("wsp_name") or t.get("vendor"),
        "templateName": t["template_name"],
        "language": t.get("language") or "en",
        "category": t.get("approved_category") or t["category"],
        "vendorTemplateId": t.get("vendor_template_id"),
        "header": {"type": ht, "url": t.get("header_media_url")} if ht == "IMAGE" else
                  ({"type": "TEXT", "text": t.get("header_text")} if ht == "TEXT" else None),
        "body": {"text": t["body"], "variables": variables},
        "footer": t.get("footer") or None,
        "buttons": [{"type": t.get("button_type"), "text": t.get("button_text"), "url": t.get("button_url") or None,
                     "urlVariable": t.get("url_variable") or None}] if (t.get("button_type") or "NONE") != "NONE" else [],
    }


# ---------------------------------------------------------------------------
# Outbound HTTP
# ---------------------------------------------------------------------------
def http_call(method, url, payload=None, headers=None, raw=None, timeout=30):
    data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body[:2000]}
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, {"error": f"Could not reach {urllib.parse.urlparse(url).netloc}: {getattr(e, 'reason', e)}"}
    except json.JSONDecodeError:
        return 0, {"error": "Vendor returned non-JSON"}


def dig(obj, path):
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(obj, list):
            obj = obj[int(part)] if part.isdigit() and int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def norm_status(v):
    s = str(v or "").upper()
    if s in ("APPROVED", "ENABLED", "ACTIVE"):
        return "APPROVED"
    if s in ("REJECTED", "FAILED", "DISABLED"):
        return "REJECTED"
    if s in ("PAUSED", "FLAGGED"):
        return "PAUSED"
    return "PENDING"


def auth(conf, url):
    key, style = conf.get("api_key", ""), conf.get("auth_style", "bearer")
    if style == "query":
        return url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"api_key": key}), {}
    if style == "x-api-key":
        return url, {"X-API-Key": key}
    if style == "apikey":
        return url, {"apikey": key}
    return url, {"Authorization": f"Bearer {key}"}


# ---------------------------------------------------------------------------
# Vendor adapters
# ---------------------------------------------------------------------------
SIM_PENDING = {}  # vendor_template_id -> decide-at timestamp


def sim_create(t):
    tid = "sim_" + hashlib.sha1(f"{t['template_name']}{time.time()}".encode()).hexdigest()[:10]
    SIM_PENDING[tid] = time.time() + 6
    return {"ok": True, "vendor_template_id": tid, "http": 200,
            "response": {"id": tid, "status": "PENDING", "category": t["category"]}}


def sim_status(t):
    if time.time() < SIM_PENDING.get(t["vendor_template_id"], 0):
        return {"status": "PENDING"}
    v = validate(t)
    if not v["ok"]:
        return {"status": "REJECTED", "reason": "INVALID_FORMAT: " + v["errors"][0]}
    promo = PROMO_RE.search(" ".join([t["body"], t.get("button_text") or "", t.get("header_text") or ""]))
    category = "MARKETING" if t["category"] == "UTILITY" and promo else t["category"]
    return {"status": "APPROVED", "category": category,
            "reason": f"Meta classified the content as MARKETING (matched '{promo.group(0)}')" if category != t["category"] else ""}


def meta_create(t, conf):
    if not (conf.get("waba_id") and conf.get("api_key")):
        return {"ok": False, "error": "Meta Cloud API: WABA ID and access token are not set in Settings."}
    v = conf.get("graph_version") or "v23.0"
    handle = None
    if (t.get("header_type") or "NONE") == "IMAGE":
        if not conf.get("app_id"):
            return {"ok": False, "error": "Meta Cloud API: App ID is needed to upload the header image."}
        try:
            with urllib.request.urlopen(t["header_media_url"], timeout=30) as r:
                blob, ctype = r.read(), r.headers.get_content_type()
            q = urllib.parse.urlencode({"file_length": len(blob), "file_type": ctype, "access_token": conf["api_key"]})
            code, sess = http_call("POST", f"https://graph.facebook.com/{v}/{conf['app_id']}/uploads?{q}")
            req = urllib.request.Request(f"https://graph.facebook.com/{v}/{sess['id']}", data=blob, method="POST")
            req.add_header("Authorization", f"OAuth {conf['api_key']}")
            req.add_header("file_offset", "0")
            with urllib.request.urlopen(req, timeout=60) as r:
                handle = json.loads(r.read().decode())["h"]
        except Exception as e:  # noqa: BLE001 - shown to the marketer
            return {"ok": False, "error": f"Header image upload failed: {e}"}
    payload = meta_payload(t, handle)
    # A rejected/paused Meta template is edited in place (same id + name); otherwise a new one is created
    if t.get("edit_in_place") and t.get("vendor_template_id"):
        edit = {"components": payload["components"]}
        code, resp = http_call("POST", f"https://graph.facebook.com/{v}/{t['vendor_template_id']}", edit,
                               {"Authorization": f"Bearer {conf['api_key']}"})
        if code != 200:
            return {"ok": False, "http": code, "response": resp, "error": dig(resp, "error.message") or f"HTTP {code}"}
        return {"ok": True, "http": code, "response": resp, "vendor_template_id": t["vendor_template_id"], "request": edit}
    code, resp = http_call("POST", f"https://graph.facebook.com/{v}/{conf['waba_id']}/message_templates", payload,
                           {"Authorization": f"Bearer {conf['api_key']}"})
    if code != 200:
        return {"ok": False, "http": code, "response": resp, "error": dig(resp, "error.message") or f"HTTP {code}"}
    return {"ok": True, "http": code, "response": resp, "vendor_template_id": str(resp.get("id")), "request": payload}


def meta_status(t, conf):
    v = conf.get("graph_version") or "v23.0"
    code, resp = http_call("GET", f"https://graph.facebook.com/{v}/{t['vendor_template_id']}?fields=name,status,category,rejected_reason",
                           headers={"Authorization": f"Bearer {conf['api_key']}"})
    if code != 200:
        return {"status": "PENDING", "error": dig(resp, "error.message") or f"HTTP {code}"}
    return {"status": norm_status(resp.get("status")), "category": resp.get("category"), "reason": resp.get("rejected_reason")}


def wsp_create(t, conf, vendor, settings):
    if not (conf.get("create_url") and conf.get("api_key")):
        return {"ok": False, "error": f"{vendor}: template create URL and API key are not set in Settings."}
    payload = vendor_payload(t, settings)
    url, headers = auth(conf, conf["create_url"].replace("{waba_id}", payload.get("waba_id", "")))
    code, resp = http_call("POST", url, payload, headers)
    if code not in (200, 201, 202):
        return {"ok": False, "http": code, "response": resp, "error": f"{vendor} returned HTTP {code}"}
    tid = dig(resp, conf.get("id_path") or "id") or dig(resp, "data.id") or dig(resp, "template_id")
    return {"ok": True, "http": code, "response": resp, "vendor_template_id": str(tid or t["template_name"]), "request": payload}


def wsp_status(t, conf, vendor):
    if not conf.get("status_url"):
        return {"status": "PENDING", "error": f"{vendor}: no status URL set; waiting for webhook."}
    url = conf["status_url"].replace("{id}", urllib.parse.quote(t["vendor_template_id"])) \
                            .replace("{name}", urllib.parse.quote(t["template_name"])) \
                            .replace("{waba_id}", t.get("waba_id") or conf.get("waba_id", ""))
    url, headers = auth(conf, url)
    code, resp = http_call("GET", url, headers=headers)
    if code != 200:
        return {"status": "PENDING", "error": f"{vendor} status HTTP {code}"}
    return {"status": norm_status(dig(resp, conf.get("status_path") or "status")),
            "category": dig(resp, conf.get("category_path") or "category"),
            "reason": dig(resp, conf.get("reason_path") or "rejected_reason")}


def vendor_create(t, settings):
    if settings["mode"] == "simulate":
        return sim_create(t)
    conf = settings["vendors"].get(t["vendor"])
    if not conf:
        return {"ok": False, "error": f"Unknown vendor {t['vendor']}"}
    return meta_create(t, conf) if conf.get("type") == "meta" else wsp_create(t, conf, t["vendor"], settings)


def vendor_status(t, settings):
    if settings["mode"] == "simulate" or t["vendor_template_id"].startswith("sim_"):
        return sim_status(t)
    conf = settings["vendors"].get(t["vendor"], {})
    return meta_status(t, conf) if conf.get("type") == "meta" else wsp_status(t, conf, t["vendor"])


def webengage_push(t, settings):
    """WebEngage has no public template API: use a configured endpoint if WebEngage gives one, else manual add."""
    packet = webengage_packet(t, settings)
    w = settings["webengage"]
    if settings["mode"] == "simulate":
        return {"ok": True, "id": "we_sim_" + hashlib.sha1(t["template_name"].encode()).hexdigest()[:8], "packet": packet,
                "response": {"status": "success", "simulated": True}}
    if not (w.get("api_key") and w.get("template_api_url")):
        return {"ok": False, "manual": True, "packet": packet,
                "error": "No WebEngage template endpoint configured - add this template in WebEngage and confirm here."}
    url = w["template_api_url"].replace("{license_code}", urllib.parse.quote(w.get("license_code", "")))
    code, resp = http_call("POST", url, packet, {"Authorization": f"Bearer {w['api_key']}"})
    if code not in (200, 201):
        return {"ok": False, "packet": packet, "response": resp, "error": f"WebEngage returned HTTP {code}"}
    tid = dig(resp, "response.data.id") or dig(resp, "data.id") or dig(resp, "id") or t["template_name"]
    return {"ok": True, "id": str(tid), "packet": packet, "response": resp}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
def find_tpl(cal, tid):
    return next((t for t in cal["templates"] if t["id"] == tid), None)


def log(t, event, **detail):
    t.setdefault("history", []).append({"at": now_iso(), "event": event, **{k: v for k, v in detail.items() if k != "response"}})
    t["history"] = t["history"][-60:]
    audit(event, template=t["template_name"], template_id=t["id"], **{k: v for k, v in detail.items() if k != "response"})


def lock_calendar(by):
    settings = load_settings()
    with LOCK:
        cal = load_calendar()
        if cal.get("locked"):
            return 409, {"error": "Already locked"}
        drafts = [t for t in cal["templates"] if t["status"] == "DRAFT"]
        blocked = [{"id": t["id"], "template_name": t["template_name"], "errors": validate(t)["errors"]}
                   for t in drafts if not validate(t)["ok"]]
        if blocked:
            return 422, {"error": f"{len(blocked)} WhatsApp template(s) need fixing before the calendar can be locked.",
                         "blocked": blocked}
        cal.update(locked=True, locked_at=now_iso(), locked_by=by or "marketer")
        use = template_usage(cal)
        for t in sorted(drafts, key=lambda x: date_sort(use[x["id"]]["first"]) if x["id"] in use else (99, 0)):
            # one-by-one order: earliest first send goes first
            t.update(status="QUEUED", queued_at=now_iso())
            t["queue_order"] = date_sort(use[t["id"]]["first"]) if t["id"] in use else (99, 0)
            log(t, "queued", by=cal["locked_by"])
        save_calendar(cal)
        audit("calendar_locked", by=cal["locked_by"], queued=len(drafts), mode=settings["mode"])
    QUEUE_WAKE.set()
    return 200, public_calendar(cal)


def unlock_calendar(by):
    with LOCK:
        cal = load_calendar()
        if not cal.get("locked"):
            return 409, {"error": "Not locked"}
        cal.update(locked=False, locked_at="", locked_by="")
        for t in cal["templates"]:
            if t["status"] == "QUEUED":
                t["status"] = "DRAFT"
                log(t, "unqueued", by=by)
        save_calendar(cal)
        audit("calendar_unlocked", by=by)
    return 200, public_calendar(cal)


def submit(tid):
    """Send one template to its vendor. Called by the queue worker, one template at a time."""
    settings = load_settings()
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t or t["status"] != "QUEUED":
            return
        v = validate(t)
        if not v["ok"]:
            t.update(status="ERROR", reason="Fix the template: " + v["errors"][0])
            log(t, "submit_blocked", error=t["reason"])
            save_calendar(cal)
            return
        t["status"] = "SUBMITTING"
        save_calendar(cal)
        snapshot = dict(t)
    res = vendor_create(snapshot, settings)  # outside the lock - network call
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        t["attempts"] = int(t.get("attempts") or 0) + 1
        t["last_request"] = res.get("request") or vendor_payload(t, settings)
        t["last_response"] = res.get("response")
        t.pop("edit_in_place", None)
        if res.get("ok"):
            t.update(status="PENDING", vendor_template_id=res["vendor_template_id"], submitted_at=now_iso(),
                     approved_category="", reason="", webengage_template_id="")
            log(t, "submitted", vendor=t["vendor"], mode=settings["mode"], vendor_template_id=t["vendor_template_id"],
                http=res.get("http"), attempt=t["attempts"])
        else:
            t.update(status="ERROR", reason=res.get("error", "Vendor call failed"))
            log(t, "submit_failed", vendor=t["vendor"], error=t["reason"], http=res.get("http"))
        save_calendar(cal)


def apply_decision(tid, decision, settings, source):
    """Vendor said APPROVED/REJECTED/PAUSED. Enforce the same-category rule, then the WebEngage step."""
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t or t["status"] != "PENDING":
            return
        st = decision.get("status")
        if st == "PENDING":
            return
        t["decided_at"] = now_iso()
        t["reason"] = decision.get("reason") or ""
        if st != "APPROVED":
            t["status"] = st
            log(t, "vendor_" + st.lower(), source=source, reason=t["reason"])
            save_calendar(cal)
            return
        t["approved_category"] = str(decision.get("category") or t["category"]).upper()
        if t["approved_category"] != t["category"]:
            t["status"] = "CATEGORY_CHANGED"
            log(t, "category_changed", source=source, requested=t["category"], approved=t["approved_category"], reason=t["reason"])
            save_calendar(cal)
            return
        t["status"] = "WE_PUSHING"
        log(t, "vendor_approved", source=source, category=t["approved_category"])
        save_calendar(cal)
    push_to_webengage(tid, settings)


def push_to_webengage(tid, settings=None):
    settings = settings or load_settings()
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t:
            return 404, {"error": "Template not found"}
        if t["status"] not in ("WE_PUSHING", "WE_ERROR", "WE_MANUAL"):
            return 409, {"error": f"Template is {t['status']}; only approved templates go to WebEngage."}
        if t.get("approved_category") != t["category"]:
            return 409, {"error": "Approved category differs from the one requested - not added to WebEngage."}
        snapshot = dict(t)
    res = webengage_push(snapshot, settings)
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        t["webengage_packet"] = res.get("packet")
        if res.get("ok"):
            t.update(status="IN_WEBENGAGE", webengage_template_id=res["id"], pushed_at=now_iso(), reason="")
            log(t, "webengage_added", id=res["id"], mode=settings["mode"])
        else:
            t.update(status="WE_MANUAL" if res.get("manual") else "WE_ERROR", reason=res["error"])
            log(t, "webengage_manual" if res.get("manual") else "webengage_failed", error=res["error"])
        save_calendar(cal)
        return (200 if res.get("ok") else 502), {"template": t}


def confirm_manual(tid, ref, by):
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t or t["status"] not in ("WE_MANUAL", "WE_ERROR"):
            return 409, {"error": "Only templates waiting for the WebEngage step can be confirmed."}
        if not ref:
            return 422, {"error": "Enter the template name or ID as it appears in WebEngage."}
        t.update(status="IN_WEBENGAGE", webengage_template_id=ref, pushed_at=now_iso(), reason="")
        log(t, "webengage_added_manually", id=ref, by=by)
        save_calendar(cal)
        return 200, {"template": t}


def resubmit(tid, by):
    """After a rejection / category change the marketer edits the copy and sends it back into the queue."""
    settings = load_settings()
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t or t["status"] not in NEEDS_EDIT:
            return 409, {"error": "Only rejected, re-categorised, paused or failed templates can be resubmitted."}
        v = validate(t)
        if not v["ok"]:
            return 422, {"error": "Fix the template first", "validation": v}
        meta = settings["vendors"].get(t["vendor"], {}).get("type") == "meta"
        if t["status"] in ("REJECTED", "PAUSED") and meta and t.get("vendor_template_id") and not t["vendor_template_id"].startswith("sim_"):
            t["edit_in_place"] = True  # Meta lets you edit a rejected/paused template under the same name
        elif t["status"] != "ERROR" or t.get("vendor_template_id"):
            # the old name is taken at Meta (an approved MARKETING / rejected template) -> next version
            t["version"] = int(t.get("version") or 1) + 1
            t["template_name"] = re.sub(r"_v\d+$", "", t["template_name"]) + f"_v{t['version']}"
        prev = t["status"]
        t.update(status="QUEUED", queued_at=now_iso(), approved_category="", reason="", webengage_template_id="",
                 vendor_template_id="" if not t.get("edit_in_place") else t["vendor_template_id"])
        t["queue_order"] = (0, 0)  # resubmissions go to the front of the queue
        log(t, "resubmitted", by=by, previous=prev, new_name=t["template_name"])
        save_calendar(cal)
    QUEUE_WAKE.set()
    return 200, {"template": t}


def update_template(tid, body):
    with LOCK:
        cal = load_calendar()
        t = find_tpl(cal, tid)
        if not t:
            return 404, {"error": "Template not found"}
        changes = {k: str(body[k]) for k in TEMPLATE_EDITABLE & body.keys() if str(body[k]) != str(t.get(k, ""))}
        if not changes:
            return 200, {"template": t}
        if t["status"] not in EDITABLE_STATES:
            return 409, {"error": f"Template is {t['status']} - it can only be edited when it is a draft or needs edits."}
        if "template_name" in changes and any(x["template_name"] == changes["template_name"] for x in cal["templates"] if x is not t):
            return 409, {"error": "Another template already uses that name."}
        if "vendor" in changes:
            vconf = load_settings()["vendors"].get(changes["vendor"], {})
            t["waba_id"] = vconf.get("waba_id", "")
            changes.setdefault("sender_number", vconf.get("sender_number", "") or t.get("sender_number", ""))
        t.update(changes)
        log(t, "edited", fields=sorted(changes))
        save_calendar(cal)
        return 200, {"template": t}


def update_row(rid, body):
    settings = load_settings()
    with LOCK:
        cal = load_calendar()
        if cal.get("locked"):
            return 409, {"error": "The calendar is locked. Unlock it to change campaign rows."}
        row = next((r for r in cal["rows"] if r["id"] == rid), None) if rid else None
        if rid and not row:
            return 404, {"error": "Row not found"}
        if not row:
            row = {"id": uuid.uuid4().hex[:12], **{k: "" for k in ROW_KEYS}}
            row.update(product="MKP", start_age="15", end_age="90", gender="A", location="IND", campaign_type="CO")
            cal["rows"].append(row)
        for k in set(ROW_KEYS) & body.keys():
            row[k] = str(body[k])
        if row.get("date") and not body.get("day"):
            m = re.match(r"(\d{1,2})", row["date"])
            if m:
                try:
                    row["day"] = datetime(cal["year"], cal["month"], int(m.group(1))).strftime("%A")
                except ValueError:
                    pass
        link_templates(cal, settings)
        save_calendar(cal)
        return 200, {"row": row}


def delete_row(rid):
    settings = load_settings()
    with LOCK:
        cal = load_calendar()
        if cal.get("locked"):
            return 409, {"error": "The calendar is locked."}
        cal["rows"] = [r for r in cal["rows"] if r["id"] != rid]
        link_templates(cal, settings)
        save_calendar(cal)
    return 200, {"ok": True}


def queue_worker():
    """Submits QUEUED templates one by one, earliest first send first."""
    while True:
        QUEUE_WAKE.wait(timeout=5)
        QUEUE_WAKE.clear()
        while True:
            cal = load_calendar()
            queued = [t for t in cal["templates"] if t["status"] == "QUEUED"]
            if not queued:
                break
            nxt = min(queued, key=lambda t: (tuple(t.get("queue_order") or (99, 0)), t.get("queued_at", "")))
            try:
                submit(nxt["id"])
            except Exception as e:  # noqa: BLE001 - keep the worker alive
                audit("queue_error", template=nxt.get("template_name"), error=str(e))
                with LOCK:
                    c = load_calendar()
                    t = find_tpl(c, nxt["id"])
                    if t and t["status"] in ("QUEUED", "SUBMITTING"):
                        t.update(status="ERROR", reason=f"Internal error: {e}")
                        save_calendar(c)
            time.sleep(max(0.5, float(load_settings().get("submit_gap_seconds") or 2)))


def poller():
    while True:
        settings = load_settings()
        interval = 3 if settings["mode"] == "simulate" else max(10, int(settings.get("poll_seconds") or 30))
        try:
            pending = [dict(t) for t in load_calendar()["templates"] if t["status"] == "PENDING"]
            for t in pending:
                decision = vendor_status(t, settings)
                if decision.get("status") != "PENDING":
                    apply_decision(t["id"], decision, settings, "poll")
        except Exception as e:  # noqa: BLE001 - keep the poller alive
            audit("poller_error", error=str(e))
        time.sleep(interval)


def handle_webhook(vendor, raw, signature):
    settings = load_settings()
    conf = settings["vendors"].get(vendor, {})
    secret = conf.get("webhook_secret", "")
    if not secret:
        return 403, {"error": f"No webhook secret configured for {vendor}"}
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature.strip()):
        return 401, {"error": "Invalid signature"}
    payload = json.loads(raw.decode("utf-8") or "{}")
    events = []
    for entry in payload.get("entry", []):  # Meta format (most WSPs relay it unchanged)
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            if ch.get("field") == "message_template_status_update":
                events.append((str(v.get("message_template_id", "")), v.get("message_template_name"),
                               {"status": norm_status(v.get("event")), "reason": v.get("reason")}))
            elif ch.get("field") == "template_category_update":
                events.append((str(v.get("message_template_id", "")), v.get("message_template_name"),
                               {"category_update": v.get("new_category")}))
    applied = []
    for vid, name, dec in events:
        t = next((x for x in load_calendar()["templates"] if x["vendor_template_id"] == vid or x["template_name"] == name), None)
        if not t:
            continue
        if "category_update" in dec:
            with LOCK:
                cal = load_calendar()
                find_tpl(cal, t["id"])["pending_category"] = dec["category_update"]
                save_calendar(cal)
            continue
        if dec["status"] == "APPROVED":
            dec["category"] = t.get("pending_category") or t["category"]
        apply_decision(t["id"], dec, settings, "webhook")
        applied.append(t["id"])
    return 200, {"applied": applied}


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def log_message(self, fmt_, *args):
        if args and "/api/calendar " not in str(args[0]) and "/api/templates " not in str(args[0]):
            super().log_message(fmt_, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # also static files: never let the browser run a stale app.js
        super().end_headers()

    def send(self, code, obj, ctype="application/json", extra=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def raw(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def body(self):
        try:
            return json.loads(self.raw().decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None

    def route(self):
        p = urllib.parse.urlparse(self.path)
        return p.path.rstrip("/") or "/", urllib.parse.parse_qs(p.query)

    def do_GET(self):
        path, qs = self.route()
        if path == "/api/calendar":
            return self.send(200, public_calendar(load_calendar()))
        if path == "/api/templates":  # light payload for polling
            c = public_calendar(load_calendar())
            return self.send(200, {k: c.get(k) for k in ("locked", "locked_at", "locked_by", "templates")})
        if path == "/api/settings":
            s = load_settings()
            return self.send(200, {"settings": redact(s), "requirements": requirements(s), "mode": s["mode"]})
        if path == "/api/export":
            wa = (qs.get("wa") or ["0"])[0] == "1"
            text, cal = export_sheet(with_wa=wa)
            name = (cal.get("name") or "calendar.csv").rsplit(".", 1)[0] + ("_with_whatsapp" if wa else "") + ".csv"
            return self.send(200, text.encode("utf-8"), "text/csv; charset=utf-8",
                             {"Content-Disposition": f'attachment; filename="{name}"'})
        m = re.fullmatch(r"/api/templates/([a-f0-9]+)/payload", path)
        if m:
            cal, s = load_calendar(), load_settings()
            t = find_tpl(cal, m.group(1))
            if not t:
                return self.send(404, {"error": "Template not found"})
            return self.send(200, {"vendor_payload": vendor_payload(t, s), "webengage_payload": webengage_packet(
                {**t, "approved_category": t.get("approved_category") or t["category"]}, s), "validation": validate(t)})
        if path == "/api/audit":
            try:
                with open(AUDIT_FILE, encoding="utf-8") as f:
                    lines = f.readlines()[-300:]
            except FileNotFoundError:
                lines = []
            return self.send(200, [json.loads(l) for l in reversed(lines)])
        if path.startswith("/webhooks/"):
            conf = load_settings()["vendors"].get("Meta Cloud API", {})
            if (qs.get("hub.mode") or [""])[0] == "subscribe" and conf.get("verify_token") and \
                    hmac.compare_digest((qs.get("hub.verify_token") or [""])[0], conf["verify_token"]):
                return self.send(200, (qs.get("hub.challenge") or [""])[0].encode(), "text/plain")
            return self.send(403, {"error": "verification failed"})
        if path.startswith("/api/"):
            return self.send(404, {"error": "Not found"})
        return super().do_GET()

    def do_POST(self):
        path, _ = self.route()
        if path.startswith("/webhooks/"):
            vendor = urllib.parse.unquote(path.split("/", 2)[2])
            vendor = {"meta": "Meta Cloud API", "trustsignal": "TrustSignal", "routemobile": "Route Mobile"}.get(vendor.lower(), vendor)
            raw = self.raw()
            try:
                return self.send(*handle_webhook(vendor, raw, self.headers.get("X-Hub-Signature-256")))
            except json.JSONDecodeError:
                return self.send(400, {"error": "Bad JSON"})
        if path == "/api/import":
            raw = self.raw().decode("utf-8-sig", "replace")
            try:
                name = urllib.parse.unquote(self.headers.get("X-File-Name") or "calendar.csv")
                return self.send(200, import_sheet(raw, name))
            except ValueError as e:
                return self.send(422, {"error": str(e)})
        b = self.body()
        if b is None:
            return self.send(400, {"error": "Body must be JSON"})
        by = str(b.get("by") or "marketer")[:80]
        if path == "/api/settings":
            s = save_settings(b)
            return self.send(200, {"settings": redact(s), "requirements": requirements(s)})
        if path == "/api/lock":
            return self.send(*lock_calendar(by))
        if path == "/api/unlock":
            return self.send(*unlock_calendar(by))
        if path == "/api/rows":
            return self.send(*update_row(None, b))
        m = re.fullmatch(r"/api/rows/([a-f0-9]+)(?:/(delete))?", path)
        if m:
            return self.send(*(delete_row(m.group(1)) if m.group(2) else update_row(m.group(1), b)))
        m = re.fullmatch(r"/api/templates/([a-f0-9]+)(?:/([a-z-]+))?", path)
        if m:
            tid, action = m.group(1), m.group(2)
            if action is None:
                return self.send(*update_template(tid, b))
            if action == "validate":
                cal, s = load_calendar(), load_settings()
                t = find_tpl(cal, tid)
                if not t:
                    return self.send(404, {"error": "Template not found"})
                d = {**t, **{k: str(v) for k, v in b.items() if k in TEMPLATE_EDITABLE}}
                return self.send(200, {"validation": validate(d), "vendor_payload": vendor_payload(d, s),
                                       "webengage_payload": webengage_packet({**d, "approved_category": d["category"]}, s)})
            if action == "resubmit":
                return self.send(*resubmit(tid, by))
            if action == "push-webengage":
                return self.send(*push_to_webengage(tid))
            if action == "confirm-webengage":
                return self.send(*confirm_manual(tid, str(b.get("reference", "")).strip(), by))
        return self.send(404, {"error": "Not found"})


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(CAL_FILE) and os.path.exists(SEED_FILE):
        with open(SEED_FILE, encoding="utf-8-sig") as f:
            import_sheet(f.read(), os.path.basename(SEED_FILE))
    with LOCK:  # a template caught mid-submit by a restart goes back to the queue
        c = load_calendar()
        for t in c["templates"]:
            if t["status"] == "SUBMITTING":
                t["status"] = "QUEUED"
        save_calendar(c)
    threading.Thread(target=poller, daemon=True).start()
    threading.Thread(target=queue_worker, daemon=True).start()
    with Server((HOST, PORT), Handler) as httpd:
        s = load_settings()
        print(f"Snapmint CRM Calendar  ->  http://{HOST}:{PORT}   (mode: {s['mode']})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
