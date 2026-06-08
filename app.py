from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from pipeline import run_pipeline

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return jsonify({"status": "YT Automation API running"})

@app.route("/api/run", methods=["POST"])
def run():
    try:
        count = request.json.get("count", 3) if request.json else 3
        results = run_pipeline(count=count)
        return jsonify({"success": True, "videos": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/videos", methods=["GET"])
def get_videos():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    sb = create_client(url, key)
    data = sb.table("videos").select("*").order("created_at", desc=True).limit(50).execute()
    return jsonify(data.data)

@app.route("/api/trends", methods=["GET"])
def get_trends():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    sb = create_client(url, key)
    data = sb.table("trends").select("*").order("created_at", desc=True).limit(20).execute()
    return jsonify(data.data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
