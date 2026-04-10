from flask import Flask, request, jsonify, make_response
import google.generativeai as genai
import pdfplumber
import docx
import io
import os

app = Flask(__name__)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization"
    return response

@app.after_request
def after_request(response):
    return add_cors_headers(response)

def extract_text(file_bytes, filename):
    name = filename.lower()
    if name.endswith(".pdf"):
        text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text
    elif name.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    elif name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    return ""

@app.route("/api/analyze", methods=["GET", "POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        response = make_response("", 204)
        return add_cors_headers(response)
    if request.method == "GET":
        return jsonify({"status": "ok"})
    prompt = request.form.get("prompt", "")
    file = request.files.get("file")
    file_text = ""
    if file:
        file_bytes = file.read()
        file_text = extract_text(file_bytes, file.filename)
    if file_text:
        prompt = prompt + "\n\n원고 내용:\n" + file_text[:6000]
    try:
        response = model.generate_content(prompt)
        return jsonify({"result": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
