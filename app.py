from flask import Flask, jsonify, request
from flask_cors import CORS
import os, re, json, asyncio, requests as http

app = Flask(__name__)
CORS(app)

def get_sb():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_trends(count=9):
    trends = []
    headers = {"User-Agent": "YTAutomation/1.0"}
    for sub in ["todayilearned", "interestingasfuck", "Damnthatsinteresting"]:
        try:
            r = http.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=5", headers=headers, timeout=10)
            if r.status_code == 200:
                for p in r.json()["data"]["children"]:
                    d = p["data"]
                    if not d.get("stickied"):
                        trends.append({"topic": d["title"], "source": f"reddit/{sub}", "score": min(int(d.get("score",0)/100),100)})
        except: pass
    if len(trends) < 3:
        trends = [
            {"topic": "Scientists discovered octopuses dream and change colors in sleep", "source": "fallback", "score": 95},
            {"topic": "The human brain generates enough electricity to power a light bulb", "source": "fallback", "score": 93},
            {"topic": "Sharks are older than trees by 50 million years", "source": "fallback", "score": 91},
            {"topic": "A day on Venus is longer than a year on Venus", "source": "fallback", "score": 89},
            {"topic": "Cleopatra lived closer to the Moon landing than to the pyramids", "source": "fallback", "score": 87},
            {"topic": "Honey never expires — 3000 year old honey found in Egyptian tombs", "source": "fallback", "score": 85},
            {"topic": "There are more trees on Earth than stars in the Milky Way", "source": "fallback", "score": 83},
            {"topic": "The inventor of the Pringles can is buried in one", "source": "fallback", "score": 79},
        ]
    sb = get_sb()
    for t in trends[:count]:
        try: sb.table("trends").insert({"topic": t["topic"][:500], "source": t["source"], "score": t["score"]}).execute()
        except: pass
    return trends[:count]

def generate_script(topic):
    prompt = f"""You are a viral YouTube Shorts scriptwriter. Niche: interesting facts.
Topic: "{topic}"
Write a ~119 word spoken script with a hook in first 3 seconds and a call to action at the end.
Respond ONLY with valid JSON (no markdown):
{{"title":"catchy title max 100 chars","hook":"opening 1-2 sentences","script":"full spoken script","description":"2-3 sentence YouTube description","hashtags":"#fact1 #fact2 #Shorts #viral"}}"""
    r = http.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000},
        timeout=30)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)

async def _tts(text, path):
    import edge_tts
    await edge_tts.Communicate(text, "en-US-GuyNeural").save(path)

def generate_voice(script, filename):
    os.makedirs("/tmp/audio", exist_ok=True)
    path = f"/tmp/audio/{filename}.mp3"
    script = re.sub(r'\[.*?\]|\(.*?\)', '', script)
    script = re.sub(r'\s+', ' ', script).strip()
    asyncio.run(_tts(script, path))
    sb = get_sb()
    with open(path, "rb") as f:
        data = f.read()
    storage_path = f"audio/{filename}.mp3"
    try:
        sb.storage.from_("videos").upload(storage_path, data, {"content-type": "audio/mpeg", "upsert": "true"})
        return sb.storage.from_("videos").get_public_url(storage_path)
    except Exception as e:
        print(f"Storage error: {e}")
        return None

def run_pipeline(count=3):
    from datetime import datetime
    results = []
    trends = get_trends(count * 2)
    for i, trend in enumerate(trends[:count]):
        try:
            sd = generate_script(trend["topic"])
            title = sd.get("title", trend["topic"][:80])
            slug = re.sub(r'[^\w]', '_', title)[:30]
            filename = f"{slug}_{i}_{int(datetime.now().timestamp())}"
            audio_url = generate_voice(sd.get("script", ""), filename)
            row = {"title": title, "script": sd.get("script",""), "description": sd.get("description",""),
                   "hashtags": sd.get("hashtags","#Shorts"), "hook": sd.get("hook",""), "audio_url": audio_url, "status": "ready"}
            get_sb().table("videos").insert(row).execute()
            results.append(row)
            print(f"✅ Done: {title}")
        except Exception as e:
            print(f"❌ Error: {e}")
    return results

@app.route("/")
def index():
    return jsonify({"status": "YT Automation API running"})

@app.route("/api/run", methods=["POST"])
def run():
    try:
        count = request.json.get("count", 3) if request.json else 3
        return jsonify({"success": True, "videos": run_pipeline(count=count)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/videos", methods=["GET"])
def get_videos():
    data = get_sb().table("videos").select("*").order("created_at", desc=True).limit(50).execute()
    return jsonify(data.data)

@app.route("/api/trends", methods=["GET"])
def get_trends_route():
    data = get_sb().table("trends").select("*").order("created_at", desc=True).limit(20).execute()
    return jsonify(data.data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
