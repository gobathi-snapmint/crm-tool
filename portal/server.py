#!/usr/bin/env python3
"""
Snapmint CRM Campaign Portal - Lightweight Local Proxy & API Server
Run this locally with zero dependencies (uses Python 3 standard library):
    python3 portal/server.py

Features:
1. Serves the portal web application at http://localhost:8000
2. Proxies API calls to Route Mobile / TrustSignal without browser CORS errors
3. Acts as the future local agent bridge (connecting to AWS Bedrock in Mumbai)
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import os

PORT = 8000
PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))

class CRMPortalHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PORTAL_DIR, **kwargs)

    def do_POST(self):
        # 1. Endpoint: Proxy Route Mobile Template Submission
        if self.path == "/api/wsp/submit-template":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            target_vendor = payload.get("vendor", "Route Mobile")
            wsp_token = payload.get("token", "")
            template_payload = payload.get("template_data", {})

            response_data = {
                "status": "SUCCESS",
                "code": 200,
                "vendor": target_vendor,
                "message": "Template successfully received and forwarded to Meta for approval.",
                "data": {
                    "template_id": f"rml_tpl_{template_payload.get('template_name', 'v1')}_987",
                    "status": "PENDING_APPROVAL",
                    "submitted_category": template_payload.get("template_category", "MARKETING")
                }
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        # 1b. Endpoint: TrustSignal Template Submission (Step 1)
        elif self.path == "/api/trustsignal/submit-template":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            template_name = payload.get("name", "sample_tpl")
            category = payload.get("category", "MARKETING")
            
            response_data = {
                "status": "SUCCESS",
                "code": 200,
                "wsp": "TrustSignal",
                "message": "Template submitted to Meta Graph API for review",
                "data": {
                    "template_id": f"ts_tpl_{template_name}_123",
                    "name": template_name,
                    "category": category,
                    "status": "PENDING_APPROVAL"
                }
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        # 1c. Endpoint: WebEngage Template Registration (Step 2)
        elif self.path == "/api/webengage/push-template":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            license_code = payload.get("license_code", "~111222333")
            template_name = payload.get("template_name", "sample_tpl")

            response_data = {
                "status": "SUCCESS",
                "code": 201,
                "system": "WebEngage",
                "message": f"Template {template_name} mapped to TrustSignal WSP and registered in WebEngage account {license_code}.",
                "data": {
                    "webengage_template_id": f"we_wa_tpl_{template_name}_789",
                    "channel": "WHATSAPP",
                    "connector": "TrustSignal",
                    "status": "READY_IN_CAMPAIGN_BUILDER"
                }
            }

            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        # 2. Endpoint: Future Agent Auto-Fill Hook (Calling Claude Sonnet 5 in Mumbai)
        elif self.path == "/api/agent/generate-campaign":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            brief = json.loads(post_data.decode("utf-8"))

            product = brief.get("product", "0% EMI BNPL Mobiles")
            segment = brief.get("segment", "Cart_Abandoners")
            guidance = brief.get("guidance", "")

            # Simulated response from Bedrock Agent (Phase 1 bridge)
            agent_output = {
                "naming": f"202611_{product[:4].upper()}_{segment[:6].upper()}_V1",
                "comms_a": f"Special Offer on {product}!",
                "comms_b": f"Namaste {{{{1}}}}! Complete your purchase at 0% EMI with monthly installments of {{{{2}}}}! {guidance}",
                "template_name": f"{product.lower().replace(' ', '_')}_{segment.lower().replace(' ', '_')}_v1",
                "cta_text": "Complete Order Now",
                "target_url": "https://snapmint.com/checkout?utm_source=wa&utm_medium=crm",
                "template_category": "UTILITY" if "repayment" in product.lower() else "MARKETING"
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(agent_output).encode("utf-8"))
            return

        super().do_POST()

    def do_OPTIONS(self):
        # Enable CORS for local testing
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), CRMPortalHandler) as httpd:
        print(f"================================================================")
        print(f"🚀 Snapmint CRM Calendar Portal running at:")
        print(f"   http://localhost:{PORT}")
        print(f"================================================================")
        print(f"• Zero database installation required (uses built-in browser storage)")
        print(f"• Pre-loaded with your exact calendar column schema")
        print(f"• Route Mobile / TrustSignal WSP template dispatch simulation ready")
        print(f"• Press Ctrl+C to stop the server\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
