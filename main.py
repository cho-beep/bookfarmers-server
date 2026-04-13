from flask import Flask, request, jsonify, make_response
import pdfplumber
import docx
import io
import os
import requests
import time
from bs4 import BeautifulSoup

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

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

def get_yes24_bestsellers(keyword):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = f"https://www.yes24.com/Product/Search?domain=BOOK&query={requests.utils.quote(keyword)}&sorttype=2&page=1"
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
            }, timeou
