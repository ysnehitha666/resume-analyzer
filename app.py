from flask import Flask, request, jsonify, send_from_directory
import os
import fitz
from google import genai
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = "resume_history.db"


# ===== SETUP: Create database table if it doesn't exist =====
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            ats_score TEXT,
            missing_skills TEXT,
            suggestion TEXT,
            strengths TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()  # Run this once when app starts


# ===== ROUTE 1: Serve homepage =====
@app.route("/")
def home():
    return send_from_directory('.', 'index.html')


# ===== ROUTE 2: Serve CSS and JS files =====
@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory('.', filename)


# ===== ROUTE 3: Full AI Analysis + Save to Database =====
@app.route("/analyze", methods=["POST"])
def analyze():

    if 'resume' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['resume']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        doc = fitz.open(filepath)
        resume_text = ""
        for page in doc:
            resume_text += page.get_text()
        doc.close()

        if len(resume_text.strip()) == 0:
            return jsonify({"error": "Could not read PDF text"}), 400

    except Exception as e:
        return jsonify({"error": f"PDF reading failed: {str(e)}"}), 500

    try:
        prompt = f"""
You are an expert resume reviewer and ATS specialist.

Analyze the following resume and reply in EXACTLY this format:

ATS_SCORE: [score out of 100]
MISSING_SKILLS: [top missing skills separated by commas]
SUGGESTION: [one most important suggestion]
STRENGTHS: [2-3 strongest points]

Resume:
{resume_text}

Reply ONLY in the exact format above. Nothing else.
"""

        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        ai_response = response.text

        lines = ai_response.strip().split('\n')
        result = {
            "ats_score": "N/A",
            "missing_skills": "N/A",
            "suggestion": "N/A",
            "strengths": "N/A"
        }

        for line in lines:
            if line.startswith("ATS_SCORE:"):
                result["ats_score"] = line.replace("ATS_SCORE:", "").strip()
            elif line.startswith("MISSING_SKILLS:"):
                result["missing_skills"] = line.replace("MISSING_SKILLS:", "").strip()
            elif line.startswith("SUGGESTION:"):
                result["suggestion"] = line.replace("SUGGESTION:", "").strip()
            elif line.startswith("STRENGTHS:"):
                result["strengths"] = line.replace("STRENGTHS:", "").strip()

        # ===== SAVE TO DATABASE =====
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (filename, ats_score, missing_skills, suggestion, strengths, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            file.filename,
            result["ats_score"],
            result["missing_skills"],
            result["suggestion"],
            result["strengths"],
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()
        conn.close()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"AI failed: {str(e)}"}), 500


# ===== ROUTE 4: Get History =====
@app.route("/history", methods=["GET"])
def get_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()

    history_list = []
    for row in rows:
        history_list.append({
            "id": row[0],
            "filename": row[1],
            "ats_score": row[2],
            "missing_skills": row[3],
            "suggestion": row[4],
            "strengths": row[5],
            "created_at": row[6]
        })

    return jsonify(history_list)


# ===== ROUTE 5: Delete a history item =====
@app.route("/history/<int:item_id>", methods=["DELETE"])
def delete_history(item_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ===== ROUTE 6: Compare Two Resumes =====
@app.route("/compare", methods=["POST"])
def compare():
    data = request.get_json()
    id1 = data.get("id1")
    id2 = data.get("id2")

    if not id1 or not id2:
        return jsonify({"error": "Please select two resumes to compare"}), 400

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM history WHERE id = ?", (id1,))
    resume1 = cursor.fetchone()

    cursor.execute("SELECT * FROM history WHERE id = ?", (id2,))
    resume2 = cursor.fetchone()

    conn.close()

    if not resume1 or not resume2:
        return jsonify({"error": "One or both resumes not found"}), 404

    # Build a prompt using the saved feedback of both resumes
    prompt = f"""
You are an expert resume reviewer. Compare these two resume analyses and tell me which one is stronger overall.

RESUME A: {resume1[1]}
- ATS Score: {resume1[2]}
- Missing Skills: {resume1[3]}
- Strengths: {resume1[5]}

RESUME B: {resume2[1]}
- ATS Score: {resume2[2]}
- Missing Skills: {resume2[3]}
- Strengths: {resume2[5]}

Reply in EXACTLY this format:

WINNER: [Resume A or Resume B]
REASON: [2-3 sentences explaining why]
RECOMMENDATION: [one tip to make the weaker resume better]

Reply ONLY in that format. Nothing else.
"""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        ai_response = response.text

        lines = ai_response.strip().split('\n')
        result = {
            "winner": "N/A",
            "reason": "N/A",
            "recommendation": "N/A",
            "resume_a_name": resume1[1],
            "resume_b_name": resume2[1]
        }

        for line in lines:
            if line.startswith("WINNER:"):
                result["winner"] = line.replace("WINNER:", "").strip()
            elif line.startswith("REASON:"):
                result["reason"] = line.replace("REASON:", "").strip()
            elif line.startswith("RECOMMENDATION:"):
                result["recommendation"] = line.replace("RECOMMENDATION:", "").strip()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)