# -*- coding: utf-8 -*-
# REAL COMMANDE AUTOMATION + FULLPAGE SCREENSHOT + HUMAN-LIKE + TELEGRAM BOT
# استعمله فقط على موقعك أو موقع تجريبي بموافقة!

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import *
import json, time, os, random, re
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# ===== إعدادات =====
CHROMEDRIVER_PATH = r"/app/chromedriver"  # مسار chromedriver على سيرفر
TELEGRAM_TOKEN = "8243189277:AAFQZXaxGBo9FHviotKvnToXb0kiNOyfiRs"  
HUMAN_DELAY_RANGE = (0.2, 0.6)
FIELD_DELAY_RANGE = (0.1, 0.3)
STITCH_STEP_VIEWPORT = 0.9

# بيانات عربية
AR_FIRST = ["أمين","كمال","ياسر","لطفي","عادل","سارة","هدى","ليلى","منصف","نور"]
AR_LAST  = ["بن يوسف","بوزيد","قروي","عماري","زروقي","منصوري","أحميدة","عطوي","قدور","حراث"]
WILAYAS  = ["الجزائر","وهران","قسنطينة","البليدة","سطيف","تيزي وزو","بجاية","باتنة"]
BALADIS  = ["الدار البيضاء","الشراقة","الحمامات","بئر مراد","باب الواد","حيدرة","درارية","سيدي امحمد"]
STREETS  = ["شارع الاستقلال","شارع أول نوفمبر","حي القدس","حي النصر","طريق الجامعة","طريق الساحل"]

# ===== دوال توليد البيانات =====
def rand_phone(): return "06" + str(random.randint(50000000, 79999999))
def rand_email(first,last,i=0):
    domains=["example.com","test.me","mail.local"]
    base=re.sub(r"\s+","",first.lower())+"."+re.sub(r"\s+","",last.lower())
    suf=f".{i}" if i else ""
    return f"{base}{suf}@{random.choice(domains)}"
def rand_name(): return random.choice(AR_FIRST)+" "+random.choice(AR_LAST)
def rand_address(): return f"{random.choice(STREETS)} رقم {random.randint(1,199)}"
def rand_postal(): return str(random.randint(10000,49999))
def rand_note(): return "طلب حقيقي - توليد تلقائي"
def human_pause(rng=HUMAN_DELAY_RANGE): time.sleep(random.uniform(*rng))

# ===== دوال مساعدة =====
def is_placeholder(text): return not text or text.strip().lower() in ("", "choose","choisir","اختر","sélectionner","select","—","-")
def scroll_into_view(drv,el): 
    try: drv.execute_script("arguments[0].scrollIntoView({block:'center',inline:'center'});",el)
    except: pass
def choose_select_option(sel_el):
    try:
        sel = Select(sel_el)
        opts=[o for o in sel.options if not is_placeholder(o.text)]
        if opts: sel.select_by_visible_text(random.choice(opts).text)
    except: pass
def move_mouse_to_element(drv, el):
    try: ActionChains(drv).move_to_element(el).pause(random.uniform(0.1,0.3)).perform()
    except: pass

# ===== الوظيفة الأساسية لإرسال الطلب =====
def send_order(URL_SITE,N,update=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
    driver.get(URL_SITE)
    wait = WebDriverWait(driver,12)

    # جمع الحقول
    form_data=[]
    all_fields=[]
    for tag in ["input","select","textarea"]:
        try: all_fields += driver.find_elements(By.TAG_NAME,tag)
        except: pass

    def attr(el,name): 
        try: return el.get_attribute(name) or ""
        except: return ""
    def tag_name(el):
        try: return el.tag_name.lower()
        except: return ""
    def get_form_parent_name(el):
        try: parent=el.find_element(By.XPATH,"ancestor::form"); return attr(parent,"id") or attr(parent,"name") or "form_sans_nom"
        except: return "hors_form"
    def capture_field(el,idx):
        t=tag_name(el); name=attr(el,"name") or attr(el,"id"); placeholder=attr(el,"placeholder"); required=attr(el,"required") is not None
        typ=attr(el,"type").lower() if t=="input" else (t if t else "text")
        if t=="input" and typ in ["hidden","submit","button","file"]: return None
        try: loc=el.location; sz=el.size; coords=(int(loc["x"]),int(loc["y"]),int(loc["x"]+sz["width"]),int(loc["y"]+sz["height"]))
        except: coords=None
        rec={"index":idx,"form":get_form_parent_name(el),"name":name,"type":typ,"tag":t,"placeholder":placeholder,"required":required,"coords":coords}
        if t=="select":
            try: rec["options"]=[o.text.strip() for o in el.find_elements(By.TAG_NAME,"option") if o.text.strip()]
            except: rec["options"]=[] 
        return rec

    idx=1
    for el in all_fields:
        item=capture_field(el,idx)
        if item: form_data.append(item); idx+=1

    # ==== إرسال الطلبات الذكي ====
    def classify_and_value(field,irow):
        name=(field.get("name") or "").lower(); ph=(field.get("placeholder") or "").lower(); ftype=field.get("type","").lower(); tag=field.get("tag","")
        def has(*keys): return any(k in (name+ph) for k in keys)
        if has("full","nom","name","الاسم"): return rand_name()
        if has("first","prenom","الاسم الاول"): return random.choice(AR_FIRST)
        if has("last","family","العائلة"): return random.choice(AR_LAST)
        if has("phone","tel","هاتف"): return rand_phone()
        if has("mail","email","e-mail"): fn,ln=random.choice(AR_FIRST),random.choice(AR_LAST); return rand_email(fn,ln,irow)
        if has("wilaya","ولاية"): return random.choice(WILAYAS)
        if has("city","ville","commune","بلدية"): return random.choice(BALADIS)
        if has("country","بلد","دولة"): return "Algeria"
        if has("address","عنوان","street"): return rand_address()
        if has("zip","postal","رمز"): return rand_postal()
        if has("qty","quantity","كمية"): return str(random.randint(1,3))
        if has("note","message","comment","ملاحظة"): return rand_note()
        if ftype=="date": return f"2025-0{random.randint(1,6)}-{random.randint(10,28)}"
        if ftype=="number": return str(random.randint(1,99))
        return "test"

    def fill_once_smart(drv, fields, irow):
        fields_to_fill = fields[:]
        if random.random()<0.5: random.shuffle(fields_to_fill)
        for fld in fields_to_fill:
            try:
                name_or_id = fld.get("name")
                if not name_or_id: continue
                try: el = drv.find_element(By.NAME,name_or_id)
                except: 
                    try: el = drv.find_element(By.ID,name_or_id)
                    except: continue
                scroll_into_view(drv, el)
                move_mouse_to_element(drv, el)
                WebDriverWait(drv,6).until(EC.visibility_of(el))
                tag = fld.get("tag",""); ftype=fld.get("type","").lower()
                if tag=="textarea" or (tag=="input" and ftype in ["text","email","tel","number","password","date","search"]):
                    val=classify_and_value(fld,irow)
                    for char in val: 
                        try: el.send_keys(char)
                        except: pass
                        time.sleep(random.uniform(0.05,0.18))
                    human_pause(FIELD_DELAY_RANGE)
                    continue
                if tag=="select": 
                    choose_select_option(el)
                    human_pause(FIELD_DELAY_RANGE)
                    continue
                if tag=="input" and ftype in ["checkbox","radio"]:
                    if random.random()<0.9 and re.search(r"(agree|terms|conditions|شروط|موافق)",name_or_id+fld.get("placeholder",""),re.I):
                        try: drv.execute_script("arguments[0].click();",el)
                        except: pass
                    human_pause(FIELD_DELAY_RANGE)
                    continue
            except: continue

    for irow in range(1,N+1):
        fdrv=webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        fdrv.get(URL_SITE)
        human_pause()
        fill_once_smart(fdrv,form_data,irow)
        try:
            submit_btn=fdrv.find_element(By.CSS_SELECTOR,"input[type='submit'], button[type='submit']")
            fdrv.execute_script("arguments[0].click();",submit_btn)
            msg=f"✅ الطلب رقم {irow} تم إرساله بنجاح!"
            print(msg)
            if update: update.message.reply_text(msg)
        except Exception:
            msg=f"⚠️ الطلب رقم {irow} لم يتم إرساله."
            print(msg)
            if update: update.message.reply_text(msg)
        human_pause((0.5,1.2))
        fdrv.quit()
    driver.quit()
    if update: update.message.reply_text("✅ انتهى إرسال جميع الطلبات.")

# ===== Telegram Bot Handler =====
def faux_command(update: Update, context: CallbackContext):
    try:
        link = context.args[0]
        N = int(context.args[1])
        update.message.reply_text(f"⌛ جاري إرسال {N} طلب على {link} …")
        send_order(link,N,update)
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {e}\nاستعمل الصيغة: /faux [link] [nombre]")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("faux", faux_command))
    print("🤖 البوت جاهز لاستقبال الأوامر على Telegram!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
