#!/usr/bin/env python3
"""
Gmail send utility using SMTP with App Password authentication.

Configuration:
  Preferred: create .env.local in the project root with:
    GMAIL_ADDRESS=your_email@gmail.com
    GMAIL_APP_PASSWORD=your_app_password

  Legacy fallback: ~/.gmail_send/.env with:
    GMAIL_ADDRESS=your_email@gmail.com
    GMAIL_APP_PASSWORD=your_app_password

Usage:
  python send_gmail.py --to recipient@example.com --subject "Subject" --body "Message"
  python send_gmail.py --to recipient@example.com --subject "Subject" --body "<h1>HTML</h1>" --html
  python send_gmail.py --to recipient@example.com --subject "Subject" --body "Message" --attachment /path/to/file.jpg
"""
import sys
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from pathlib import Path

from service_config import load_gmail_secret_config


def load_config():
    """Load Gmail configuration from .env.local with legacy fallback support."""
    config, _secret_source, error = load_gmail_secret_config()
    if error:
        return None, error
    return config, None


def send_email(to_addrs, subject, body, is_html=False, attachments=None,
               html_body=None, text_body=None, inline_images=None):
    """
    Send an email using Gmail SMTP with support for inline images.

    Args:
        to_addrs: List of recipient email addresses
        subject: Email subject
        body: Email body (plain text or HTML) - legacy parameter
        is_html: If True, body is treated as HTML - legacy parameter
        attachments: List of file paths to attach
        html_body: HTML content for the email (new parameter)
        text_body: Plain text fallback for the email (new parameter)
        inline_images: List of dicts with keys:
            - cid: Content-ID for referencing in HTML (e.g., "chart")
            - content: Image bytes
            - subtype: Image subtype (e.g., "jpeg", "png")

    Returns:
        tuple: (success: bool, message: str)
    """
    config, error = load_config()
    if error:
        return False, error

    # Determine if we're using the new multipart structure with inline images
    use_inline = html_body is not None and inline_images

    if use_inline:
        # Build multipart/related > multipart/alternative > [text/plain, text/html]
        # This structure allows HTML with inline images and a text fallback
        msg = MIMEMultipart('related')
        msg["From"] = config["email"]
        msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
        msg["Subject"] = subject

        # Create the alternative part for text/html
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        # Attach plain text fallback
        text_fallback = text_body or "This email requires an HTML-capable email client."
        msg_alternative.attach(MIMEText(text_fallback, 'plain', 'utf-8'))

        # Attach HTML body
        msg_alternative.attach(MIMEText(html_body, 'html', 'utf-8'))

        # Attach inline images
        for img_data in inline_images:
            img = MIMEImage(img_data['content'], _subtype=img_data.get('subtype', 'jpeg'))
            img.add_header('Content-ID', f"<{img_data['cid']}>")
            img.add_header('Content-Disposition', 'inline', filename=f"{img_data['cid']}.{img_data.get('subtype', 'jpeg')}")
            msg.attach(img)

        logging.info(f"Built multipart/related email with {len(inline_images)} inline image(s)")

    elif html_body is not None:
        # HTML email without inline images - use alternative for text fallback
        msg = MIMEMultipart('alternative')
        msg["From"] = config["email"]
        msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
        msg["Subject"] = subject

        # Attach plain text fallback
        text_fallback = text_body or "This email requires an HTML-capable email client."
        msg.attach(MIMEText(text_fallback, 'plain', 'utf-8'))

        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    else:
        # Legacy behavior - simple text or HTML body
        msg = MIMEMultipart()
        msg["From"] = config["email"]
        msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
        msg["Subject"] = subject

        # Attach body
        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body or "", content_type))

    # Attach files (regular attachments, not inline)
    if attachments:
        for filepath in attachments:
            path = Path(filepath)
            if not path.exists():
                return False, f"Attachment not found: {filepath}"

            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={path.name}"
            )
            msg.attach(part)

    # Send email
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(config["email"], config["app_password"])

        # Handle multiple recipients
        recipients = to_addrs if isinstance(to_addrs, list) else [to_addrs]
        server.sendmail(config["email"], recipients, msg.as_string())
        server.quit()
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed. Check your app password: {e}"
    except Exception as e:
        return False, f"Failed to send email: {e}"


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("\nAdditional options:")
        print("  --html-body FILE    Read HTML body from file (enables new multipart mode)")
        print("  --text-body FILE    Read plain text fallback from file")
        sys.exit(0)

    # Parse arguments
    to_addrs = []
    subject = None
    body = None
    is_html = False
    attachments = []
    html_body = None
    text_body = None

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--to" and i + 1 < len(sys.argv):
            # Support comma-separated recipients
            recipients = sys.argv[i + 1]
            to_addrs.extend([r.strip() for r in recipients.split(",")])
            i += 2
        elif arg == "--subject" and i + 1 < len(sys.argv):
            subject = sys.argv[i + 1]
            i += 2
        elif arg == "--body" and i + 1 < len(sys.argv):
            body = sys.argv[i + 1]
            i += 2
        elif arg == "--html-body" and i + 1 < len(sys.argv):
            # Read HTML body from file
            html_file = Path(sys.argv[i + 1])
            if html_file.exists():
                html_body = html_file.read_text()
            else:
                print(f"Error: HTML body file not found: {sys.argv[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg == "--text-body" and i + 1 < len(sys.argv):
            # Read text body from file
            text_file = Path(sys.argv[i + 1])
            if text_file.exists():
                text_body = text_file.read_text()
            else:
                print(f"Error: Text body file not found: {sys.argv[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg == "--html":
            is_html = True
            i += 1
        elif arg == "--attachment" and i + 1 < len(sys.argv):
            attachments.append(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    # Validate required arguments
    if not to_addrs:
        print("Error: --to is required")
        sys.exit(1)
    if not subject:
        print("Error: --subject is required")
        sys.exit(1)
    # Allow either --body or --html-body
    if body is None and html_body is None:
        print("Error: --body or --html-body is required")
        sys.exit(1)

    success, message = send_email(
        to_addrs, subject, body, is_html,
        attachments if attachments else None,
        html_body=html_body,
        text_body=text_body
    )
    print(message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
