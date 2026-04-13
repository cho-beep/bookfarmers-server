from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import pdfplumber
import docx
import io
import os
import requests

app = Flask(__name__)
CORS(app, origins="*")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

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

@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return "", 200
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

@app.route("/api/books", methods=["GET", "OPTIONS"])
def search_books():
    if request.method == "OPTIONS":
        return "", 200
    query = request.args.get("query", "")
    display = request.args.get("display", "30")
    sort = request.args.get("sort", "date")
    if not query:
        return jsonify({"error": "query 파라미터가 필요합니다"}), 400
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": display, "sort": sort}
    try:
        res = requests.get("https://openapi.naver.com/v1/search/book.json", headers=headers, params=params)
        return jsonify(res.json())
    except Exception as e:
