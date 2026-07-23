#!/usr/bin/env python3
"""
UW API Discovery Helper

Captures and analyzes network traffic from myaccount.uw.co.uk using
browser DevTools HAR exports or manually pasted request/response pairs.

Usage:
    python discover_api.py parse-har capture.har          # Parse a HAR file
    python discover_api.py interactive                     # Interactive mode

Output:
    ~/.config/uw-api/discovered_endpoints.json            # Structured endpoint config
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "uw-api"
OUTPUT_PATH = CONFIG_DIR / "discovered_endpoints.json"

INTERACTIVE_INSTRUCTIONS = r"""
╔══════════════════════════════════════════════════════════════════╗
║           UW API Discovery Helper - Interactive Mode           ║
╚══════════════════════════════════════════════════════════════════╝

This script helps you discover API endpoints used by the Utility
Warehouse customer portal (myaccount.uw.co.uk).

Step 1: Open Chrome/Firefox DevTools
  - Press F12 (or Cmd+Option+I on Mac)
  - Go to the Network tab
  - Check "Preserve log"
  - Clear existing entries (the 🚫 button)

Step 2: Log in and capture traffic
  - Navigate to https://myaccount.uw.co.uk/
  - Log in with your credentials
  - Navigate to: Account overview, Energy usage, Bills list,
    Download a bill PDF, Meter readings page
  - Open a bill PDF if available

Step 3: Export the HAR file
  - Chrome: Right-click any request → "Save all as HAR with content"
  - Firefox: Click the gear icon → "Save All As HAR"
  - Save the file and note its path

Step 4: Run the parser
  python discover_api.py parse-har /path/to/capture.har

Alternatively, you can paste raw request/response pairs in the
interactive mode (type 'paste' to start).
"""


def parse_har(har_path: str) -> dict[str, Any]:
    with open(har_path) as f:
        har = json.load(f)

    log = har.get("log", har)
    entries = log.get("entries", [])

    endpoints: dict[str, Any] = defaultdict(dict)
    graphql_operations: set[str] = set()
    graphql_url: str = ""
    auth: dict[str, str] = {}
    cookies: set[str] = set()
    csrf_headers: set[str] = set()
    content_types: set[str] = set()
    base_urls: set[str] = set()

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        url = request.get("url", "")
        method = request.get("method", "")
        req_headers = {h["name"].lower(): h["value"] for h in request.get("headers", [])}
        res_headers = {h["name"].lower(): h["value"] for h in response.get("headers", [])}

        if "myaccount.uw.co.uk" not in url and "uw.co.uk" not in url:
            continue

        ct = res_headers.get("content-type", "")
        content_types.add(ct)

        host = _extract_host(url)
        base_urls.add(f"{host}/api" if host else "")

        for rh in res_headers:
            if "set-cookie" in rh:
                parts = rh.split("=")
                if parts:
                    cookies.add(parts[0])

        for name, _value in req_headers.items():
            if "csrf" in name.lower() or "xsrf" in name.lower():
                csrf_headers.add(name)

        path = _extract_path(url)

        if "/server/graphql" in url:
            graphql_url = _clean_url(url)
            post_data = request.get("postData", {})
            text = post_data.get("text", "")
            if text:
                try:
                    body = json.loads(text)
                    op = body.get("operationName")
                    if op:
                        graphql_operations.add(op)
                except json.JSONDecodeError:
                    pass
            continue

        if "/login" in path and method in ("POST", "post"):
            auth["login_url"] = _clean_url(url)
            auth["content_type"] = req_headers.get("content-type", "")
            _log_auth_bodies(request, response, auth)

        if "/api/" in url:
            _categorize_endpoint(path, method, url, req_headers, endpoints)

    base_url = _detect_base_url(endpoints, auth)
    if base_url:
        auth["login_url"] = auth.get("login_url", f"{base_url}/login")

    result: dict[str, Any] = {
        "base_url": base_url or "https://myaccount.uw.co.uk",
        "auth": auth,
        "endpoints": dict(endpoints),
    }
    if graphql_url:
        result["graphql_url"] = graphql_url
        result["graphql_operations"] = sorted(graphql_operations)
    if csrf_headers:
        auth["csrf_header"] = next(iter(csrf_headers))

    _print_summary(result, cookies, csrf_headers, content_types)
    return result


def _extract_host(url: str) -> str:
    match = re.search(r"https?://([^/]+)", url)
    return match.group(0).rstrip("/") if match else ""


def _extract_path(url: str) -> str:
    match = re.search(r"https?://[^/]+(/[^?#]*)", url)
    return match.group(1) if match else ""


def _clean_url(url: str) -> str:
    return re.sub(r"[?#].*", "", url)


def _log_auth_bodies(request: dict, response: dict, auth: dict) -> None:
    req_body = ""
    if "postData" in request:
        req_body = request["postData"].get("text", "")
    if req_body:
        try:
            auth["request_fields"] = list(json.loads(req_body).keys())
            auth["request_content_type"] = "application/json"
        except json.JSONDecodeError:
            from urllib.parse import parse_qs

            auth["request_fields"] = list(parse_qs(req_body).keys())
            auth["request_content_type"] = "application/x-www-form-urlencoded"
    else:
        auth["request_fields"] = []
    auth["response_code"] = response.get("status", 0)


def _categorize_endpoint(
    path: str, method: str, url: str, req_headers: dict, endpoints: dict
) -> None:
    clean_url = _clean_url(url)

    if re.search(r"/account", path, re.I):
        endpoints["account"]["account"] = clean_url
    elif re.search(r"/services", path, re.I):
        endpoints["account"]["services"] = clean_url
    elif re.search(r"/energy|/usage|/consumption", path, re.I):
        if re.search(r"/tariff", path, re.I):
            endpoints["energy"]["tariff"] = clean_url
        elif re.search(r"/history|/consumption", path, re.I):
            endpoints["energy"]["consumption"] = clean_url
        else:
            endpoints["energy"]["usage"] = clean_url
    elif re.search(r"/bill|/invoice", path, re.I):
        if re.search(r"/pdf", path, re.I):
            endpoints["bills"]["pdf_download"] = clean_url
        elif "GET" in method.upper() and re.search(r"/[a-f\d-]{8,}", path):
            endpoints["bills"]["detail"] = clean_url.rsplit("/", 1)[0]
        else:
            endpoints["bills"]["list"] = clean_url
    elif re.search(r"/meter", path, re.I):
        if re.search(r"/reading", path, re.I):
            if "POST" in method.upper():
                endpoints["meters"]["submit"] = clean_url
            else:
                endpoints["meters"]["readings"] = clean_url
        else:
            endpoints["meters"]["list"] = clean_url


def _detect_base_url(endpoints: dict, auth: dict) -> str | None:
    all_urls = [auth.get("login_url", "")]
    for cat in endpoints.values():
        for url in cat.values():
            all_urls.append(str(url))

    for url in all_urls:
        if url:
            match = re.match(r"(https?://[^/]+/api)", url)
            if match:
                return match.group(1)
    return None


def _print_summary(
    result: dict, cookies: set[str], csrf_headers: set[str], content_types: set[str]
) -> None:
    print("\n" + "=" * 60)
    print("API DISCOVERY RESULTS")
    print("=" * 60)

    print(f"\nBase URL: {result['base_url']}")
    print("\nAuth:")
    print(f"  Login URL: {result['auth'].get('login_url', 'Not found')}")
    print(f"  Request fields: {result['auth'].get('request_fields', [])}")
    print(f"  Content type: {result['auth'].get('request_content_type', 'N/A')}")

    if csrf_headers:
        print(f"\nCSRF Headers detected: {csrf_headers}")
        print(f"  -> CSRF header: {result['auth'].get('csrf_header', '')}")

    print(f"\nDetected Cookies: {sorted(cookies)}")
    print(f"\nContent Types: {sorted(content_types)}")

    if result.get("graphql_url"):
        print(f"\nGraphQL endpoint: {result['graphql_url']}")
        print(f"Operations ({len(result.get('graphql_operations', []))}):")
        for op in result.get("graphql_operations", []):
            print(f"  - {op}")

    print("\nEndpoints:")
    for category, eps in result.get("endpoints", {}).items():
        print(f"  [{category}]")
        for name, url in eps.items():
            print(f"    {name}: {url}")

    print("=" * 60)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def cmd_parse_har(args: list[str]) -> None:
    if not args:
        print("Usage: python discover_api.py parse-har <har_file>")
        sys.exit(1)

    har_path = args[0]
    if not os.path.exists(har_path):
        print(f"Error: File not found: {har_path}")
        sys.exit(1)

    result = parse_har(har_path)

    _ensure_dir(CONFIG_DIR)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nConfig written to: {OUTPUT_PATH}")
    print("The API library will automatically load this on next use.")


def cmd_validate(args: list[str]) -> None:
    path = Path(args[0]) if args else OUTPUT_PATH
    if not path.exists():
        print(f"No config found at {path}")
        print("Run 'parse-har' first to generate one.")
        sys.exit(1)

    data = json.loads(path.read_text())
    required = ["base_url", "auth", "endpoints"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"Config missing required keys: {missing}")
    else:
        print("Config is valid.")
        print(f"  Base URL: {data.get('base_url')}")
        print(f"  Login URL: {data.get('auth', {}).get('login_url')}")
        endpoint_categories = list(data.get("endpoints", {}).keys())
        print(f"  Endpoint categories: {endpoint_categories}")


def cmd_interactive(args: list[str]) -> None:
    print(INTERACTIVE_INSTRUCTIONS)

    entries: list[dict] = []

    while True:
        try:
            cmd = input("\ndiscover> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if cmd == "help":
            print("Commands:")
            print("  paste   - Paste a request/response pair (JSON)")
            print("  done    - Save and generate config")
            print("  show    - Show captured entries")
            print("  help    - Show this help")
            print("  quit    - Exit without saving")
        elif cmd == "quit":
            print("Exiting without saving.")
            sys.exit(0)
        elif cmd == "show":
            print(json.dumps(entries, indent=2) if entries else "No entries captured.")
        elif cmd == "done":
            _ensure_dir(CONFIG_DIR)
            temp_har = OUTPUT_PATH.with_suffix(".temp.har")
            har = {"log": {"entries": entries}}
            temp_har.write_text(json.dumps(har, indent=2))
            result = parse_har(str(temp_har))
            OUTPUT_PATH.write_text(json.dumps(result, indent=2))
            temp_har.unlink()
            print(f"\nConfig written to: {OUTPUT_PATH}")
            break
        elif cmd == "paste":
            print('Paste request+response JSON (format: {"request": {...}, "response": {...}}),')
            print("type 'END' on a new line when done:")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            try:
                entry = json.loads("\n".join(lines))
                entries.append(entry)
                print(f"Captured 1 entry. Total: {len(entries)}")
            except json.JSONDecodeError as exc:
                print(f"Error parsing JSON: {exc}")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for help.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python discover_api.py parse-har <har_file>")
        print("  python discover_api.py validate [config_path]")
        print("  python discover_api.py interactive")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "parse-har":
        cmd_parse_har(args)
    elif command == "validate":
        cmd_validate(args)
    elif command == "interactive":
        cmd_interactive(args)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
