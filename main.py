# -*- coding: utf-8 -*-
# Telegram Bot + Selenium + chromedriver-autoinstaller
# ⚠️ استعمله فقط على موقعك أو موقع تجريبي بموافقة!

import os, time, random, re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import chromedriver_autoinstaller
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== إعدادات =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
HUMAN_DELAY_RANGE = (0.2, 0.6)

AR_FIRST = ["أمين","كمال","ياسر","لطفي","عادل","سارة","هدى","ليلى","منصف","نور"]
AR_LAST  = ["بن يوسف","بوزيد","قروي","عماري","زروقي","منصوري","أحميدة","عطوي","قدور","حراث"]
WILAYAS  = ["الجزائر","وهران","قسنطينة","البليدة","سطيف","تيزي وزو","بجاية","باتنة"]
BALADIS  = ["الدار البيضاء","الشراقة","الحمامات","بئر مراد","باب الواد","حيدرة","درارية","سيدي امحمد"]
STREETS  = ["شارع الاستقلال","شارع أول نوفمبر","حي القدس","حي النصر","طريق الجامعة","طريق الساحل"]

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

def classify_and_value(field,irow):
    name=(field.get("name") or "").lower()
    ph=(field.get("placeholder") or "").lower()
    ftype=field.get("type","").lower()
    tag=field.get("tag","")
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

def collect_form_fields(drv):
    fields=[]
    for el in drv.find_elements(By.CSS_SELECTOR,"input,select,textarea"):
        tag=el.tag_name.lower()
        ftype=el.get_attribute("type") or ""
        name=el.get_attribute("name") or el.get_attribute("id") or ""
        ph=el.get_attribute("placeholder") or ""
        if not name: continue
        fields.append({"name":name,"tag":tag,"type":ftype,"placeholder":ph})
    return fields

def fill_once_smart(drv, fields, irow):
    for fld in fields:
        try:
            name_or_id = fld.get("name")
            if not name_or_id: continue
            try: el = drv.find_element(By.NAME,name_or_id)
            except: 
                try: el = drv.find_element(By.ID,name_or_id)
                except: continue
            tag = fld.get("tag",""); ftype=fld.get("type","").lower()
            if tag=="textarea" or (tag=="input" and ftype in ["text","email","tel","number","password","date","search"]):
                val=classify_and_value(fld,irow)
                for char in val: 
                    el.send_keys(char)
                    time.sleep(random.uniform(0.05,0.18))
                continue
            if tag=="select": 
                sel=Select(el)
                opts=[o for o in sel.options if o.text.strip()]
                if opts: sel.select_by_visible_text(random.choice(opts).text)
                continue
            if tag=="input" and ftype in ["checkbox","radio"]:
                drv.execute_script("arguments[0].click();",el)
        except: continue

# ===== Telegram Bot =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ✨ بعتلي:\n/run <url> <عدد الطلبات>")

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("⚠️ الاستعمال: /run <url> <عدد>")
        return
    url = context.args[0]
    try: n = int(context.args[1])
    except: n = 1

    await update.message.reply_text(f"⏳ جاري إرسال {n} طلبات إلى: {url}")

    chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")

    success=0
    for i in range(1,n+1):
        try:
            drv=webdriver.Chrome(options=options)
            drv.get(url)
            fields=collect_form_fields(drv)
            fill_once_smart(drv,fields,i)
            try:
                btn=drv.find_element(By.CSS_SELECTOR,"input[type='submit'],button[type='submit']")
                drv.execute_script("arguments[0].click();",btn)
                success+=1
            except: pass
            drv.quit()
        except Exception as e:
            print("❌ خطأ:",e)

    await update.message.reply_text(f"✅ تم إرسال {success}/{n} بنجاح.")

# ===== Main =====
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run_command))
    app.run_polling()

if __name__=="__main__":
    main()
