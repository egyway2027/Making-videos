import os
import asyncio
import requests
import time
import edge_tts
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

# ==========================================
# إعدادات البيئة السحابية
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DID_API_KEY = os.getenv("DID_API_KEY")
AVATAR_IMAGE_URL = os.getenv("AVATAR_IMAGE_URL")

# ==========================================
# دالة الحماية وفحص الملفات
# ==========================================
def validate_file(file_path: str, file_type: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"خطأ: ملف {file_type} ({file_path}) غير موجود.")
    if os.path.getsize(file_path) == 0:
        raise ValueError(f"خطأ: ملف {file_type} ({file_path}) تالف أو حجمه 0 بايت.")
    print(f"[✓] تم فحص وتأكيد سلامة ملف {file_type}.")

# ==========================================
# 1. توليد السكريبت المالي (مباشرة عبر API بدون مكتبة جوجل)
# ==========================================
def generate_financial_script():
    prompt = "اكتب نصاً مالياً قصيراً واحترافياً لسيناريو فيديو مدته 30 ثانية عن أساسيات الاستثمار والتخطيط المالي. أريد النص المنطوق فقط."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            if response.status_code == 200:
                # استخراج النص بنجاح
                text = data['candidates'][0]['content']['parts'][0]['text']
                return text.strip()
            else:
                print(f"المحاولة رقم {attempt + 1} فشلت بسبب رفض السيرفر: {data}")
                time.sleep(15)
        except Exception as e:
            print(f"المحاولة رقم {attempt + 1} فشلت بسبب خطأ اتصال: {e}")
            time.sleep(15)
            
    raise Exception("فشل توليد النص من Gemini بعد 3 محاولات مباشرة.")

# ==========================================
# 2. توليد الصوت وإرفاقه سحابياً
# ==========================================
async def generate_audio(text: str, output_path: str):
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural", rate="+10%")
    await communicate.save(output_path)
    validate_file(output_path, "الصوت")

def upload_temp_audio(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        response = requests.post('https://file.io', files={'file': f})
    if response.status_code == 200:
        return response.json()['link']
    raise Exception("فشل رفع الصوت المؤقت للسيرفر الوسيط.")

# ==========================================
# 3. تحريك الشخصية (D-ID)
# ==========================================
def generate_avatar_video(audio_url: str, avatar_url: str, output_path: str):
    url = "https://api.d-id.com/talks"
    headers = {"Authorization": f"Basic {DID_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "source_url": avatar_url,
        "script": {"type": "audio", "audio_url": audio_url},
        "config": {"fluent": "true", "pad_audio": "0.0"}
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code not in [200, 201]:
        raise Exception(f"فشل الاتصال بـ D-ID: {response.text}")
        
    talk_id = response.json().get("id")
    status_url = f"https://api.d-id.com/talks/{talk_id}"
    
    print("[+] جاري معالجة الفيديو في D-ID (يرجى الانتظار، قد يستغرق دقيقة)...")
    
    while True:
        status_response = requests.get(status_url, headers=headers)
        status_data = status_response.json()
        status = status_data.get("status")
        
        if status == "done":
            print("[+] اكتملت المعالجة بنجاح! جاري تنزيل الفيديو الخام...")
            vid_url = status_data.get("result_url")
            vid_resp = requests.get(vid_url)
            with open(output_path, 'wb') as f:
                f.write(vid_resp.content)
            validate_file(output_path, "الفيديو الخام")
            break
        elif status == "error":
            raise Exception(f"خطأ في معالجة D-ID: {status_data}")
        
        time.sleep(10)

# ==========================================
# 4. المونتاج وإضافة الترجمة
# ==========================================
def process_video(raw_video: str, text_overlay: str, final_output: str):
    clip = VideoFileClip(raw_video)
    
    txt_clip = TextClip(
        text=text_overlay[:40] + "...", 
        font='Arial', 
        font_size=40, 
        color='yellow', 
        bg_color='black',
        method='caption',
        size=(int(clip.w * 0.9), None)
    ).with_duration(clip.duration).with_position(('center', 'bottom'))
    
    final_clip = CompositeVideoClip([clip, txt_clip])
    final_clip.write_videofile(final_output, codec="libx264", audio_codec="aac", fps=24)
    validate_file(final_output, "الفيديو النهائي")

# ==========================================
# المحرك الرئيسي
# ==========================================
async def main():
    print("--- بدء الأتمتة المالية ---")
    
    script_text = generate_financial_script()
    print(f"[+] النص المولد:\n{script_text}\n")
    
    await generate_audio(script_text, "audio.mp3")
    temp_audio_url = upload_temp_audio("audio.mp3")
    print("[+] تم رفع الصوت للسيرفر الوسيط بنجاح.")
    
    generate_avatar_video(temp_audio_url, AVATAR_IMAGE_URL, "raw_video.mp4")
    process_video("raw_video.mp4", script_text, "final_video.mp4")
    
    print("[✓] تم الانتهاء من تصدير الفيديو النهائي بنجاح!")

if __name__ == "__main__":
    asyncio.run(main())
