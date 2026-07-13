"""
DentalPose Web — PDF Report Generator
همون منطق نسخه‌ی دسکتاپ (زمان واقعی بدپاسچر به تفکیک روز + توصیه + مخرج جدا
برای هیپ/زانو موقع ایستاده + تاریخ شمسی)، فقط ورودیش ردیف‌های دیتابیسه
به‌جای فایل‌های CSV.
"""
import os
import io
import logging
import textwrap
from datetime import datetime, date
from collections import defaultdict
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages

logger = logging.getLogger(__name__)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _RTL_OK = True
except ImportError:
    _RTL_OK = False
    logger.warning("arabic_reshaper/python-bidi not installed — Persian text will render incorrectly")


def rtl_shaping_available() -> bool:
    return _RTL_OK


def _fa(text: str) -> str:
    if not _RTL_OK:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _fa_font(bold: bool = False) -> Optional[fm.FontProperties]:
    name = "Vazirmatn-Bold.ttf" if bold else "Vazirmatn-Regular.ttf"
    path = os.path.join(_FONT_DIR, name)
    if os.path.exists(path):
        return fm.FontProperties(fname=path)
    logger.warning(f"Persian font not found at {path}")
    return None


def _to_jalali(g_date) -> str:
    """تبدیل تاریخ میلادی به شمسی — همون الگوریتم نسخه‌ی دسکتاپ، کراس‌چک‌شده با jdatetime"""
    gy, gm, gd = g_date.year, g_date.month, g_date.day
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    gy2 = gy - 1 if gm < 3 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400)
    for i in range(gm - 1):
        days += g_days_in_month[i]
    if gm > 2 and (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)):
        days += 1
    days += gd

    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)

    return f"{jy:04d}-{jm:02d}-{jd:02d}"


AREAS = ['hip', 'knee', 'neck', 'chin', 'shoulder']
AREA_FA = {'hip': 'لگن', 'knee': 'زانو', 'neck': 'گردن', 'chin': 'کج‌شدگی سر', 'shoulder': 'شونه'}
AREA_COLOR = {'hip': '#4A9EFF', 'knee': '#00D4AA', 'neck': '#FF4B4B',
              'chin': '#C084FC', 'shoulder': '#FFB347'}

DAILY_BAD_THRESHOLD_PCT = 10.0

RECOMMENDATIONS = {
    'hip': "زاویه‌ی لگن شما بخش قابل‌توجهی از این روز خارج از محدوده‌ی نرمالتون بوده — "
           "معمولاً نشونه‌ی خم‌شدن طولانی‌مدت تنه به‌سمت جلو برای رسیدن به بیمار. "
           "ارتفاع صندلی رو بالاتر ببرید یا صندلی بیمار رو نزدیک‌تر بیارید تا فاصله‌ی دسترسی کم بشه.",
    'knee': "زاویه‌ی زانوی شما مدت قابل‌توجهی از باسلاین‌تون فاصله داشته — "
            "معمولاً به‌خاطر ارتفاع نامناسب صندلی یا جمع‌کردن/ضربدری‌کردن پاها حین کار. "
            "مطمئن بشید هر دو پا صاف روی زمین باشه و ارتفاع صندلی طوری باشه که ران‌ها تقریباً افقی بمونن.",
    'neck': "خمیدگی گردن شما بخش قابل‌توجهی از این روز از محدوده‌ی نرمال بیشتر بوده — "
            "نشونه‌ی رایج خم‌کردن سر به‌سمت پایین برای دیدن حفره‌ی کار. "
            "صندلی بیمار رو بالاتر بیارید تا نیازی به خم‌کردن گردن نباشه، یا از لوپ با زاویه‌ی declination بیشتر استفاده کنید.",
    'chin': "کج‌شدگی سر شما بخش قابل‌توجهی از این روز از محدوده‌ی نرمال بیشتر بوده — "
            "نشونه‌ی رایج خم‌کردن سر به‌سمت پایین برای دیدن حفره‌ی کار. "
            "صندلی بیمار رو بالاتر بیارید تا نیازی به خم‌کردن گردن نباشه، یا از لوپ با زاویه‌ی declination بیشتر استفاده کنید.",
    'shoulder': "بالاآمدگی شونه‌ی شما مدت قابل‌توجهی از این روز بالا بوده — "
                "یعنی برای رسیدن به محدوده‌ی کاری، بازو رو بالا نگه داشتین. "
                "صندلی بیمار رو پایین‌تر بیارید، طوری که محدوده‌ی کاری (دهان بیمار) تقریباً هم‌سطح آرنج شما "
                "باشه وقتی شونه در حالت نرمال و آویزونه.",
}


def _collect_history(frame_rows):
    """
    frame_rows: لیست PostureFrameRow (از دیتابیس، مرتب‌شده بر اساس زمان)
    خروجی دقیقاً هم‌ساختار نسخه‌ی دسکتاپه: به تفکیک روز، با مخرج زمانی جدا
    برای هیپ/زانو (زمان ایستاده حذف میشه).
    """
    if not frame_rows:
        return None

    day_bad = defaultdict(lambda: {a: 0.0 for a in AREAS})
    day_total = defaultdict(lambda: {a: 0.0 for a in AREAS})
    day_angle_sum = defaultdict(lambda: {'hip': 0.0, 'knee': 0.0, 'neck': 0.0, 'shoulder': 0.0})
    day_angle_n = defaultdict(int)

    # فاصله‌ی متوسط بین فریم‌ها برای cap کردن پرش بین سشن‌ها/وقفه‌ها
    times = [r.time for r in frame_rows]
    diffs = sorted(t2 - t1 for t1, t2 in zip(times, times[1:]) if t2 > t1)
    median_diff = diffs[len(diffs)//2] if diffs else 0.2
    cap = max(median_diff * 5, 2.0)

    for i in range(len(frame_rows) - 1):
        r0, r1 = frame_rows[i], frame_rows[i+1]
        dt = min(r1.time - r0.time, cap)
        if dt <= 0:
            continue
        day = datetime.fromtimestamp(r0.time).date()

        day_angle_sum[day]['hip'] += r0.hip_angle or 0
        day_angle_sum[day]['knee'] += r0.knee_angle or 0
        day_angle_sum[day]['neck'] += r0.neck_angle or 0
        day_angle_sum[day]['shoulder'] += r0.shoulder_elev_pct or 0
        day_angle_n[day] += 1

        bad_flags = {'hip': r0.hip_bad, 'knee': r0.knee_bad, 'neck': r0.neck_bad,
                     'chin': r0.chin_bad, 'shoulder': r0.shoulder_bad}
        for a in AREAS:
            if r0.is_standing and a in ('hip', 'knee'):
                continue
            day_total[day][a] += dt
            if bad_flags[a]:
                day_bad[day][a] += dt

    if not day_total:
        return None

    days = sorted(day_total.keys())
    n_sessions = len(set(r.session_id for r in frame_rows))
    return {
        'days': days,
        'day_bad': day_bad,
        'day_total': day_total,
        'day_angle_avg': {
            d: {k: (v/day_angle_n[d] if day_angle_n[d] else 0.0) for k, v in day_angle_sum[d].items()}
            for d in days
        },
        'n_sessions': n_sessions,
    }


def _build_charts_page(doctor_name: str, hist: dict, font_reg, font_bold):
    days = hist['days']
    day_total = hist['day_total']
    day_bad = hist['day_bad']
    day_angle_avg = hist['day_angle_avg']

    total_minutes = sum(day_total[d]['neck'] for d in days) / 60.0
    total_bad_min = {a: sum(day_bad[d][a] for d in days) / 60.0 for a in AREAS}

    fig = plt.figure(figsize=(8.27, 11.69), facecolor='white')
    fig.text(0.1, 0.965, _fa("گزارش پاسچر — DentalPose"), fontsize=17,
              fontproperties=font_bold, ha='left')
    fig.text(0.1, 0.94, _fa(f"دکتر: {doctor_name}"), fontsize=12, fontproperties=font_reg, ha='left')
    fig.text(0.1, 0.92, _fa(f"تاریخ تولید گزارش: {_to_jalali(datetime.now().date())}"),
              fontsize=9, color='gray', fontproperties=font_reg, ha='left')
    fig.text(0.1, 0.90,
              _fa(f"تعداد سشن: {hist['n_sessions']}  |  زمان کل ردیابی‌شده: "
                  f"{total_minutes:.0f} دقیقه (~{total_minutes/60:.1f} ساعت)  |  "
                  f"تعداد روزهای فعال: {len(days)}"),
              fontsize=9, fontproperties=font_reg, ha='left')

    date_labels = [_to_jalali(d)[5:] for d in days]
    x = list(range(len(days)))

    ax1 = fig.add_axes([0.12, 0.63, 0.76, 0.18])
    for key, color, label in [('neck', AREA_COLOR['neck'], 'گردن'),
                               ('hip', AREA_COLOR['hip'], 'لگن'),
                               ('knee', AREA_COLOR['knee'], 'زانو')]:
        vals = [day_angle_avg[d][key] for d in days]
        ax1.plot(x, vals, color=color, lw=1.4, marker='o', ms=3, label=_fa(label))
    ax1.set_title(_fa("روند زاویه‌ها (میانگین روزانه)"), fontsize=10, fontproperties=font_bold)
    ax1.set_ylabel(_fa("زاویه (درجه)"), fontsize=8, fontproperties=font_reg)
    ax1.legend(prop=font_reg, fontsize=7, loc='best')
    ax1.set_xticks(x)
    ax1.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=6)
    if len(x) > 15:
        step = len(x) // 15 + 1
        ax1.set_xticks(x[::step]); ax1.set_xticklabels(date_labels[::step], rotation=45, ha='right', fontsize=6)

    ax2 = fig.add_axes([0.12, 0.40, 0.34, 0.16])
    labels_fa = [_fa(AREA_FA[a]) for a in AREAS]
    vals_min = [total_bad_min[a] for a in AREAS]
    colors = [AREA_COLOR[a] for a in AREAS]
    bars = ax2.bar(labels_fa, vals_min, color=colors)
    for bar, v in zip(bars, vals_min):
        ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f'{v:.0f}',
                  ha='center', va='bottom', fontsize=7)
    ax2.set_title(_fa("کل زمان بدپاسچر (دقیقه)"), fontsize=10, fontproperties=font_bold)
    ax2.tick_params(axis='x', labelsize=7)
    for lbl in ax2.get_xticklabels():
        lbl.set_fontproperties(font_reg)

    ax3 = fig.add_axes([0.55, 0.40, 0.33, 0.16])
    sh_vals = [day_angle_avg[d]['shoulder'] for d in days]
    ax3.plot(x, sh_vals, color=AREA_COLOR['shoulder'], lw=1.4, marker='o', ms=3)
    ax3.set_title(_fa("روند بالاآمدگی شونه (میانگین روزانه)"), fontsize=10, fontproperties=font_bold)
    ax3.set_ylabel('%', fontsize=8)
    ax3.set_xticks(x)
    ax3.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=6)
    if len(x) > 15:
        step = len(x) // 15 + 1
        ax3.set_xticks(x[::step]); ax3.set_xticklabels(date_labels[::step], rotation=45, ha='right', fontsize=6)

    fig.text(0.1, 0.06, _fa("این گزارش خودکار تولید می‌شود و جایگزین ارزیابی بالینی نیست."),
              fontsize=7, color='gray', fontproperties=font_reg, ha='left')
    return fig


def _wrap_fa(text: str, width: int = 58) -> list:
    return textwrap.wrap(text, width=width)


def _build_daily_pages(doctor_name: str, hist: dict, font_reg, font_bold):
    days = hist['days']
    day_total = hist['day_total']
    day_bad = hist['day_bad']

    pages = []
    fig, ax = None, None
    y = 0.0
    LINE_H = 0.022
    TOP = 0.95
    BOTTOM = 0.06

    def new_page():
        nonlocal fig, ax, y
        if fig is not None:
            pages.append(fig)
        fig = plt.figure(figsize=(8.27, 11.69), facecolor='white')
        ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off')
        y = TOP
        ax.text(0.9, y, _fa(f"گزارش روزانه — {doctor_name}"), fontsize=13,
                 fontproperties=font_bold, ha='right', transform=ax.transAxes)
        y -= LINE_H * 2

    def ensure_space(n_lines):
        nonlocal y
        if y - n_lines * LINE_H < BOTTOM:
            new_page()

    new_page()

    for day in sorted(days, reverse=True):
        day_total_areas = day_total.get(day, {})
        total_s_overall = day_total_areas.get('neck', 0.0)
        if total_s_overall <= 0:
            continue
        total_min = total_s_overall / 60.0

        triggered = []
        for a in AREAS:
            area_total_s = day_total_areas.get(a, 0.0)
            if area_total_s <= 0:
                continue
            bad_s = day_bad[day][a]
            pct = (bad_s / area_total_s * 100)
            if pct > DAILY_BAD_THRESHOLD_PCT:
                triggered.append((a, bad_s / 60.0, pct))

        header = f"{_to_jalali(day)}   —   زمان ردیابی‌شده: {total_min:.0f} دقیقه"
        n_lines_needed = 2 + (0 if triggered else 1)
        for a, _, _ in triggered:
            n_lines_needed += 1 + len(_wrap_fa(RECOMMENDATIONS[a]))
        ensure_space(n_lines_needed)

        ax.text(0.9, y, _fa(header), fontsize=10.5, fontproperties=font_bold,
                 ha='right', transform=ax.transAxes)
        y -= LINE_H * 1.4

        if not triggered:
            ax.text(0.87, y, _fa("همه‌ی نواحی در محدوده‌ی نرمال بودن."), fontsize=8.5,
                     fontproperties=font_reg, color='#00A876', ha='right', transform=ax.transAxes)
            y -= LINE_H
        else:
            for a, bad_min, pct in triggered:
                line = f"- {AREA_FA[a]}: {bad_min:.0f} دقیقه ({pct:.0f}٪ از زمان امروز)"
                ax.text(0.87, y, _fa(line), fontsize=9, fontproperties=font_bold,
                         color=AREA_COLOR[a], ha='right', transform=ax.transAxes)
                y -= LINE_H
                for wline in _wrap_fa(RECOMMENDATIONS[a]):
                    ax.text(0.84, y, _fa(wline), fontsize=8, fontproperties=font_reg,
                             color='#333333', ha='right', transform=ax.transAxes)
                    y -= LINE_H * 0.85
                y -= LINE_H * 0.3

        y -= LINE_H * 0.6

    if fig is not None:
        pages.append(fig)
    return pages


def generate_pdf_bytes(doctor_name: str, frame_rows) -> Optional[bytes]:
    """PDF رو توی حافظه می‌سازه (نه فایل روی دیسک) و بایت‌هاش رو برمی‌گردونه —
    برای سرور که نباید فایل موقت جایی ول کنه"""
    hist = _collect_history(frame_rows)
    if hist is None:
        return None

    font_reg = _fa_font(bold=False)
    font_bold = _fa_font(bold=True) or font_reg

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        chart_fig = _build_charts_page(doctor_name, hist, font_reg, font_bold)
        pdf.savefig(chart_fig)
        plt.close(chart_fig)
        for page_fig in _build_daily_pages(doctor_name, hist, font_reg, font_bold):
            pdf.savefig(page_fig)
            plt.close(page_fig)
    buf.seek(0)
    return buf.getvalue()
