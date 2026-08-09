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
HEDRA_API_KEY = os.getenv("HEDRA_API_KEY")
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
# 1. توليد السكريبت المالي (اختيار النموذج الشغال)
# ==========================================
def generate_financial_script():
    prompt = "اكتب نصاً مالياً قصيراً واحترافياً لسيناريو فيديو مدته 30 ثانية عن أساسيات الاستثمار والتخطيط المالي. أريد النص المنطوق فقط بدون عناوين."
    
    candidate_models = [
        "gemma-2-9b-it",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ]
    
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for model_name in candidate_models:
        print(f"[+] تجربة الاتصال بالنموذج: {model_name} ...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()
            
            if response.status_code == 200:
                text = data['candidates'][0]['content']['parts'][0]['text']
                print(f"[✓] نجاح التوليد عبر النموذج: {model_name}")
                return text.strip()
            else:
                err_msg = data.get('error', {}).get('message', 'رفض غير معروف')
                print(f"[-] النموذج {model_name} غير متاح ({response.status_code}): {err_msg}")
        except Exception as e:
            print(f"[-] خطأ أثناء طلب النموذج {model_name}: {e}")
            
        time.sleep(2)

    raise Exception("فشل توليد النص بعد تجربة كافة النماذج المتاحة لمفتاحك.")

# ==========================================
# 2. توليد الصوت آلياً
# ==========================================
async def generate_audio(text: str, output_path: str):
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural", rate="+10%")
    await communicate.save(output_path)
    validate_file(output_path, "الصوت")

# ==========================================
# 3. تحريك الشخصية بواسطة Hedra API (مباشرة دون سيرفرات وسيطة)
# ==========================================
def generate_avatar_video_hedra(audio_path: str, avatar_url: str, output_path: str):
    headers = {
        "X-API-KEY": HEDRA_API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # 1. رفع الصوت المباشر إلى Hedra
    print("[+] رفع ملف الصوت المباشر إلى Hedra...")
    with open(audio_path, 'rb') as f:
        audio_resp = requests.post("https://api.hedra.com/v1/audio", files={"file": f}, headers=headers)
    if audio_resp.status_code not in [200, 201]:
        raise Exception(f"فشل رفع الصوت إلى Hedra: {audio_resp.text}")
    
    audio_data = audio_resp.json()
    audio_id = audio_data.get("id") or audio_data.get("audio_id")
    print(f"[✓] تم رفع الصوت بنجاح (Audio ID: {audio_id})")

    # 2. رفع صورة الشخصية إلى Hedra
    print("[+] جاري تجهيز ورفع صورة الشخصية إلى Hedra...")
    img_bytes = requests.get(avatar_url, timeout=30).content
    files = {"file": ("avatar.jpg", img_bytes, "image/jpeg")}
    
    img_resp = requests.post("https://api.hedra.com/v1/image", files=files, headers=headers)
    if img_resp.status_code not in [200, 201]:
        raise Exception(f"فشل رفع الصورة إلى Hedra: {img_resp.text}")
        
    img_data = img_resp.json()
    image_id = img_data.get("id") or img_data.get("image_id")
    print(f"[✓] تم رفع الصورة بنجاح (Image ID: {image_id})")

    # 3. طلب توليد فيديو تحريك الوجه
    print("[+] بدء توليد الفيديو في Hedra...")
    gen_payload = {
        "audio_id": audio_id,
        "image_id": image_id,
        "aspect_ratio": "16:9"
    }
    
    gen_resp = requests.post(
        "https://api.hedra.com/v1/characters", 
        json=gen_payload, 
        headers={"X-API-KEY": HEDRA_API_KEY, "Content-Type": "application/json"}
    )
    if gen_resp.status_code not in [200, 201]:
        raise Exception(f"فشل بدء توليد الفيديو في Hedra: {gen_resp.text}")
        
    job_data = gen_resp.json()
    job_id = job_data.get("job_id") or job_data.get("id")
    print(f"[+] تم بدء عملية التوليد برقم (Job ID: {job_id})، جاري الانتظار...")

    # 4. المتابعة حتى اكتمال المعالجة
    status_url = f"https://api.hedra.com/v1/characters/{job_id}"
    while True:
        status_resp = requests.get(status_url, headers=headers)
        res_data = status_resp.json()
        status = res_data.get("status", "").lower()

        if status in ["completed", "done", "success"]:
            video_url = res_data.get("video_url") or res_data.get("url") or res_data.get("result_url")
            print(f"[✓] اكتمل توليد الفيديو بنجاح! تنزيل الملف الخام...")
            vid_bytes = requests.get(video_url).content
            with open(output_path, 'wb') as f:
                f.write(vid_bytes)
            validate_file(output_path, "الفيديو الخام")
            break
        elif status in ["failed", "error"]:
            raise Exception(f"فشل معالجة Hedra: {res_data}")

        print("[+] المعالجة جارية في Hedra... انتظر 10 ثوانٍ.")
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
    
    generate_avatar_video_hedra("audio.mp3", AVATAR_IMAGE_URL, "raw_video.mp4")
    process_video("raw_video.mp4", script_text, "final_video.mp4")
    
    print("[✓] تم الانتهاء من تصدير الفيديو النهائي بنجاح!")

if __name__ == "__main__":
    asyncio.run(main())
