# -*- coding: utf-8 -*-
# main.py
# Telegram-controlled REAL COMMANDE automation (Headless Selenium + Fullpage screenshot + Human-like)
# استعمله فقط على موقعك أو على بيئة اختبار بموافقة!

import os
import time
import random
import re
import json
import asyncio
import tempfile
from urllib.parse import urlparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ====== Configuration ======
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("Environment variable TELEGRAM_TOKEN is required.")

# chromedriver path: default for Railway/Render container, override with env if needed
CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH", "/app/chromedriver")

HUMAN_DELAY_RANGE = (0.2, 0.6)
FIELD_DELAY_RANGE = (0.1, 0.3)
STITCH_STEP_VIEWPORT = 0.9

AR_FIRST = ["أمين","كمال","ياسر","لطفي","عادل","سارة","هدى","ليلى","منصف","نور"]
AR_LAST  = ["بن يوسف","بوزيد","قروي","عماري","زروقي","منصوري","أحميدة","عطوي","قدور","حراث"]
WILAYAS  = ["الجزائر","وهران","قسنطينة","البليدة","سطيف","تيزي وزو","بجاية","باتنة"]
BALADIS  = ["الدار البيضاء","الشراقة","الحمامات","بئر مراد","باب الواد","حيدرة","درارية","سيدي امحمد"]
STREETS  = ["شارع الاستقلال","شارع أول نوفمبر","حي القدس","حي النصر","طريق الجامعة","طريق الساحل"]

# ====== Utility functions ======
def human_pause(rng=HUMAN_DELAY_RANGE):
    time.sleep(random.uniform(*rng))

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

def is_placeholder(text):
    return not text or text.strip().lower() in ("", "choose","choisir","اختر","sélectionner","select","—","-")

def scroll_into_view(drv,el):
    try: drv.execute_script("arguments[0].scrollIntoView({block:'center',inline:'center'});",el)
    except: pass

def move_mouse_to_element(drv, el):
    try: ActionChains(drv).move_to_element(el).pause(random.uniform(0.1,0.3)).perform()
    except: pass

def choose_select_option(sel_el):
    try:
        sel = Select(sel_el)
        opts=[o for o in sel.options if not is_placeholder(o.text)]
        if opts:
            # choose random visible text option
            sel.select_by_visible_text(random.choice(opts).text)
    except: pass

# ====== Blocking worker (runs in thread) ======
def selenium_collect_and_submit(url: str, n: int, tmpdir: str):
    """
    Blocking function that:
      - opens page headless,
      - collects form fields,
      - takes fullpage screenshot,
      - highlights fields,
      - then opens page n times submitting smart data,
    Returns:
      dict with keys: 'domain', 'screenshot_path', 'logs' (list of tuples (i, success, message))
    """
    logs = []
    parsed = urlparse(url)
    domain = parsed.netloc or "site"
    output_dir = Path(tmpdir) / domain
    output_dir.mkdir(parents=True, exist_ok=True)

    # Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    wait = WebDriverWait(driver, 12)

    # collect fields
    form_data = []
    all_fields = []
    for tag in ["input","select","textarea"]:
        try:
            all_fields += driver.find_elements(By.TAG_NAME, tag)
        except:
            pass

    def attr(el,name):
        try: return el.get_attribute(name) or ""
        except: return ""

    def tag_name(el):
        try: return el.tag_name.lower()
        except: return ""

    def get_form_parent_name(el):
        try:
            parent = el.find_element(By.XPATH, "ancestor::form")
            return attr(parent, "id") or attr(parent, "name") or "form_sans_nom"
        except:
            return "hors_form"

    def capture_field(el, idx):
        t = tag_name(el)
        name = attr(el, "name") or attr(el, "id")
        placeholder = attr(el, "placeholder")
        required = attr(el, "required") is not None
        typ = attr(el, "type").lower() if t == "input" else (t if t else "text")
        if t == "input" and typ in ["hidden","submit","button","file"]:
            return None
        try:
            loc = el.location; sz = el.size
            coords = (int(loc["x"]), int(loc["y"]), int(loc["x"] + sz["width"]), int(loc["y"] + sz["height"]))
        except:
            coords = None
        rec = {"index": idx, "form": get_form_parent_name(el), "name": name, "type": typ, "tag": t,
               "placeholder": placeholder, "required": required, "coords": coords}
        if t == "select":
            try:
                rec["options"] = [o.text.strip() for o in el.find_elements(By.TAG_NAME, "option") if o.text.strip()]
            except:
                rec["options"] = []
        return rec

    idx = 1
    for el in all_fields:
        item = capture_field(el, idx)
        if item:
            form_data.append(item)
            idx += 1

    # save JSON
    json_path = output_dir / "form_fields.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(form_data, f, ensure_ascii=False, indent=2)

    # take fullpage screenshot
    def take_fullpage_screenshot(drv, path):
        total_w = drv.execute_script("return document.documentElement.scrollWidth")
        total_h = drv.execute_script("return document.documentElement.scrollHeight")
        vp_w = drv.execute_script("return window.innerWidth")
        vp_h = drv.execute_script("return window.innerHeight")
        stitched = Image.new("RGB", (total_w, total_h))
        y = 0
        step = int(vp_h * STITCH_STEP_VIEWPORT) if vp_h else 800
        while y < total_h:
            drv.execute_script(f"window.scrollTo(0,{y});")
            time.sleep(0.2)
            shot = Image.open(BytesIO(drv.get_screenshot_as_png()))
            stitched.paste(shot, (0, y))
            y += step
        stitched.save(path)

    screenshot_path = output_dir / "screenshot_full.png"
    take_fullpage_screenshot(driver, str(screenshot_path))

    # highlight and save
    img = Image.open(screenshot_path)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()
    for it in form_data:
        if not it.get("coords"):
            continue
        x1, y1, x2, y2 = it["coords"]
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        draw.text((x1+3, y1+3), str(it["index"]), fill="red", font=font)

    highlighted_path = output_dir / "screenshot_full_highlighted.png"
    img.save(highlighted_path)

    # close initial driver (we'll re-open per submission to be clean)
    driver.quit()

    # helper to classify values
    def classify_and_value(field, irow):
        name = (field.get("name") or "").lower()
        ph = (field.get("placeholder") or "").lower()
        ftype = field.get("type","").lower()
        tag = field.get("tag","")
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

    def fill_once_smart_sync(drv, fields, irow):
        fields_to_fill = fields[:]
        if random.random() < 0.5:
            random.shuffle(fields_to_fill)
        for fld in fields_to_fill:
            try:
                name_or_id = fld.get("name")
                if not name_or_id:
                    continue
                try:
                    el = drv.find_element(By.NAME, name_or_id)
                except:
                    try:
                        el = drv.find_element(By.ID, name_or_id)
                    except:
                        continue
                scroll_into_view(drv, el)
                move_mouse_to_element(drv, el)
                WebDriverWait(drv,6).until(EC.visibility_of(el))
                tag = fld.get("tag",""); ftype = fld.get("type","").lower()
                if tag=="textarea" or (tag=="input" and ftype in ["text","email","tel","number","password","date","search"]):
                    val = classify_and_value(fld, irow)
                    for ch in val:
                        try:
                            el.send_keys(ch)
                        except:
                            pass
                        time.sleep(random.uniform(0.05,0.18))
                    human_pause(FIELD_DELAY_RANGE)
                    continue
                if tag=="select":
                    choose_select_option(el)
                    human_pause(FIELD_DELAY_RANGE)
                    continue
                if tag=="input" and ftype in ["checkbox","radio"]:
                    if random.random()<0.9 and re.search(r"(agree|terms|conditions|شروط|موافق)", name_or_id + fld.get("placeholder",""), re.I):
                        try: drv.execute_script("arguments[0].click();", el)
                        except: pass
                    human_pause(FIELD_DELAY_RANGE)
                    continue
            except:
                continue

    # perform N submissions
    for irow in range(1, n+1):
        try:
            fdrv = webdriver.Chrome(service=service, options=options)
            fdrv.get(url)
            human_pause()
            fill_once_smart_sync(fdrv, form_data, irow)
            try:
                submit_btn = fdrv.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
                fdrv.execute_script("arguments[0].click();", submit_btn)
                logs.append((irow, True, "Submitted"))
            except Exception as e:
                logs.append((irow, False, f"Submit failed: {e}"))
            human_pause((0.5,1.2))
            fdrv.quit()
        except Exception as ex:
            logs.append((irow, False, f"Driver error: {ex}"))
            try:
                fdrv.quit()
            except:
                pass

    return {
        "domain": domain,
        "screenshot_path": str(highlighted_path),
        "json_path": str(json_path),
        "logs": logs
    }

# ====== Async wrapper that calls blocking worker in thread ======
async def worker_run_and_report(url: str, n: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    tmpdir = os.getcwd()  # save files into current working dir (Railway persists within build)
    loop = asyncio.get_event_loop()
    # run blocking selenium code in thread
    try:
        result = await asyncio.to_thread(selenium_collect_and_submit, url, n, tmpdir)
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ خلل أثناء التنفيذ: {e}")
        return

    # send screenshot + JSON + logs
    try:
        # send screenshot
        spath = result.get("screenshot_path")
        if spath and os.path.exists(spath):
            await context.bot.send_photo(chat_id=chat_id, photo=InputFile(spath))
        # send json as file
        jpath = result.get("json_path")
        if jpath and os.path.exists(jpath):
            await context.bot.send_document(chat_id=chat_id, document=InputFile(jpath))
        # send logs summary
        logs = result.get("logs", [])
        summary_lines = []
        for i, ok, msg in logs:
            symbol = "✅" if ok else "⚠️"
            summary_lines.append(f"{symbol} الطلب #{i}: {msg}")
        summary_text = "\n".join(summary_lines) if summary_lines else "لا توجد سجلات."
        await context.bot.send_message(chat_id=chat_id, text=f"📋 ملخص الطلبات:\n{summary_text}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ تعذّر إرسال الملفات: {e}")

# ====== Telegram command handler ======
async def faux_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        if not context.args or len(context.args) < 2:
            await context.bot.send_message(chat_id=chat_id, text="❗ استعمل: /faux [link] [nombre]\nمثال: /faux https://example.com/product 3")
            return
        link = context.args[0]
        try:
            n = int(context.args[1])
            if n <= 0:
                raise ValueError()
        except:
            await context.bot.send_message(chat_id=chat_id, text="❗ العدد لازم يكون عدد صحيح موجب.")
            return

        await context.bot.send_message(chat_id=chat_id, text=f"⌛ بدء تنفيذ {n} طلبات على: {link}")
        # run blocking Selenium in background thread and report results
        asyncio.create_task(worker_run_and_report(link, n, context, chat_id))

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ خطأ: {e}")

# ====== Start bot ======
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("faux", faux_command))
    print("🤖 البوت جاهز لاستقبال الأوامر")
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
