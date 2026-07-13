# DentalPose Web

نسخه‌ی وبِ DentalPose — همون منطق ردیابی پوسچر نسخه‌ی دسکتاپ، ولی روی مرورگر گوشی
اجرا می‌شه (بدون نیاز به نصب اپ)، و داده‌ها روی یه سرور مرکزی ذخیره می‌شن.

## ساختار پروژه

```
dentalpose-web/
├── backend/          # FastAPI + SQLite
│   ├── app/
│   │   ├── main.py       # مسیرهای API
│   │   ├── models.py     # جدول‌های دیتابیس
│   │   ├── crud.py       # عملیات دیتابیس
│   │   ├── report.py     # ساخت PDF (پورت از نسخه‌ی دسکتاپ)
│   │   └── fonts/        # فونت فارسی برای PDF
│   ├── tests/         # تست‌های backend (11 تست، پاس شده)
│   └── requirements.txt
├── frontend/          # HTML/JS، بدون build step
│   ├── index.html
│   ├── style.css
│   └── js/
│       ├── config.js      # آستانه‌ها — دقیقاً مثل config.py
│       ├── tracking.js    # پورت tracking.py (فرمول زاویه‌ها یکسانه)
│       ├── api.js
│       └── app.js         # دوربین، MediaPipe، UI
└── render.yaml        # تنظیمات deploy روی Render.com
```

## تست محلی (قبل از deploy)

```bash
cd backend
pip install -r requirements.txt
python -m unittest discover tests -v   # باید 11 تست پاس بشه
uvicorn app.main:app --reload
```

بعد `http://localhost:8000` رو باز کن — همون‌جا هم API هم فرانت‌اند سرو می‌شن.

⚠️ **نکته:** روی `localhost` (نه HTTPS)، مرورگر معمولاً اجازه‌ی دسترسی به دوربین
می‌ده، ولی بعد از deploy روی یه دامنه‌ی واقعی، Render خودش HTTPS می‌ده که لازمه‌ی
کار کردن دوربین توی مرورگره.

## Deploy روی Render.com (رایگان)

۱. یه ریپازیتوری جدید توی GitHub بساز (مثلاً `dentalpose-web`) و کل این پوشه رو
   push کن:
   ```bash
   cd dentalpose-web
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<username>/dentalpose-web.git
   git push -u origin main
   ```

۲. برو به [render.com](https://render.com) → Sign up (می‌تونی مستقیم با GitHub
   وارد بشی) → **New +** → **Web Service**

۳. ریپازیتوری `dentalpose-web` رو انتخاب کن. Render خودش فایل `render.yaml` رو
   می‌بینه و تنظیمات (build/start command) رو خودکار پر می‌کنه.

۴. **Create Web Service** رو بزن. اولین build چند دقیقه طول می‌کشه (چون
   matplotlib و بقیه‌ی پکیج‌ها نصب می‌شن).

۵. وقتی تموم شد، Render یه لینک می‌ده مثل:
   ```
   https://dentalpose-web.onrender.com
   ```
   همین لینک رو به همکارات بده — روی گوشی باز می‌کنن، اسمشون رو وارد می‌کنن،
   کار می‌کنه.

### ⚠️ محدودیت پلن رایگان Render

سرویس رایگان بعد از ~۱۵ دقیقه بی‌استفاده «می‌خوابه» و درخواست بعدی چند ثانیه
طول می‌کشه تا بیدار بشه. برای تست اولیه مشکلی نیست؛ اگه بعداً جدی‌تر شد
(دیگه مرحله‌ی تست نیست)، باید پلن پولی (چند دلار در ماه) رو در نظر بگیری تا
سرویس همیشه روشن بمونه.

### دیتابیس

فعلاً SQLite — یه فایل ساده کنار کد. برای تعداد کم کاربر (چند همکار) کاملاً
کافیه. اگه بعداً کاربرها زیاد شدن یا خواستی از چند نسخه‌ی سرور همزمان استفاده
کنی، باید بری روی Postgres (Render خودش دیتابیس Postgres رایگان هم می‌ده) —
فقط کافیه `DATABASE_URL` رو عوض کنی، کد دیگه‌ای نیاز به تغییر نداره.

## چیزی که هنوز باقی مونده (برای فازهای بعدی)

- بک‌آپ خودکار دیتابیس (الان فقط روی دیسک Render‌ه؛ اگه سرویس پاک بشه دیتا هم می‌ره)
- احراز هویت واقعی (الان فقط اسم، بدون رمز — هرکسی اسم یکی دیگه رو بزنه می‌تونه
  داده‌هاشو ببینه)
- تست واقعی روی گوشی‌های مختلف (فقط منطق pure-JS تست شده، نه دوربین/MediaPipe
  واقعی روی مرورگر)
