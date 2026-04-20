from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import datetime
import re as _re

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── ENV
PAYSTACK_SECRET  = os.getenv("PAYSTACK_SECRET_KEY")
COHERE_API_KEY   = os.getenv("COHERE_API_KEY")
SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_SERVICE_KEY")
GMAIL_USER       = os.getenv("GMAIL_USER")
GMAIL_PASS       = os.getenv("GMAIL_APP_PASSWORD")
ADMIN_SECRET     = os.getenv("ADMIN_SECRET", "kindred-admin-2026")

OWNER_EMAILS = ["olawumimojisola52@gmail.com"]

print("=== Kindred Backend Starting ===")
print("Paystack key exists:", bool(PAYSTACK_SECRET))
print("Cohere key exists:", bool(COHERE_API_KEY))
print("Supabase URL:", SUPABASE_URL)
print("================================")


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


# STRICT SUBSCRIPTION CHECK
def get_subscription(email):
    if not email:
        return {"has_subscription": False, "plan": "free"}
    
    email = email.strip().lower()
    
    # Only owner is forced Pro
    if email in [e.strip().lower() for e in OWNER_EMAILS]:
        print(f"✅ OWNER FORCED PRO: {email}")
        return {"has_subscription": True, "plan": "pro"}
    
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/subscriptions?email=eq.{email}&status=eq.active&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        
        if rows and len(rows) > 0:
            plan = rows[0].get("plan", "free")
            print(f"✅ Paid subscription found: {email} → {plan}")
            return {"has_subscription": True, "plan": plan}
        
        print(f"User is Free: {email}")
        return {"has_subscription": False, "plan": "free"}
    except Exception as e:
        print(f"Subscription check error: {e}")
        return {"has_subscription": False, "plan": "free"}


def get_usage(email):
    month = datetime.datetime.now().strftime("%Y-%m")
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/usage?email=eq.{email}&month=eq.{month}&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        return rows[0].get("count", 0) if rows else 0
    except:
        return 0


def increment_usage(email):
    month = datetime.datetime.now().strftime("%Y-%m")
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/usage?email=eq.{email}&month=eq.{month}&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        if rows:
            count = rows[0].get("count", 0)
            record_id = rows[0].get("id")
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/usage?id=eq.{record_id}",
                headers=supabase_headers(),
                json={"count": count + 1}
            )
        else:
            requests.post(
                f"{SUPABASE_URL}/rest/v1/usage",
                headers=supabase_headers(),
                json={"email": email, "month": month, "count": 1}
            )
    except Exception as e:
        print("Usage increment error:", e)


# EMAIL FUNCTIONS (keep your original)
def send_email(to_email, subject, html, name=""):
    if not GMAIL_USER or not GMAIL_PASS:
        print("Gmail not configured")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Kindred <{GMAIL_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"Email failed: {e}")


def build_email_html(headline, body_html, cta_text="", cta_link="", name=""):
    # Paste your original build_email_html function here if you want (it's fine)
    # For brevity, I'm using a simple version. Replace with your full one if needed.
    bg_color = "#FFF5F5"
    accent_color = "#FF8A8A"
    text_dark = "#3D2B2B"
    greeting = f"Hi {name}," if name else "Hi there,"
    cta_button = f'''
    <div style="text-align:center;margin-top:32px;">
        <a href="{cta_link}" style="background:{accent_color}; color:#FFF5F5; padding:14px 36px; border-radius:50px; font-weight:700; text-decoration:none; font-size:0.95rem; display:inline-block;">
            {cta_text}
        </a>
    </div>''' if cta_text and cta_link else ""
    
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700&family=Inter:wght@400;500;600&display=swap');</style></head>
<body style="margin:0;padding:0;background:{bg_color};font-family:'Inter',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{bg_color};padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="text-align:center;padding-bottom:32px;">
  <h1 style="font-family:'Fraunces',Georgia,serif;color:{accent_color};font-size:2.4rem;margin:0 0 6px 0;">Kindred</h1>
</td></tr>
<tr><td style="background:#ffffff;border-radius:20px;border:2px solid {accent_color};padding:45px 40px;">
  <p style="color:{text_dark};font-size:1.05rem;margin:0 0 24px 0;line-height:1.6;">{greeting}</p>
  <h2 style="font-family:'Fraunces',Georgia,serif;color:{accent_color};font-size:1.75rem;margin:0 0 24px 0;line-height:1.3;">{headline}</h2>
  <div style="color:{text_dark};font-size:0.98rem;line-height:1.75;">{body_html}</div>
  {cta_button}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# MULTILINGUAL + DETECTION
MULTILINGUAL_PATTERNS = [
    _re.compile(r'\b(mo fe|e joo|jowo|bawo ni|ese|kilode|eyin|emi ni|se o)\b', _re.IGNORECASE),
    _re.compile(r'\b(dey|wetin|abeg|oga|sabi|sha|walahi)\b', _re.IGNORECASE),
    _re.compile(r'\b(yauwa|sannu|nagode|wallahi|insha allah)\b', _re.IGNORECASE),
    _re.compile(r'\b(bonjour|merci|je suis|comment|pourquoi)\b', _re.IGNORECASE),
]

def is_multilingual(text):
    return any(p.search(text) for p in MULTILINGUAL_PATTERNS)

def detect_language(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ['mo fe', 'jowo', 'bawo', 'kilode', 'ese']):
        return "yoruba"
    if any(word in text_lower for word in ['yauwa', 'sannu', 'nagode', 'wallahi']):
        return "hausa"
    if any(word in text_lower for word in ['bonjour', 'merci', 'je suis']):
        return "french"
    if any(word in text_lower for word in ['wetin', 'abeg', 'oga', 'sha']):
        return "pidgin"
    return "english"


# ROUTES
@app.route('/')
def homepage():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_html(filename):
    if filename.endswith(('.html', '.css', '.js')) or '.' not in filename:
        try:
            return send_from_directory('.', filename)
        except:
            return jsonify({"error": "File not found"}), 404
    return jsonify({"error": "File not found"}), 404


@app.route('/transform', methods=['POST'])
def transform():
    data = request.json or {}
    raw_text = data.get('text', '').strip()
    format_type = data.get('format', 'email').lower()
    tone = data.get('tone', 'professional')
    email = data.get('email', '').strip().lower()
    output_language = data.get('output_language', 'auto').lower()

    if not raw_text or not email:
        return jsonify({"success": False, "error": "Text and email required"})

    sub = get_subscription(email)
    is_pro = sub["has_subscription"]

    detected_lang = detect_language(raw_text)
    final_lang = output_language if output_language != 'auto' else detected_lang

    if not is_pro:
        if format_type not in ['email', 'conversation']:
            return jsonify({"success": False, "upgrade_required": True, "error": f"{format_type} is Pro only."})
        if is_multilingual(raw_text):
            return jsonify({"success": False, "upgrade_required": True, "error": "Multilingual is Pro only."})
        if get_usage(email) >= 5:
            return jsonify({"success": False, "upgrade_required": True, "error": "Free limit reached."})

    format_guides = {
        "email": "Write a professional email.",
        "conversation": "Write a natural WhatsApp-style message.",
        "proposal": "Write a business proposal.",
        "social_media_post": "Write an engaging social media post.",
        "content_strategy": "Create a content strategy.",
        "essay": "Write a well-structured essay.",
        "speech": "Write a powerful speech.",
        "teaching_explanation": "Explain clearly like teaching a beginner.",
        "product_description": "Write persuasive product description.",
        "cover_letter": "Write a strong cover letter."
    }

    guide = format_guides.get(format_type, "Write clearly.")

    lang_instruction = f"Respond entirely in {final_lang.capitalize()}." if final_lang != "english" else "Respond in natural English."

    prompt = f"""You are Kindred.
{lang_instruction}

FORMAT: {format_type.replace('_', ' ').upper()}
TONE: {tone}

{guide}

User wrote:
{raw_text}

Output ONLY the final text."""

    try:
        res = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
            json={"model": "command-a-03-2025", "messages": [{"role": "user", "content": prompt}]},
            timeout=35
        )
        result = res.json()
        output = result['message']['content'][0]['text'].strip() if 'message' in result else "Error"

        if not is_pro and email:
            increment_usage(email)

        return jsonify({"success": True, "output": output, "plan": sub["plan"]})

    except Exception as e:
        print(f"Transform error: {e}")
        return jsonify({"success": False, "error": "AI service error"})


# ENSURE FREE USER
@app.route('/ensure-free-user', methods=['POST'])
def ensure_free_user():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    if email in [e.strip().lower() for e in OWNER_EMAILS]:
        return jsonify({"success": True, "plan": "pro"})

    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/subscriptions?email=eq.{email}&select=*",
            headers=supabase_headers()
        )
        if not res.json():
            requests.post(
                f"{SUPABASE_URL}/rest/v1/subscriptions",
                headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
                json={"email": email, "plan": "free", "status": "active"}
            )
            print(f"✅ New user created as FREE: {email}")
        return jsonify({"success": True, "plan": "free"})
    except Exception as e:
        print(f"Ensure free user error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# CHECK SUBSCRIPTION
@app.route('/check-subscription', methods=['POST'])
def check_subscription():
    data = request.json or {}
    email = data.get('email', '')
    sub = get_subscription(email)
    return jsonify({"success": True, "has_subscription": sub["has_subscription"], "plan": sub["plan"]})


# PAYMENT ROUTES (Recurring)
@app.route('/pay/naira', methods=['POST'])
def pay_naira():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    currency = data.get('currency', 'NGN').upper()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "Valid email required"}), 400

    PAYSTACK_PLAN_CODE = "PLN_m8wf2yudi3jflnx"

    try:
        res = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}", "Content-Type": "application/json"},
            json={
                "email": email,
                "amount": 5000000,
                "currency": currency,
                "plan": PAYSTACK_PLAN_CODE,
                "callback_url": "https://kindred-evk6.onrender.com/kindred-callback.html",
                "metadata": {"plan": "pro", "currency": currency},
                "channels": ["card"]
            },
            timeout=15
        )
        result = res.json()

        if result.get('status') and result.get('data'):
            return jsonify({
                "success": True,
                "payment_url": result['data']['authorization_url'],
                "reference": result['data']['reference']
            })
        return jsonify({"success": False, "message": result.get('message', 'Failed')}), 400
    except Exception as e:
        print(f"Paystack error: {e}")
        return jsonify({"success": False, "message": "Payment error"}), 500


# VERIFY & WEBHOOK (simplified)
@app.route('/verify/paystack', methods=['POST'])
def verify_paystack():
    data = request.json or {}
    reference = data.get('reference')
    if not reference:
        return jsonify({"success": False, "error": "Reference required"}), 400

    try:
        res = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}
        )
        result = res.json()

        if not result.get('status') or result['data']['status'] != 'success':
            return jsonify({"success": False, "error": "Payment failed"})

        email = result['data']['customer']['email'].strip().lower()
        requests.post(
            f"{SUPABASE_URL}/rest/v1/subscriptions",
            headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"email": email, "plan": "pro", "status": "active"}
        )
        print(f"✅ Subscription activated for {email}")
        return jsonify({"success": True, "email": email})
    except Exception as e:
        print(f"Verify error: {e}")
        return jsonify({"success": False, "error": "Verification failed"}), 500


@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    data = request.json or {}
    if data.get('event') == 'charge.success':
        try:
            email = data['data']['customer']['email']
            requests.post(
                f"{SUPABASE_URL}/rest/v1/subscriptions",
                headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
                json={"email": email, "plan": "pro", "status": "active"}
            )
            print(f"Webhook: Pro for {email}")
        except:
            pass
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)