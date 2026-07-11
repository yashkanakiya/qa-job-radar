#!/usr/bin/env python3
"""
QA Job Radar - hosted scanner
Runs on a GitHub Actions schedule. Checks public remote-job APIs for
QA / manual-tester roles, scores them against Yash's resume skills,
extracts any email/phone in the description, and emails a digest of
NEW matches (jobs it hasn't already reported) to a target inbox.

Nothing here touches Indeed or LinkedIn directly - both block automated
access for every tool, not just this one. This covers the sources that
allow it: RemoteOK, Remotive, Arbeitnow.
"""

import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests

STATE_FILE = Path("seen_jobs.json")

RESUME_SKILLS = [
    "manual testing", "cypress", "automation", "postman", "api testing",
    "regression", "smoke testing", "sanity testing", "functional testing",
    "exploratory testing", "cross-browser", "responsive testing",
    "test case", "test planning", "bug reporting", "defect life cycle",
    "agile", "scrum", "ci/cd", "github actions", "javascript", "typescript",
    "rest api", "sql", "docker", "jenkins", "aws", "terraform", "linux",
    "qa", "tester", "quality assurance", "remote",
]

ROLE_KEYWORDS = [
    "qa", "quality assurance", "tester", "test engineer",
    "manual test", "sdet", "software tester",
]


def load_seen():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen)))


def score_match(text):
    text = (text or "").lower()
    hits = sum(1 for s in RESUME_SKILLS if s in text)
    return min(100, round((hits / len(RESUME_SKILLS)) * 100 * 1.8))


def is_role_match(title, desc):
    blob = f"{title} {desc}".lower()
    return any(k in blob for k in ROLE_KEYWORDS)


def is_india(text):
    t = (text or "").lower()
    return "india" in t


def extract_contacts(text):
    import re
    if not text:
        return [], []
    emails = list(dict.fromkeys(re.findall(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))
    phones_raw = re.findall(
        r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}", text)
    phones = []
    for p in phones_raw:
        digits = re.sub(r"\D", "", p)
        if len(digits) >= 8 and p.strip() not in phones:
            phones.append(p.strip())
    return emails, phones


def fetch_remoteok():
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", timeout=20,
                          headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        for item in data[1:] if isinstance(data, list) else []:
            title = item.get("position", "")
            desc = item.get("description", "") + " " + " ".join(item.get("tags", []))
            if not is_role_match(title, desc):
                continue
            jobs.append({
                "id": f"remoteok:{item.get('id')}",
                "title": title,
                "company": item.get("company", "Unknown"),
                "location": item.get("location", "Remote"),
                "url": item.get("url") or item.get("apply_url", ""),
                "source": "RemoteOK",
                "description": item.get("description", ""),
            })
    except Exception as e:
        print(f"[warn] RemoteOK fetch failed: {e}")
    return jobs


def fetch_remotive():
    jobs = []
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": "qa tester"}, timeout=20,
            headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        for item in data.get("jobs", []):
            title = item.get("title", "")
            desc = item.get("description", "")
            if not is_role_match(title, desc):
                continue
            jobs.append({
                "id": f"remotive:{item.get('id')}",
                "title": title,
                "company": item.get("company_name", "Unknown"),
                "location": item.get("candidate_required_location", "Remote"),
                "url": item.get("url", ""),
                "source": "Remotive",
                "description": desc,
            })
    except Exception as e:
        print(f"[warn] Remotive fetch failed: {e}")
    return jobs


def fetch_arbeitnow():
    jobs = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                          timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        for item in data.get("data", []):
            if not item.get("remote"):
                continue
            title = item.get("title", "")
            desc = item.get("description", "")
            if not is_role_match(title, desc):
                continue
            jobs.append({
                "id": f"arbeitnow:{item.get('slug', title)}",
                "title": title,
                "company": item.get("company_name", "Unknown"),
                "location": item.get("location", "Remote"),
                "url": item.get("url", ""),
                "source": "Arbeitnow",
                "description": desc,
            })
    except Exception as e:
        print(f"[warn] Arbeitnow fetch failed: {e}")
    return jobs


def build_email_body(new_jobs):
    india_first = sorted(new_jobs, key=lambda j: (not j["india"], -j["match"]))
    lines = [f"QA Job Radar - {len(new_jobs)} new match(es) this scan\n"]
    for j in india_first:
        lines.append("-" * 60)
        lines.append(f"{j['title']}  ({j['match']}% match)")
        lines.append(f"{j['company']}  |  {j['location']}  |  {j['source']}")
        if j["india"]:
            lines.append("Flag: India")
        if j["emails"]:
            lines.append("Email found: " + ", ".join(j["emails"]))
        if j["phones"]:
            lines.append("Phone found: " + ", ".join(j["phones"]))
        if j["url"]:
            lines.append(f"Link: {j['url']}")
        lines.append("")
    return "\n".join(lines)


def send_email(body, new_count):
    sender = os.environ["EMAIL_ADDRESS"]
    app_password = os.environ["EMAIL_APP_PASSWORD"]
    recipient = os.environ.get("EMAIL_TO", sender)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"QA Job Radar: {new_count} new QA/tester match(es)"
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())


def main():
    seen = load_seen()
    all_jobs = fetch_remoteok() + fetch_remotive() + fetch_arbeitnow()

    new_jobs = []
    for j in all_jobs:
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        j["match"] = score_match(f"{j['title']} {j['description']}")
        j["india"] = is_india(f"{j['title']} {j['location']} {j['description']}")
        j["emails"], j["phones"] = extract_contacts(j["description"])
        new_jobs.append(j)

    print(f"Fetched {len(all_jobs)} total, {len(new_jobs)} new.")

    if new_jobs:
        body = build_email_body(new_jobs)
        try:
            send_email(body, len(new_jobs))
            print("Email sent.")
        except Exception as e:
            print(f"[error] Email send failed: {e}")
    else:
        print("No new matches this run - no email sent.")

    save_seen(seen)


if __name__ == "__main__":
    main()
