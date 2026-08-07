import os
import asyncio
import requests
import json
import edge_tts
import google.generativeai as genai
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ==========================================
# إعدادات البيئة السحابية
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DID_API_KEY = os.getenv("DID_API_KEY")
AVATAR_IMAGE_URL = os.getenv("AVATAR_IMAGE_URL")

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# دالة الحماية وفحص الملفات
# ==========================================
def validate_file(file_path: str, file_type: str):
    """التحقق من وجود الملف وأن حجمه أكبر من صفر بايت لتجنب الأخطاء"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"خطأ: ملف {file_type} ({file_path}) غير موجود.")
    if os.path.getsize(file_path) == 0:
        raise ValueError(f"خطأ: ملف {file_type} ({file_path}) تالف أو حجمه 0 بايت.")
    print(f"[✓] تم فحص وتأكيد سلامة ملف {file_type}.")

# ==========================================
# 1. توليد السكريبت المالي
# ==========================================
import os
import time
from google import genai

# إنشاء العميل باستخدام المفتاح السري
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_financial_script():
    prompt = "اكتب نصاً مالياً قصيراً واحترافياً لسيناريو فيديو مدته 30 ثانية عن أساسيات الاستثمار والتخطيط المالي."
    
    # آلية المحاولة والتغلب على الضغط
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            print(f"المحاولة رقم {attempt + 1} فشلت: {e}")
            time.sleep(15)
            
    raise Exception("فشل توليد النص بعد 3 محاولات بسبب قيود الـ API")


# ==========================================
# 2. توليد الصوت وإرفاقه سحابياً
# ==========================================
async def generate_audio(text: str, output_path: str):
    # استخدام صوت مصري واثق ومناسب للمحتوى المالي
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural", rate="+10%")
    await communicate.save(output_path)
    validate_file(output_path, "الصوت")

def upload_temp_audio(file_path: str) -> str:
    """رفع الصوت مؤقتاً لتمكين D-ID من قراءته سحابياً"""
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
    
    print("[+] جاري معالجة الفيديو في D-ID...")
    import time
import google.generativeai as genai

# استخدم هذا النموذج المستقر
model = genai.GenerativeModel('gemini-1.5-pro')

def generate_financial_script():
    prompt = "اكتب النص المالي المخصص هنا..."
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"Waiting for rate limit... Attempt {attempt + 1}")
                time.sleep(20) # انتظار 20 ثانية قبل إعادة المحاولة
            else:
                raise e
    raise Exception("Failed after 3 retries due to rate limit.")

# ==========================================
# 4. المونتاج وإضافة الترجمة
# ==========================================
def process_video(raw_video: str, text_overlay: str, final_output: str):
    clip = VideoFileClip(raw_video)
    txt_clip = TextClip(
        text_overlay[:30] + "...", # عرض جزء تشويقي من النص
        fontsize=40, color='yellow', font='Arial-Bold', bg_color='black',
        size=(clip.w * 0.9, None), method='caption'
    ).set_duration(clip.duration).set_position(('center', 'bottom'))
    
    final_clip = CompositeVideoClip([clip, txt_clip])
    final_clip.write_videofile(final_output, codec="libx264", audio_codec="aac", fps=24)
    validate_file(final_output, "الفيديو النهائي")

# ==========================================
# المحرك الرئيسي
# ==========================================
async def main():
    print("--- بدء الأتمتة المالية ---")
    data = generate_financial_script()
    print(f"[+] الموضوع اليوم: {data['title']}")
    
    await generate_audio(data['script'], "audio.mp3")
    temp_audio_url = upload_temp_audio("audio.mp3")
    print("[+] تم رفع الصوت للسيرفر الوسيط بنجاح.")
    
    generate_avatar_video(temp_audio_url, AVATAR_IMAGE_URL, "raw_video.mp4")
    process_video("raw_video.mp4", data['script'], "final_video.mp4")
    
    print("[✓] تم الانتهاء من تصدير الفيديو النهائي. (تم تجاوز دالة الرفع ليوتيوب لحين إضافة ملف التوكن الخاص بك)")

if __name__ == "__main__":
    asyncio.run(main())
