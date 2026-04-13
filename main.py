from flask import Flask, request, jsonify, make_response
import pdfplumber
import docx
import io
import os
import requests
import time
from bs4 import BeautifulSoup

app = Flask(__name__)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.after_request
def after_request(response):
    return add_cors(response)

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

def get_yes24_bestsellers(keyword, genre=""):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = f"https://www.yes24.com/Product/Search?domain=BOOK&query={requests.utils.quote(keyword)}&inQueryId=&sorttype=2&page=1"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "lxml")
        books = []
        items = soup.select(".goods_info")[:10]
        for item in items:
            title_el = item.select_one(".goods_name a")
            author_el = item.select_one(".goods_auth")
            pub_el = item.select_one(".goods_pub")
            price_el = item.select_one(".goods_price strong")
            date_el = item.select_one(".goods_date")
            if title_el:
                books.append({
                    "title": title_el.get_text(strip=True),
                    "author": author_el.get_text(strip=True) if author_el else "",
                    "publisher": pub_el.get_text(strip=True) if pub_el else "",
                    "price": price_el.get_text(strip=True) if price_el else "",
                    "date": date_el.get_text(strip=True) if date_el else ""
                })
        return books
    except Exception as e:
        return []

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    for attempt in range(3):
        try:
            res = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 16000}
            }, timeout=180)
            data = res.json()
            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            if data.get("error", {}).get("code") == 503:
                time.sleep(5)
                continue
            raise Exception(f"API 오류: {data}")
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise Exception("Gemini 응답 시간 초과. 다시 시도해주세요.")
            time.sleep(3)
    raise Exception("Gemini 서버가 불안정합니다. 잠시 후 다시 시도해주세요.")

@app.route("/api/analyze", methods=["GET", "POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return make_response("", 204)
    if request.method == "GET":
        return jsonify({"status": "ok"})
    prompt = request.form.get("prompt", "")
    file = request.files.get("file")
    use_search = request.form.get("use_search", "false") == "true"
    keyword = request.form.get("search_keyword", "")
    file_text = ""
    if file:
        file_bytes = file.read()
        file_text = extract_text(file_bytes, file.filename)
    if file_text:
        prompt = prompt + "\n\n원고 내용:\n" + file_text[:6000]
    if use_search and keyword:
        books = get_yes24_bestsellers(keyword)
        if books:
            book_info = "\n".join([f"- {b['title']} / {b['author']} / {b['publisher']} / {b['date']} / {b['price']}" for b in books])
            prompt = prompt + f"\n\n[yes24 실시간 검색 결과 - '{keyword}' 키워드]\n{book_info}\n\n위 실시간 데이터를 우선 참고하여 분석하세요."
    try:
        result = call_gemini(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
