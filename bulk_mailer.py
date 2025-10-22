"""
bulk_mailer.py

Send personalized bulk emails using SMTP (zero external packages required).

Usage example:
    python bulk_mailer.py --csv recipients.csv --subject "Hello {first}" --body body.txt \
        --smtp-server smtp.gmail.com --port 587 --user youremail@gmail.com --delay 2

CSV format (no header required) - columns:
    email,first,last
Example:
    alice@example.com,Alice,Smith
    bob@example.com,Bob,Jones

Template placeholders: {first}, {last}, {email}
Body file can be plain text or HTML (if html, set --html flag).
"""

import csv
import smtplib
import ssl
import time
import argparse
import os
from email.message import EmailMessage
from typing import List, Dict

def load_recipients(csv_path: str) -> List[Dict[str,str]]:
    recipients = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().startswith('#'):
                continue
            email = row[0].strip()
            first = row[1].strip() if len(row) > 1 else ""
            last  = row[2].strip() if len(row) > 2 else ""
            recipients.append({"email": email, "first": first, "last": last})
    return recipients

def load_file_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def build_message(sender: str, recipient: dict, subject_template: str, body_template: str,
                  is_html: bool=False, attachment_path: str=None) -> EmailMessage:
    msg = EmailMessage()
    subs = { "first": recipient.get("first",""), "last": recipient.get("last",""), "email": recipient.get("email","") }
    subject = subject_template.format(**subs)
    body = body_template.format(**subs)

    msg['From'] = sender
    msg['To'] = recipient["email"]
    msg['Subject'] = subject

    if is_html:
        msg.set_content("This email contains HTML. Open in an HTML-capable client.")
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    if attachment_path:
        try:
            with open(attachment_path, 'rb') as ap:
                data = ap.read()
                import mimetypes
                ctype, encoding = mimetypes.guess_type(attachment_path)
                if ctype is None:
                    maintype, subtype = 'application', 'octet-stream'
                else:
                    maintype, subtype = ctype.split('/', 1)
                filename = os.path.basename(attachment_path)
                msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        except Exception as e:
            print(f"Warning: failed to attach {attachment_path}: {e}")

    return msg

def send_bulk(smtp_server: str, port: int, user: str, password: str,
              sender_display: str, recipients: List[Dict[str,str]],
              subject_template: str, body_template: str, is_html: bool,
              attachment_path: str, delay: float, use_tls: bool=True):
    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_server, port, timeout=60) as server:
        server.ehlo()
        if use_tls:
            server.starttls(context=context)
            server.ehlo()
        server.login(user, password)

        sent = 0
        for i, r in enumerate(recipients, start=1):
            try:
                msg = build_message(sender_display or user, r, subject_template, body_template, is_html, attachment_path)
                server.send_message(msg)
                sent += 1
                print(f"[{i}/{len(recipients)}] Sent to {r['email']}")
            except Exception as e:
                print(f"[{i}/{len(recipients)}] ERROR sending to {r['email']}: {e}")
            if delay > 0 and i != len(recipients):
                time.sleep(delay)
        print(f"Done. Sent: {sent}/{len(recipients)}")

def main():
    parser = argparse.ArgumentParser(description="Bulk mailer using SMTP (no external libs).")
    parser.add_argument("--csv", required=True, help="CSV file with recipients: email,first,last")
    parser.add_argument("--subject", required=True, help="Subject template, supports {first}, {last}, {email}")
    parser.add_argument("--body", required=True, help="Path to body text file (plain or HTML if --html).")
    parser.add_argument("--smtp-server", default="smtp.gmail.com", help="SMTP host (default smtp.gmail.com)")
    parser.add_argument("--port", type=int, default=587, help="SMTP port (default 587)")
    parser.add_argument("--user", required=False, help="SMTP username (email). If omitted, uses ENV SMTP_USER")
    parser.add_argument("--password", required=False, help="SMTP password (or app password). If omitted, uses ENV SMTP_PASS")
    parser.add_argument("--sender-name", required=False, help="Optional display From name (e.g. 'Name <you@example.com>')")
    parser.add_argument("--html", action="store_true", help="Treat body as HTML and send an HTML email.")
    parser.add_argument("--attachment", required=False, help="Path to a single attachment file (optional).")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds to wait between emails (default 1.5s).")
    parser.add_argument("--no-tls", action="store_true", help="Don't use STARTTLS (not recommended).")
    args = parser.parse_args()

    user = args.user or os.getenv("SMTP_USER")
    password = args.password or os.getenv("SMTP_PASS")
    if not user or not password:
        print("Error: SMTP username and password required either via flags or environment variables SMTP_USER/SMTP_PASS.")
        print("For Gmail: create an App Password and use it here (requires 2FA).")
        return

    recipients = load_recipients(args.csv)
    if not recipients:
        print("No recipients loaded from CSV. Check file format.")
        return

    body_template = load_file_text(args.body)

    send_bulk(
        smtp_server=args.smtp_server,
        port=args.port,
        user=user,
        password=password,
        sender_display=args.sender_name,
        recipients=recipients,
        subject_template=args.subject,
        body_template=body_template,
        is_html=args.html,
        attachment_path=args.attachment,
        delay=args.delay,
        use_tls=(not args.no_tls)
    )

if __name__ == "__main__":
    main()
