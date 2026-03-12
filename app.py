from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import datetime
from flask import Flask, send_from_directory

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

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

# ── YOUR EMAIL — always Pro, no payment needed
OWNER_EMAILS = [
    "olawumimojisola52@gmail.com",
]

print("=== Kindred Backend Starting ===")
print("Paystack key exists:    ", bool(PAYSTACK_SECRET))
print("Cohere key exists:      ", bool(COHERE_API_KEY))
print("Supabase URL:           ", SUPABASE_URL)
print("Supabase key exists:    ", bool(SUPABASE_KEY))
print("Gmail user:             ", GMAIL_USER)
print("Gmail pass exists:      ", bool(GMAIL_PASS))
print("================================")


# ════════════════════════════════
#  HELPERS
# ════════════════════════════════

def supabase_headers():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json"
    }

def get_subscription(email):
    if email in OWNER_EMAILS:
        return {"has_subscription": True, "plan": "pro"}
    try:
        res  = requests.get(
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
        res  = requests.get(
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
        res  = requests.get(
            f"{SUPABASE_URL}/rest/v1/usage?email=eq.{email}&month=eq.{month}&select=*",
            headers=supabase_headers(), timeout=10
        )
        rows = res.json()
        if rows and len(rows) > 0:
            count     = rows[0].get("count", 0)
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
    users    = []
    page     = 1
    per_page = 100
    while True:
        res = requests.get(
            f"{SUPABASE_URL}/auth/v1/admin/users?page={page}&per_page={per_page}",
            headers=supabase_headers(), timeout=20
        )
        if res.status_code != 200:
            raise Exception(f"Supabase fetch failed: {res.status_code} - {res.text}")
        data       = res.json()
        page_users = data.get("users", [])
        for u in page_users:
            if u.get("email"):
                users.append({
                    "email":      u["email"],
                    "name":       u.get("user_metadata", {}).get("first_name", ""),
                    "created_at": u.get("created_at")
                })
        if len(page_users) < per_page:
            break
        page += 1
    return users

def send_email(to_email, subject, html, name=""):
    if not GMAIL_USER or not GMAIL_PASS:
        raise Exception("Gmail not configured in .env — add GMAIL_USER and GMAIL_APP_PASSWORD")
    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Kindred <{GMAIL_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

def build_email_html(headline, body_html, cta_text="", cta_link="", name=""):
    greeting   = f"Hi {name}," if name else "Hi there,"
    cta_button = ""
    if cta_text and cta_link:
        cta_button = f'<div style="text-align:center;margin-top:32px;"><a href="{cta_link}" style="background:#e8a838;color:#0f1623;padding:14px 36px;border-radius:50px;font-weight:700;text-decoration:none;font-size:0.95rem;display:inline-block;">{cta_text}</a></div>'
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f1623;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1623;padding:40px 20px;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="text-align:center;padding-bottom:32px;">
  <h1 style="font-family:Georgia,serif;color:#e8a838;font-size:2.2rem;margin:0 0 4px;">Kindred</h1>
  <p style="color:#c8bfad;font-size:0.85rem;margin:0;">Say exactly what you mean.</p>
</td></tr>
<tr><td style="background:#1a2438;border-radius:16px;border:1px solid rgba(232,168,56,0.15);padding:40px;">
  <p style="color:#f7f2e8;font-size:1rem;margin:0 0 20px 0;">{greeting}</p>
  <h2 style="font-family:Georgia,serif;color:#e8a838;font-size:1.6rem;margin:0 0 20px;line-height:1.3;">{headline}</h2>
  <div style="color:#c8bfad;font-size:0.95rem;line-height:1.8;">{body_html}</div>
  {cta_button}
</td></tr>
<tr><td style="text-align:center;padding-top:28px;">
  <p style="color:#c8bfad;font-size:0.75rem;margin:0;">You received this because you signed up for Kindred.<br>© 2026 Kindred. All rights reserved.</p>
</td></tr>
</table></td></tr></table></body></html>"""


# ════════════════════════════════
#  ROUTES
# ════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Kindred backend is live ✦", "status": "running"})


# ── HEALTH CHECK (lets frontend test connection)
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


# ── AI TRANSFORM
import re as _re

MULTILINGUAL_PATTERNS = [
    # Yoruba
    _re.compile(r'\b(mo fe|e joo|e jo|jowo|bawo ni|ese|eku aro|eku ile|eku ise|nibo|kilode|eyin|emi ni|se o|jẹ|pẹlu|lati|naa|àwa|ẹ jọwọ|ọmọ|ọdun|ile|owo)\b', _re.IGNORECASE),
    # Nigerian Pidgin
    _re.compile(r'\b(dey|nau|abi|wetin|wahala|abeg|oga|sabi|wey|no be|e be like|chop|pikin|bros|ehen|sha|sef|walahi|jare|na im|dem say|how far|i wan|make i|no dey|you sabi)\b', _re.IGNORECASE),
    # Igbo
    _re.compile(r'\b(biko|daalu|kedu|nna m|nne m|ginị|anyi|ulo|oge|o di mma|ihe|ndi|ha|ya|obodo|ọ bụ)\b', _re.IGNORECASE),
    # Hausa
    _re.compile(r'\b(yauwa|sannu|nagode|don allah|tare da|ina kwana|lafiya|malam|alhaji|wallahi|insha allah|kai|kin|kun|suna)\b', _re.IGNORECASE),
    # French
    _re.compile(r'\b(bonjour|bonsoir|merci|s\'il vous|je suis|je veux|comment|pourquoi|nous sommes|c\'est|qu\'est|je ne|il faut|voici|voilà)\b', _re.IGNORECASE),
]

def is_multilingual(text):
    return any(p.search(text) for p in MULTILINGUAL_PATTERNS)


@app.route('/transform', methods=['POST'])
def transform():
    data        = request.json or {}
    raw_text    = data.get('text', '')
    format_type = data.get('format', 'email').lower()
    tone        = data.get('tone', 'professional')
    instruction = data.get('instruction', '')
    email       = data.get('email', '')

    FREE_FORMATS = ['email', 'conversation']

    sub    = get_subscription(email)
    is_pro = sub["has_subscription"]

    # Block Pro-only formats for free users
    if not is_pro and format_type not in FREE_FORMATS:
        return jsonify({"success": False, "upgrade_required": True,
                        "error": f"{format_type.title()} is a Pro feature. Upgrade to unlock all formats."})

    # Block multilingual input for free users (enforced server-side)
    if not is_pro and not instruction and is_multilingual(raw_text):
        return jsonify({"success": False, "upgrade_required": True,
                        "error": "🌍 Multilingual input (Yoruba, Pidgin, Igbo & more) is a Pro feature. Upgrade to write in any language!"})

    if not is_pro:
        usage = get_usage(email)
        if usage >= 5:
            return jsonify({"success": False, "upgrade_required": True,
                            "error": "You have used all 5 free transforms this month. Upgrade to Pro for unlimited."})

    format_guides = {
        "email": "Write a professional email. Include: Subject line, greeting, body paragraphs, sign-off.",
        "essay": "Write an essay. NO greeting. Start with intro paragraph. Academic prose. No bullet points.",
        "caption": "Write a social media caption. Hook first. Then story. Then CTA. End with 3-5 hashtags.",
        "proposal": "Write a business proposal. Sections: Problem, Solution, Value, Next Steps. No greetings.",
        "conversation": "Write a conversational WhatsApp-style message. Short, warm, human. No formal greetings."
    }

    guide = format_guides.get(format_type, "Write clearly and appropriately.")

    if instruction:
        prompt = f"{instruction}:\n\n{raw_text}\n\nOutput ONLY the adjusted message. No labels or preamble."
    else:
        prompt = f"""You are Kindred, an expert multilingual AI writing assistant.

The user may write in ANY language — Yoruba, Pidgin, Igbo, Hausa, French, or broken English. Understand their intent fully and transform it into polished English.

FORMAT: {format_type.upper()}
TONE: {tone}

Format instructions:
{guide}

Tone guide:
- professional: clear, respectful, confident
- casual: friendly, relaxed, warm
- formal: very official, structured
- empathetic: warm, acknowledges feelings first
- anxiety mode: calm, reassuring, gentle but clear

The user wrote:
{raw_text}

Output ONLY the final {format_type}. No labels, no explanation, no preamble."""

    try:
        res    = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
            json={"model": "command-a-03-2025", "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        result = res.json()
        if 'message' in result:
            output = result['message']['content'][0]['text']
            if not is_pro and email:
                increment_usage(email)
            return jsonify({"success": True, "output": output, "plan": sub["plan"]})
        else:
            return jsonify({"success": False, "error": "AI error: " + str(result)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── CHECK SUBSCRIPTION
@app.route('/check-subscription', methods=['POST'])
def check_subscription():
    data  = request.json or {}
    email = data.get('email', '')
    sub   = get_subscription(email)
    return jsonify({"success": True, "has_subscription": sub["has_subscription"], "plan": sub["plan"]})


# ── PAYMENT — Paystack NGN and USD
@app.route('/pay/naira', methods=['POST'])
def pay_naira():
    data     = request.json or {}
    email    = data.get('email')
    plan     = data.get('plan', 'pro')
    currency = data.get('currency', 'NGN')

    amount = 50000 if currency == 'USD' else 700000

    res    = requests.post(
        "https://api.paystack.co/transaction/initialize",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}", "Content-Type": "application/json"},
        json={
            "email":        email,
            "amount":       amount,
            "currency":     currency,
            "callback_url": "http://localhost:8080/kindred-callback.html",
            "metadata":     {"plan": plan, "currency": currency}
        }
    )
    result = res.json()
    print("Paystack init:", result)

    if result.get('status'):
        return jsonify({"success": True, "payment_url": result['data']['authorization_url'],
                        "reference": result['data']['reference']})
    return jsonify({"success": False, "message": result.get('message', 'Payment init failed')}), 400


# ── VERIFY PAYMENT
@app.route('/verify/paystack', methods=['POST'])
def verify_paystack():
    data      = request.json or {}
    reference = data.get('reference')
    try:
        res    = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}
        )
        result = res.json()
        print("Paystack verify:", result)

        if result.get('status') and result['data']['status'] == 'success':
            email    = result['data']['customer']['email']
            plan     = result['data']['metadata'].get('plan', 'pro')
            amount   = result['data']['amount']
            currency = result['data']['metadata'].get('currency', 'NGN')

            save = requests.post(
                f"{SUPABASE_URL}/rest/v1/subscriptions",
                headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
                json={"email": email, "plan": plan, "status": "active",
                      "amount": amount, "reference": reference, "currency": currency}
            )
            print(f"Subscription saved: {email} - {plan} | Supabase status: {save.status_code}")
            return jsonify({"success": True, "plan": plan, "email": email})
        else:
            return jsonify({"success": False, "error": "Payment not confirmed by Paystack"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── PAYSTACK WEBHOOK (production only)
@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    data  = request.json or {}
    event = data.get('event')
    if event == 'charge.success':
        email     = data['data']['customer']['email']
        plan      = data['data']['metadata'].get('plan', 'pro')
        reference = data['data']['reference']
        amount    = data['data']['amount']
        currency  = data['data']['metadata'].get('currency', 'NGN')
        requests.post(
            f"{SUPABASE_URL}/rest/v1/subscriptions",
            headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"email": email, "plan": plan, "status": "active",
                  "amount": amount, "reference": reference, "currency": currency}
        )
        print(f"Webhook: saved {email} - {plan}")
    return jsonify({"status": "ok"}), 200


# ── WAITLIST SIGNUP
@app.route('/waitlist', methods=['POST'])
def waitlist():
    data  = request.json or {}
    email = data.get('email', '').strip().lower()
    name  = data.get('name', '').strip()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "Please enter a valid email."}), 400

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/waitlist",
            headers={**supabase_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={"email": email, "name": name, "source": "landing"}, timeout=10
        )
    except Exception as e:
        print("Waitlist DB error:", e)

    try:
        first = name.split()[0].capitalize() if name else "there"
        body_html = f"""
<p>You know that feeling when you have something important to say  an email to send, a message to write, a proposal to pitch  and the words just won't come out right?</p>
<p>You rewrite it five times. It still sounds off. Too harsh. Too casual. Too desperate. Too stiff. So you either send something bad, or you send nothing at all.</p>
<p>That is exactly why Kindred exists.</p>
<p><strong style="color:#e8a838;">Kindred is your personal writing partner.</strong><br>
You type whatever is on your mind 
messy, unfiltered, even in Yoruba or Pidgin and Kindred transforms it into something clear, confident and perfectly worded. In seconds.</p>




<p>Someone wanted to ask their boss for a salary raise but did not know how to start. They typed <em>"i want to ask for a raise but i don't want to sound greedy"</em>  Kindred gave them a confident, respectful message that got the conversation started.</p>

<p>Someone with anxiety wanted to send a condolence message and did not know how to express it. They typed <em>"I want to send condolence message to my friend"</em> — Kindred gave them exactly the right words. Warm, honest, human.</p>

<p><strong style="color:#e8a838;">That is what we built for you.</strong><br>
5 formats. Any tone. Any language. Unlimited expression.</p>
<p>Start free right now — no credit card, no catch.</p>
<p style="color:#c8bfad;font-size:0.9rem;margin-top:24px;">With love,<br><strong style="color:#e8a838;"> Kindred</strong></p>
"""
        html = build_email_html(
            headline="Welcome to Kindred. ",
            body_html=body_html,
            cta_text="Start Using Kindred ",
            cta_link="http://localhost:8080/kindred-auth.html?plan=free&mode=signup",
            name=name
        )
        send_email(email, f"Welcome to Kindred, {first} ", html, name)
        print(f"Welcome email sent to {email}")
    except Exception as e:
        print(f"Welcome email failed: {e}")

    return jsonify({"success": True, "message": "Check your email."})


# ── ADMIN VERIFY
@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    data   = request.json or {}
    secret = data.get('secret', '')
    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "message": "Wrong password"}), 401
    return jsonify({"success": True})


# ── GET SUBSCRIBERS (used by newsletter dashboard)
@app.route('/waitlist/list', methods=['POST'])
def waitlist_list():
    data   = request.json or {}
    secret = data.get('secret', '')
    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "message": "Wrong password"}), 401
    try:
        users = get_all_auth_users()
        return jsonify({"success": True, "subscribers": users, "count": len(users)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── SEND NEWSLETTER
@app.route('/newsletter/send', methods=['POST'])
def newsletter_send():
    data      = request.json or {}
    secret    = data.get('secret', '')
    subject   = data.get('subject', '').strip()
    headline  = data.get('headline', '').strip()
    body_html = data.get('body_html', '').strip()
    cta_text  = data.get('cta_text', '').strip()
    cta_link  = data.get('cta_link', '').strip()

    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "message": "Wrong password"}), 401
    if not subject or not headline or not body_html:
        return jsonify({"success": False, "message": "Subject, headline and body are required"}), 400

    try:
        users = get_all_auth_users()
    except Exception as e:
        return jsonify({"success": False, "message": f"Could not fetch users: {e}"}), 500

    if not users:
        return jsonify({"success": False, "message": "No users found"}), 400

    sent   = 0
    failed = 0
    errors = []

    for user in users:
        email = user.get('email')
        name  = user.get('name', '')
        if not email:
            continue
        try:
            html = build_email_html(headline, body_html, cta_text, cta_link, name)
            send_email(email, subject, html, name)
            sent += 1
            print(f"✅ Sent to {email}")
        except Exception as e:
            failed += 1
            errors.append({"email": email, "error": str(e)})
            print(f"❌ Failed {email}: {e}")

    return jsonify({
        "success": sent > 0,
        "message": f"Sent to {sent} of {len(users)} users.",
        "sent": sent, "failed": failed,
        "total": len(users),
        "failed_emails": errors[:10]
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
