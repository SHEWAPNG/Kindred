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

# CORS handling
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    response = jsonify({})
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response, 200

# ── ENV
PAYSTACK_SECRET  = os.getenv("PAYSTACK_SECRET_KEY")
COHERE_API_KEY   = os.getenv("COHERE_API_KEY")
SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_SERVICE_KEY")
GMAIL_USER       = os.getenv("GMAIL_USER")
GMAIL_PASS       = os.getenv("GMAIL_APP_PASSWORD")
ADMIN_SECRET     = os.getenv("ADMIN_SECRET", "kindred-admin-2026")

# ── OWNER EMAILS (always Pro)
OWNER_EMAILS = ["olawumimojisola52@gmail.com"]

print("=== Kindred Backend Starting ===")
print("Paystack key exists: ", bool(PAYSTACK_SECRET))
print("Cohere key exists: ", bool(COHERE_API_KEY))
print("Supabase URL: ", SUPABASE_URL)
print("Supabase key exists: ", bool(SUPABASE_KEY))
print("Gmail user: ", GMAIL_USER)
print("Gmail pass exists: ", bool(GMAIL_PASS))
print("================================")


# ════════════════════════════════
#  HELPERS
# ════════════════════════════════

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_subscription(email):
    if not email:
        return {"has_subscription": False, "plan": "free"}
    
    email = email.strip().lower()
    
    # Force Pro for owner - very strict
    if email in [e.strip().lower() for e in OWNER_EMAILS]:
        print(f"✅ Owner detected as Pro: {email}")
        return {"has_subscription": True, "plan": "pro"}
    
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/subscriptions?email=eq.{email}&status=eq.active&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        if rows and len(rows) > 0:
            return {"has_subscription": True, "plan": rows[0].get("plan", "pro")}
        return {"has_subscription": False, "plan": "free"}
    except Exception as e:
        print("Subscription check error:", e)
        return {"has_subscription": False, "plan": "free"}
    
def get_usage(email):
    month = datetime.datetime.now().strftime("%Y-%m")
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/usage?email=eq.{email}&month=eq.{month}&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        if rows and len(rows) > 0:
            return rows[0].get("count", 0)
        return 0
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
        if rows and len(rows) > 0:
            count = rows[0].get("count", 0)
            record_id = rows[0].get("id")
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/usage?id=eq.{record_id}",
                headers=supabase_headers(),
                json={"count": count + 1}, timeout=10
            )
        else:
            requests.post(
                f"{SUPABASE_URL}/rest/v1/usage",
                headers=supabase_headers(),
                json={"email": email, "month": month, "count": 1}, timeout=10
            )
    except Exception as e:
        print("Usage increment error:", e)

def get_all_auth_users():
    users = []
    page = 1
    per_page = 100
    while True:
        res = requests.get(
            f"{SUPABASE_URL}/auth/v1/admin/users?page={page}&per_page={per_page}",
            headers=supabase_headers(), timeout=20
        )
        if res.status_code != 200:
            raise Exception(f"Supabase fetch failed: {res.status_code} - {res.text}")
        data = res.json()
        page_users = data.get("users", [])
        for u in page_users:
            if u.get("email"):
                users.append({
                    "email": u["email"],
                    "name": u.get("user_metadata", {}).get("first_name", ""),
                    "created_at": u.get("created_at")
                })
        if len(page_users) < per_page:
            break
        page += 1
    return users

# ====================== EMAIL SENDING ======================
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
        print(f"✅ Email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")

def build_email_html(headline, body_html, cta_text="", cta_link="", name=""):
    bg_color = "#FFF5F5"
    accent_color = "#FF8A8A"
    text_dark = "#3D2B2B"
    greeting = f"Hi {name}," if name else "Hi there,"
    cta_button = ""
    if cta_text and cta_link:
        cta_button = f'''
        <div style="text-align:center;margin-top:32px;">
            <a href="{cta_link}"
               style="background:{accent_color}; color:#FFF5F5; padding:14px 36px;
                      border-radius:50px; font-weight:700; text-decoration:none;
                      font-size:0.95rem; display:inline-block;">
                {cta_text}
            </a>
        </div>'''
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700&family=Inter:wght@400;500;600&display=swap');
    </style>
</head>
<body style="margin:0;padding:0;background:{bg_color};font-family:'Inter',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{bg_color};padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="text-align:center;padding-bottom:32px;">
  <h1 style="font-family:'Fraunces',Georgia,serif;color:{accent_color};font-size:2.4rem;margin:0 0 6px 0;">
    Kindred
  </h1>
  <p style="color:{text_dark};font-size:0.9rem;margin:0;opacity:0.85;">Say exactly what you mean.</p>
</td></tr>
<tr><td style="background:#ffffff;border-radius:20px;border:2px solid {accent_color};padding:45px 40px;box-shadow:0 10px 30px rgba(255,138,138,0.08);">
  <p style="color:{text_dark};font-size:1.05rem;margin:0 0 24px 0;line-height:1.6;">{greeting}</p>
 
  <h2 style="font-family:'Fraunces',Georgia,serif;color:{accent_color};font-size:1.75rem;margin:0 0 24px 0;line-height:1.3;">
    {headline}
  </h2>
 
  <div style="color:{text_dark};font-size:0.98rem;line-height:1.75;">{body_html}</div>
  {cta_button}
</td></tr>
<tr><td style="text-align:center;padding-top:32px;">
  <p style="color:{text_dark};font-size:0.78rem;margin:0;opacity:0.7;">
    You received this because you signed up for Kindred.<br>
    © 2026 Kindred. All rights reserved.
  </p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# ════════════════════════════════
# MULTILINGUAL DETECTION
# ════════════════════════════════
# ════════════════════════════════
# MULTILINGUAL DETECTION (Yoruba, Pidgin, Hausa, French + more)
# ════════════════════════════════
MULTILINGUAL_PATTERNS = [
    # Yoruba
    _re.compile(r'\b(mo fe|e joo|e jo|jowo|bawo ni|ese|eku aro|eku ile|eku ise|nibo|kilode|eyin|emi ni|se o|jẹ|pẹlu|lati|naa|àwa|ẹ jọwọ|ọmọ|ọdun|ile|owo|kilode|bawo|se|o|ni)\b', _re.IGNORECASE),
    
    # Nigerian Pidgin
    _re.compile(r'\b(dey|nau|abi|wetin|wahala|abeg|oga|sabi|wey|no be|e be like|chop|pikin|bros|ehen|sha|sef|walahi|jare|na im|dem say|how far|i wan|make i|no dey|you sabi|commot|wetin dey|how you dey)\b', _re.IGNORECASE),
    
    # Hausa
    _re.compile(r'\b(yauwa|sannu|nagode|don allah|tare da|ina kwana|lafiya|malam|alhaji|wallahi|insha allah|kai|kin|kun|suna|ban|ka|ki|mu|su|da|ina|za|ka|ki)\b', _re.IGNORECASE),
    
    # French
    _re.compile(r'\b(bonjour|bonsoir|merci|s\'il vous plaît|je suis|je veux|comment|pourquoi|nous sommes|c\'est|qu\'est|je ne|il faut|voici|voilà|monsieur|madame|au revoir|enchanté)\b', _re.IGNORECASE),
    
    # General multilingual fallback (common words in many African/French contexts)
    _re.compile(r'\b(merci|bon|oui|non|je|tu|il|elle|nous|vous|ils|aller|faire|dire|savoir|voir|venir|aller)\b', _re.IGNORECASE),
]

def is_multilingual(text):
    return any(p.search(text) for p in MULTILINGUAL_PATTERNS)

def detect_language(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ['mo fe', 'jowo', 'bawo', 'kilode', 'ese', 'emi ni']):
        return "yoruba"
    if any(word in text_lower for word in ['yauwa', 'sannu', 'nagode', 'wallahi', 'insha allah']):
        return "hausa"
    if any(word in text_lower for word in ['bonjour', 'merci', 'je suis', 'comment', 'pourquoi']):
        return "french"
    if any(word in text_lower for word in ['wetin', 'abeg', 'oga', 'sha', 'walahi']):
        return "pidgin"
    return "english"


# ════════════════════════════════
# ROUTES
# ════════════════════════════════

@app.route('/', methods=['GET'])
# ====================== SERVE HTML FILES ======================
@app.route('/')
def homepage():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_html(filename):
    """Serve all .html files directly"""
    if filename.endswith(('.html', '.css', '.js')) or '.' not in filename:
        try:
            return send_from_directory('.', filename)
        except:
            return jsonify({"error": "File not found"}), 404
    return jsonify({"error": "File not found"}), 404

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


# ── AI TRANSFORM
@app.route('/transform', methods=['POST'])
def transform():
    data = request.json or {}
    raw_text = data.get('text', '').strip()
    format_type = data.get('format', 'email').lower()
    tone = data.get('tone', 'professional')
    instruction = data.get('instruction', '').strip()
    email = data.get('email', '').strip().lower()
    output_language = data.get('output_language', 'auto').lower()

    if not raw_text or not email:
        return jsonify({"success": False, "error": "Text and email are required"})

    sub = get_subscription(email)
    is_pro = sub["has_subscription"]

    print(f"Transform → Email: {email} | Pro: {is_pro} | Format: {format_type} | Output Lang: {output_language}")

    # ====================== ACCESS CONTROL ======================
    if not is_pro:
        FREE_FORMATS = ['email', 'conversation']
        if format_type not in FREE_FORMATS:
            return jsonify({"success": False, "upgrade_required": True,
                            "error": f"{format_type.replace('_', ' ').title()} is a Pro feature."})

        if is_multilingual(raw_text):
            return jsonify({"success": False, "upgrade_required": True,
                            "error": "Multilingual input is a Pro feature."})

        usage = get_usage(email)
        if usage >= 5:
            return jsonify({"success": False, "upgrade_required": True,
                            "error": "Free limit reached. Upgrade to Pro."})

    # ====================== LANGUAGE LOGIC ======================
    detected_lang = detect_language(raw_text)
    
    # Use user selection if provided, otherwise auto-detect
    if output_language == 'auto':
        final_lang = detected_lang
    else:
        final_lang = output_language

    # ====================== FORMAT GUIDES ======================
    format_guides = {
        "email": "Write a clear, professional email with subject, greeting, body and sign-off.",
        "conversation": "Write a natural, warm WhatsApp-style conversation.",
        "proposal": "Write a professional business proposal with clear sections.",
        "social_media_post": "Write an engaging social media post with strong hook and call-to-action.",
        "content_strategy": "Create a content strategy including goals, audience, topics and schedule.",
        "essay": "Write a well-structured essay with introduction, body and conclusion.",
        "speech": "Write a powerful speech (wedding, motivational, or presentation).",
        "teaching_explanation": "Explain the topic clearly like teaching a beginner. Use simple language and examples.",
        "product_description": "Write persuasive product description highlighting benefits.",
        "cover_letter": "Write a compelling job application cover letter."
    }

    guide = format_guides.get(format_type, "Write clearly and naturally.")

    # Language instruction
    lang_instruction = f"Respond entirely in {final_lang.capitalize()}." if final_lang != "english" else "Respond in natural, polished English."

    # Final Prompt
    prompt = f"""You are Kindred — a warm, culturally intelligent writing assistant.
You perfectly understand Yoruba, Hausa, Pidgin, French, and English.

{lang_instruction}

FORMAT: {format_type.replace('_', ' ').upper()}
TONE: {tone}

Guidelines:
{guide}

User wrote:
{raw_text}

Output ONLY the final transformed text. No explanations, no labels."""

    try:
        res = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
            json={"model": "command-a-03-2025", "messages": [{"role": "user", "content": prompt}]},
            timeout=35
        )
        result = res.json()

        if 'message' in result and result['message'].get('content'):
            output = result['message']['content'][0]['text'].strip()

            if not is_pro and email:
                increment_usage(email)

            return jsonify({
                "success": True,
                "output": output,
                "plan": sub["plan"],
                "detected_lang": detected_lang,
                "output_lang": final_lang
            })
        else:
            return jsonify({"success": False, "error": "AI failed to generate response"})

    except Exception as e:
        print(f"Transform error: {e}")
        return jsonify({"success": False, "error": "AI service error. Please try again."})
   
# ── ENSURE NEW USER IS FREE
@app.route('/ensure-free-user', methods=['POST'])
def ensure_free_user():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400
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
            print(f"✅ New user set as FREE: {email}")
        return jsonify({"success": True, "plan": "free"})
    except Exception as e:
        print(f"Error ensuring free user: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ── SEND WELCOME EMAIL AFTER FIRST SIGN-IN
@app.route('/send-welcome', methods=['POST'])
def send_welcome():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()

    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    try:
        first = name.split()[0].capitalize() if name else "there"

        body_html = f"""
<p>Hi {first},</p>
<p>Imagine this: You have something important to say — a message to a client, a difficult conversation with your boss, or even a heartfelt note to someone you care about — but the words just won't come out right.</p>
<p>You rewrite it five times. It still feels off. Too harsh. Too weak. Too desperate. Too cold.</p>
<p>That frustration ends today.</p>
<p><strong>Welcome to Kindred.</strong></p>
<p>Kindred is your personal writing partner. You type whatever is in your heart — messy, emotional, in Yoruba, Pidgin, or broken English — and we turn it into words that feel clear, confident, and truly you.</p>
<p>Freelancers in Lagos have used it to finally get paid. Students have used it to write essays their lecturers praised. People with anxiety have used it to say "no" with warmth and honesty.</p>
<p>Now it's your turn.</p>
<p>Go ahead — open the app and try your first transformation. You'll be amazed at how good it feels to finally say exactly what you mean.</p>
<p style="color:#FF8A8A;"><strong>This is just the beginning of your better communication journey.</strong></p>
<p style="color:#3D2B2B;font-size:0.9rem;margin-top:28px;">With love and excitement for your words,<br><strong>Adesewa and the Kindred team</strong></p>
"""

        html = build_email_html(
            headline="Welcome to Kindred. You found your words. ✦",
            body_html=body_html,
            cta_text="Open Kindred Now →",
            cta_link="https://kindred-evk6.onrender.com/kindred-app.html",
            name=name
        )

        send_email(email, f"Welcome to Kindred, {first} ✦", html, name)
        print(f"✅ Welcome email sent to: {email}")
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Welcome email failed for {email}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ── CHECK SUBSCRIPTION
@app.route('/check-subscription', methods=['POST'])
def check_subscription():
    data = request.json or {}
    email = data.get('email', '')
    sub = get_subscription(email)
    return jsonify({"success": True, "has_subscription": sub["has_subscription"], "plan": sub["plan"]})


# ── WAITLIST
@app.route('/waitlist', methods=['POST'])
def waitlist():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "Please enter a valid email."}), 400

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/waitlist",
            headers={**supabase_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={"email": email, "name": name, "source": "landing"}
        )
    except Exception as e:
        print("Waitlist DB error:", e)

    try:
        first = name.split()[0].capitalize() if name else "there"
        body_html = f"""
<p>You know that feeling when you have something important to say — an email to send, a message to write, a proposal to pitch — and the words just won't come out right?</p>
<p>You rewrite it five times. It still sounds off. Too harsh. Too casual. Too desperate. Too stiff. So you either send something bad, or you send nothing at all.</p>
<p>That is exactly why Kindred exists.</p>
<p><strong style="color:#FF8A8A;">Kindred is your personal writing partner.</strong><br>
You type whatever is on your mind — messy, unfiltered, even in Yoruba or Pidgin — and Kindred transforms it into something clear, confident and perfectly worded. In seconds.</p>
<p>Start free right now — no credit card, no catch.</p>
<p style="color:#3D2B2B;font-size:0.9rem;margin-top:24px;">With love,<br><strong>Adesewa and the Kindred team</strong></p>
"""
        html = build_email_html(
            headline="Welcome to Kindred. You found us. ✦",
            body_html=body_html,
            cta_text="Start Using Kindred Free →",
            cta_link="https://kindred-evk6.onrender.com/kindred-auth.html",
            name=name
        )
        send_email(email, f"Welcome to Kindred, {first} ✦", html, name)
        print(f"✅  welcome email sent to {email}")
    except Exception as e:
        print(f" email failed for {email}: {e}")

    return jsonify({"success": True, "message": "Welcome to Kindred! Welcome email sent."})


# ── ADMIN ROUTES
@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    data = request.json or {}
    secret = data.get('secret', '')
    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "message": "Wrong password"}), 401
    return jsonify({"success": True})

@app.route('/waitlist/list', methods=['POST'])
def waitlist_list():
    data = request.json or {}
    secret = data.get('secret', '')
    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "message": "Wrong password"}), 401
    try:
        users = get_all_auth_users()
        return jsonify({"success": True, "subscribers": users, "count": len(users)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── PAYMENT ROUTES (STRICT & UPDATED)

@app.route('/pay/naira', methods=['POST'])
def pay_naira():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    plan_name = data.get('plan', 'pro')
    currency = data.get('currency', 'NGN').upper()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "Valid email is required"}), 400

    # Use your actual Paystack Plan Code for recurring billing
    PAYSTACK_PLAN_CODE = "PLN_m8wf2yudi3jflnx"

    try:
        res = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET}",
                "Content-Type": "application/json"
            },
            json={
                "email": email,
                "amount": 500000,                    # First payment = ₦5,000
                "currency": currency,
                "plan": PAYSTACK_PLAN_CODE,           # This enables recurring
                "callback_url": "https://kindred-evk6.onrender.com/kindred-callback.html",
                "metadata": {
                    "plan": plan_name,
                    "currency": currency,
                    "source": "pricing_page",
                    "is_recurring": True
                },
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

        return jsonify({"success": False, "message": result.get('message', 'Failed to initialize subscription')}), 400

    except Exception as e:
        print(f"Paystack subscription init error: {e}")
        return jsonify({"success": False, "message": "Payment service error. Try again later."}), 500


@app.route('/verify/paystack', methods=['POST'])
def verify_paystack():
    data = request.json or {}
    reference = data.get('reference')

    if not reference:
        return jsonify({"success": False, "error": "Reference is required"}), 400

    try:
        res = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
            timeout=15
        )
        result = res.json()

        if not result.get('status') or result['data']['status'] != 'success':
            return jsonify({"success": False, "error": "Payment not successful on Paystack"})

        email = result['data']['customer']['email'].strip().lower()
        plan = result['data']['metadata'].get('plan', 'pro')
        amount = result['data']['amount']
        currency = result['data']['metadata'].get('currency', 'NGN')

        # Save subscription in Supabase
        requests.post(
            f"{SUPABASE_URL}/rest/v1/subscriptions",
            headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={
                "email": email,
                "plan": plan,
                "status": "active",
                "amount": amount,
                "reference": reference,
                "currency": currency,
                "updated_at": datetime.datetime.utcnow().isoformat()
            }
        )

        print(f"✅ Recurring Pro subscription activated for {email} | Ref: {reference}")

        # Send welcome email
        try:
            first = email.split('@')[0].capitalize()
            body_html = f"""
            <p>Your subscription to Kindred Pro is now active!</p>
            <p>You will be charged ₦5,000 monthly. You can cancel anytime from your Paystack dashboard.</p>
            <p>Enjoy unlimited transforms and all Pro features.</p>
            """
            html = build_email_html(
                headline="Welcome to Kindred Pro! 🎉",
                body_html=body_html,
                cta_text="Open Kindred App →",
                cta_link="https://kindred-evk6.onrender.com/kindred-app.html",
                name=first
            )
            send_email(email, "Welcome to Kindred Pro!", html, first)
        except:
            pass

        return jsonify({"success": True, "plan": plan, "email": email, "message": "Recurring subscription activated"})

    except Exception as e:
        print(f"Verify error: {e}")
        return jsonify({"success": False, "error": "Internal verification error"}), 500


@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    data = request.json or {}
    event = data.get('event')
    if event == 'charge.success':
        try:
            email = data['data']['customer']['email']
            plan = data['data']['metadata'].get('plan', 'pro')
            reference = data['data']['reference']
            amount = data['data']['amount']
            currency = data['data']['metadata'].get('currency', 'NGN')

            requests.post(
                f"{SUPABASE_URL}/rest/v1/subscriptions",
                headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
                json={"email": email, "plan": plan, "status": "active",
                      "amount": amount, "reference": reference, "currency": currency}
            )
            print(f"Webhook: saved {email} - {plan}")
        except Exception as e:
            print(f"Webhook error: {e}")
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)