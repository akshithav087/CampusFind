
from datetime import date
from email.message import EmailMessage
from hashlib import sha256
import os
from pathlib import Path
import re
import smtplib
import ssl
from urllib.parse import urlencode
from uuid import uuid4

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from db import get_db_connection


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FOLDER = PROJECT_ROOT / "frontend"
app = Flask(
    __name__,
    static_folder=str(FRONTEND_FOLDER),
    static_url_path=""
)
CORS(app, origins=[
    os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5000"),
    "http://127.0.0.1:5500",
    "http://localhost:5500"
])

# Maximum total request size: 5 MB
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

UPLOAD_FOLDER = Path(
    os.getenv("UPLOAD_FOLDER", Path(__file__).resolve().parent / "uploads")
)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def public_item(item):
    """Return public item details without the reporter's private email."""
    if item is None:
        return None

    item = dict(item)

    item.pop("reporter_email", None)

    if item.get("image_url"):
        image_path = item["image_url"]

        if image_path.startswith("/"):
            item["image_url"] = (
                request.host_url.rstrip("/") + image_path
            )

    return item


def send_contact_email(item, sender_name, sender_email, message, token):
    """Email the reporter a message and a private return-confirmation link."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM") or smtp_username or ""

    if not all((smtp_host, smtp_username, smtp_password, from_email)):
        raise RuntimeError("Email delivery is not configured on this site.")

    frontend_url = os.getenv(
        "FRONTEND_BASE_URL", "http://127.0.0.1:5000"
    ).rstrip("/")
    confirm_url = (
        f"{frontend_url}/item.html?"
        + urlencode({"id": item["id"], "confirmToken": token})
    )

    email = EmailMessage()
    email["Subject"] = f"CampusFind: message about {item['title']}"
    email["From"] = from_email
    email["To"] = item["reporter_email"]
    email["Reply-To"] = f"{sender_name} <{sender_email}>"
    email.set_content(
        f"Hello {item['reporter_name']},\n\n"
        f"{sender_name} contacted you about your CampusFind report, "
        f"\"{item['title']}\":\n\n{message}\n\n"
        "You can reply directly to this email to communicate with them.\n\n"
        "If your item has been returned to you, confirm it here:\n"
        f"{confirm_url}\n\n"
        "Only use this link after you have received your item. "
        "Confirming will remove the report from Browse Items."
    )

    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    context = ssl.create_default_context()

    if use_ssl:
        with smtplib.SMTP_SSL(
            smtp_host, port, context=context, timeout=20
        ) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(email)
    else:
        with smtplib.SMTP(smtp_host, port, timeout=20) as server:
            if use_tls:
                server.starttls(context=context)
            server.login(smtp_username, smtp_password)
            server.send_message(email)


def save_uploaded_image(file):
    """Validate and save an optional uploaded image."""
    if file is None or not file.filename:
        return None

    original_name = secure_filename(file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Use a JPG, PNG, WEBP or GIF image."
        )

    # Check the file signature rather than trusting its extension.
    file.stream.seek(0)
    header = file.stream.read(12)
    file.stream.seek(0)

    valid_signature = (
        (
            extension in ("jpg", "jpeg")
            and header.startswith(b"\xff\xd8\xff")
        )
        or (
            extension == "png"
            and header.startswith(b"\x89PNG\r\n\x1a\n")
        )
        or (
            extension == "gif"
            and header.startswith((b"GIF87a", b"GIF89a"))
        )
        or (
            extension == "webp"
            and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
        )
    )

    if not valid_signature:
        raise ValueError(
            "The selected file is not a valid supported image."
        )

    filename = f"{uuid4().hex}.{extension}"
    file.save(UPLOAD_FOLDER / filename)

    return f"/api/uploads/{filename}"


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "error": "The upload is too large. Maximum request size is 5 MB."
    }), 413


@app.route("/api/uploads/<path:filename>", methods=["GET"])
def uploaded_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/", methods=["GET"])
def frontend_home():
    return send_from_directory(FRONTEND_FOLDER, "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT 1")
        finally:
            cur.close()

        return jsonify({
            "status": "success",
            "message": "Flask and PostgreSQL are connected!"
        }), 200

    except Exception:
        app.logger.exception("Database connection failed")

        return jsonify({
            "error": "Database connection failed. Check configuration."
        }), 500

    finally:
        if conn is not None:
            conn.close()


@app.route("/api/items", methods=["GET"])
def get_items():
    conn = None
    cur = None

    try:
        status = request.args.get("status", "").strip().lower()
        category = request.args.get("category", "").strip()
        search = request.args.get("q", "").strip()

        if status and status not in ("lost", "found"):
            return jsonify({
                "error": "Status must be lost or found."
            }), 400

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, title, description, category, status,
                   location, item_date, image_url,
                   reporter_name, is_resolved, created_at
            FROM items
            WHERE is_resolved = FALSE
              AND (%s = '' OR status = %s)
              AND (%s = '' OR category ILIKE %s)
              AND (
                    %s = ''
                    OR title ILIKE %s
                    OR description ILIKE %s
                    OR location ILIKE %s
                  )
            ORDER BY created_at DESC
        """, (
            status, status,
            category, f"%{category}%",
            search,
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

        items = cur.fetchall()

        return jsonify([
            public_item(item) for item in items
        ]), 200

    except Exception:
        app.logger.exception("Failed to retrieve items")

        return jsonify({
            "error": "Could not retrieve items."
        }), 500

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, title, description, category, status,
                   location, item_date, image_url,
                   reporter_name, is_resolved, created_at
            FROM items
            WHERE id = %s
        """, (item_id,))

        item = cur.fetchone()

        if item is None:
            return jsonify({
                "error": "Item not found."
            }), 404

        return jsonify(public_item(item)), 200

    except Exception:
        app.logger.exception("Failed to retrieve item")

        return jsonify({
            "error": "Could not retrieve the item."
        }), 500

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


@app.route("/api/items/<int:item_id>/contact", methods=["POST"])
def contact_reporter(item_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Please send valid contact details."}), 400

    sender_name = str(data.get("name", "")).strip()
    sender_email = str(data.get("email", "")).strip()
    message = str(data.get("message", "")).strip()
    if not sender_name or not sender_email or not message:
        return jsonify({"error": "Name, email, and message are required."}), 400
    if len(sender_name) > 100 or len(sender_email) > 150 or len(message) > 5000:
        return jsonify({"error": "Please shorten the contact details or message."}), 400
    if any(ord(character) < 32 for character in sender_name):
        return jsonify({"error": "Please enter a valid name."}), 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", sender_email):
        return jsonify({"error": "Please provide a valid email address."}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, reporter_name, reporter_email, is_resolved
            FROM items
            WHERE id = %s
        """, (item_id,))
        item = cur.fetchone()
        if item is None:
            return jsonify({"error": "Item not found."}), 404
        if item["is_resolved"]:
            return jsonify({"error": "This report has already been marked reunited."}), 409

        token = uuid4().hex + uuid4().hex
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        cur.execute(
            "UPDATE items SET resolution_token_hash = %s WHERE id = %s",
            (token_hash, item_id)
        )
        conn.commit()

        try:
            send_contact_email(item, sender_name, sender_email, message, token)
        except RuntimeError as error:
            cur.execute(
                "UPDATE items SET resolution_token_hash = NULL "
                "WHERE id = %s AND resolution_token_hash = %s",
                (item_id, token_hash)
            )
            conn.commit()
            return jsonify({"error": str(error)}), 503
        except Exception:
            app.logger.exception("Could not send reporter contact email")
            cur.execute(
                "UPDATE items SET resolution_token_hash = NULL "
                "WHERE id = %s AND resolution_token_hash = %s",
                (item_id, token_hash)
            )
            conn.commit()
            return jsonify({"error": "Could not send the message. Please try again later."}), 502

        return jsonify({
            "message": "Your message was emailed to the reporter. They can reply directly to you."
        }), 200
    except Exception:
        if conn is not None:
            conn.rollback()
        app.logger.exception("Failed to contact item reporter")
        return jsonify({"error": "Could not send your message."}), 500
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


@app.route("/api/items/<int:item_id>/confirm-return", methods=["POST"])
def confirm_item_return(item_id):
    data = request.get_json(silent=True)
    token = data.get("token", "") if isinstance(data, dict) else ""
    if not isinstance(token, str) or len(token) != 64:
        return jsonify({"error": "This confirmation link is invalid or expired."}), 400

    token_hash = sha256(token.encode("utf-8")).hexdigest()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE items
            SET is_resolved = TRUE, resolution_token_hash = NULL
            WHERE id = %s AND is_resolved = FALSE
              AND resolution_token_hash = %s
            RETURNING id
        """, (item_id, token_hash))
        item = cur.fetchone()
        if item is None:
            conn.rollback()
            return jsonify({"error": "This confirmation link is invalid or already used."}), 400

        conn.commit()
        return jsonify({
            "message": "Thanks for confirming. This report has been removed from Browse Items."
        }), 200
    except Exception:
        if conn is not None:
            conn.rollback()
        app.logger.exception("Failed to confirm item return")
        return jsonify({"error": "Could not update this report."}), 500
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


@app.route("/api/items", methods=["POST"])
def create_item():
    # Accept JSON and multipart form submissions.
    if request.is_json:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": "Please send valid JSON data."
            }), 400

        image_file = None
    else:
        data = request.form
        image_file = request.files.get("image")

    required = [
        "title",
        "description",
        "category",
        "status",
        "location",
        "reporter_name",
        "reporter_email"
    ]

    for field in required:
        value = data.get(field)

        if not isinstance(value, str) or not value.strip():
            return jsonify({
                "error": f"{field} is required."
            }), 400

    status = data["status"].strip().lower()

    if status not in ("lost", "found"):
        return jsonify({
            "error": "Status must be lost or found."
        }), 400

    email = data["reporter_email"].strip()

    if (
        "@" not in email
        or "." not in email.split("@")[-1]
        or any(char.isspace() for char in email)
    ):
        return jsonify({
            "error": "Please provide a valid email address."
        }), 400

    item_date = data.get("item_date") or None

    if item_date:
        try:
            date.fromisoformat(item_date)
        except (ValueError, TypeError):
            return jsonify({
                "error": "item_date must use YYYY-MM-DD format."
            }), 400

    image_url = None

    try:
        if image_file:
            image_url = save_uploaded_image(image_file)
        elif request.is_json:
            # Preserve compatibility with existing JSON clients.
            image_url = data.get("image_url") or None

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO items (
                title, description, category, status, location,
                item_date, image_url, reporter_name, reporter_email
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, title, description, category, status,
                      location, item_date, image_url,
                      reporter_name, created_at
        """, (
            data["title"].strip(),
            data["description"].strip(),
            data["category"].strip(),
            status,
            data["location"].strip(),
            item_date,
            image_url,
            data["reporter_name"].strip(),
            email
        ))

        item = cur.fetchone()
        conn.commit()

        return jsonify({
            "message": "Item reported successfully!",
            "item": public_item(item)
        }), 201

    except Exception:
        if conn is not None:
            conn.rollback()

        # Remove the uploaded file if the database insert fails.
        if image_url and image_file:
            filename = Path(image_url).name
            (UPLOAD_FOLDER / filename).unlink(missing_ok=True)

        app.logger.exception("Failed to create item")

        return jsonify({
            "error": "Could not save the item."
        }), 500

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


if __name__ == "__main__":
    app.run(debug=True)
