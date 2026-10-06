import os
import json
import base64
from flask import Flask, render_template, request, Response, session, stream_with_context, jsonify, redirect, url_for, send_from_directory
from google import genai
from google.genai import types
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "duoverse_secret_key_12345")

# Login Credentials
VALID_USERNAME = "AD patel"
VALID_PASSWORD = "AD patel001"

# Google OAuth Credentials
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "336615336061-k6k42485rgvvtusb9rt0pv17e58ioeat.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# System Prompt
SYSTEM_INSTRUCTION = """
You are Duoverse, an advanced, highly intelligent, helpful, and friendly AI assistant.
Always identify yourself as Duoverse when asked.
If asked who made, created, or developed you, state clearly and explicitly that you were made by AnshPatel.
Provide structured, clear, and comprehensive responses using clean Markdown.
When an image is provided, analyze and describe it accurately based on the user's prompt.
"""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- Main App & Auth Routes ---

@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("index.html", user_name=session.get("user_name", "User"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session["logged_in"] = True
            session["user_name"] = username
            session["history"] = []
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Invalid Username or Password"}), 401

    return render_template("login.html")

@app.route("/login/google")
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        session["logged_in"] = True
        session["user_name"] = user_info.get("name", "Google User")
        session["history"] = []
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})

# --- SEO & Verification Routes ---

@app.route('/google90cbb23eccda2c2f.html')
def google_verify():
    return send_from_directory('static', 'google90cbb23eccda2c2f.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

# --- Chat Stream Endpoint ---

@app.route("/chat_stream", methods=["POST"])
def chat_stream():
    if not session.get("logged_in"):
        return Response("Unauthorized", status=401)

    data = request.json or {}
    user_message = data.get("message", "").strip()
    image_b64 = data.get("image", None)

    if not user_message and not image_b64:
        return Response("Message or image is required.", status=400)

    history = session.get("history", [])
    
    formatted_history = [
        types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["text"])])
        for msg in history
    ]

    current_parts = []
    
    if image_b64:
        if "," in image_b64:
            header, image_b64 = image_b64.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
        else:
            mime_type = "image/jpeg"

        image_bytes = base64.b64decode(image_b64)
        current_parts.append(
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        )

    prompt_text = user_message if user_message else "Please analyze and describe this photo in detail."
    current_parts.append(types.Part.from_text(text=prompt_text))

    formatted_history.append(types.Content(role="user", parts=current_parts))

    def generate():
        full_response = ""
        try:
            if not client:
                yield f"data: {json.dumps({'error': 'GEMINI_API_KEY environment variable missing.'})}\n\n"
                return

            response = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=formatted_history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[{"google_search": {}}]
                )
            )

            for chunk in response:
                if chunk.text:
                    token = chunk.text
                    full_response += token
                    yield f"data: {json.dumps({'token': token})}\n\n"

            history.append({"role": "user", "text": f"[Photo Uploaded] {prompt_text}" if image_b64 else prompt_text})
            history.append({"role": "model", "text": full_response})
            session["history"] = history

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    session["history"] = []
    return jsonify({"status": "success"})

# --- Server Start ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)