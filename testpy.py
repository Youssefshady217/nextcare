import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
st.set_page_config(page_title="صيدلية د/ نادر", layout="centered")

def reshape_arabic(text):
    return get_display(arabic_reshaper.reshape(str(text)))

# تسجيل الدخول
VALID_USERNAME = "romany"
VALID_PASSWORD = "1111"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")

    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        login = st.form_submit_button("دخول")

        if login:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.success("✅ تم تسجيل الدخول بنجاح")
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# عنوان التطبيق
st.title("د/نادر نبيل فهمى")


def fix_arabic(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))

uploaded_file = st.file_uploader("📤 ارفع ملف PDF", type=["pdf"])

if uploaded_file:
    # ------------------ قراءة النصوص (البيانات الأساسية) ------------------
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")

    all_lines = []
    for page in doc:
        text = page.get_text("text")
        all_lines.extend(text.split("\n"))

    client_name = ""
    main_date = ""
    approval_no = ""

    for idx, line in enumerate(all_lines):
        if idx == 1:   # رقم الموافقة
            approval_no = line.strip()
        elif idx == 7: # اسم المؤمن
            client_name = line.strip()
        elif idx == 26: # التاريخ
            main_date = line.replace("ﺗﺎﺭﻳﺦ ﺍﻟﺪﺧﻮﻝ", "").strip()

    # ------------------ قراءة أول جدول فقط ------------------
    table_data = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                first_table = tables[0]  # أول جدول
                for row in first_table:
                    fixed_row = [fix_arabic(cell) for cell in row]
                    table_data.append(fixed_row)
                break  # نوقف بعد أول جدول

    df = None
    if table_data:
        df = pd.DataFrame(table_data)
        df.columns = df.iloc[0]
        df = df.drop(0).reset_index(drop=True)

        # تنظيف أسماء الأعمدة
        df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
        # rename الأعمدة
        df = df.rename(columns={
            "ﺣﺼﺔ ﺍﻟﻤﺮﻳﺾ": "حصة المريض",
            "ﺳﻌﺮ ﺍﻟﻮﺣﺪﺓ": "سعر الوحدة",
            "ﺍﻟﻜﻤﻴﺔ ﺍﻟﻤﻮﺍﻓﻖ ﻋﻠﻴﻬﺎ": "الكمية الموافق عليها",
            "ﺇﺳﻢ ﺍﻟﺨﺪﻣﺔ": "اسم الدواء",
        })
        # تحويل الأعمدة لأرقام (عشان الضرب يشتغل)
        df["الكمية الموافق عليها"] = pd.to_numeric(df["الكمية الموافق عليها"], errors="coerce").fillna(0)
        df["سعر الوحدة"] = pd.to_numeric(df["سعر الوحدة"], errors="coerce").fillna(0)

        # حساب حصة المريض = الكمية × سعر الوحدة
        df["سعر الكمية"] = df["الكمية الموافق عليها"] * df["سعر الوحدة"]
        df = df[[
            "اسم الدواء",
            "الكمية الموافق عليها",
            "سعر الوحدة",
            "سعر الكمية"
        ]]
        df = df[
            (df["اسم الدواء"].astype(str).str.strip() != "") &
            ((df["الكمية الموافق عليها"] != 0) | (df["سعر الوحدة"] != 0))
        ]

        

        st.subheader("📌 الجدول المستخرج")
        st.dataframe(df, use_container_width=True)

    # ------------------ إنشاء PDF ------------------
    if st.button("📄 توليد إيصال PDF") and df is not None:
        class PDF(FPDF):
            def header(self):
                pdf.add_font("Amiri", "", "Amiri-Regular.ttf", uni=True)
                self.add_font("Amiri", "B", "Amiri-Bold.ttf", uni=True)
                self.set_fill_color(230, 230, 230)
                self.image("logo.png", x=10, y=8, w=20)
                self.set_font("Amiri", "B", 14)
                self.cell(0, 10, fix_arabic("صيدلية د/ نادر نبيل فهمى"), ln=1, align="C")
                self.set_font("Amiri", "", 11)
                self.cell(0, 10, fix_arabic("م.ض: 01-40-181-00591-5"), ln=1, align="C")
                self.cell(0, 10, fix_arabic("س.ت: 94294"), ln=1, align="C")
                self.set_font("Amiri", "", 10)
                self.cell(0, 10, fix_arabic("العنوان: اسيوط - شركه فريال - شارع الامام علي"), ln=1, align="C")
                self.cell(0, 10, fix_arabic("تليفون: 01211136366"), ln=1, align="C")
                self.ln(5)
                try:
                    self.image("logo.png", 10, 8, 20)
                except:
                    pass

            def footer(self):
                self.set_y(-15)
                self.set_font("Amiri", "", 10)
                self.cell(0, 10, fix_arabic(f"صفحة {self.page_no()}"), align="C")

        pdf = PDF()
        pdf.add_font("Amiri", "", "Amiri-Regular.ttf", uni=True)
        pdf.add_font("Amiri", "B", "Amiri-Bold.ttf", uni=True)
        pdf.add_page()
        pdf.set_font("Amiri", "", 14)

        # بيانات العميل
        pdf.cell(0, 10, fix_arabic(f"رقم الموافقة: {approval_no}"), ln=1, align="R")
        pdf.cell(0, 10, fix_arabic(f"اسم المؤمن: {client_name}"), ln=1, align="R")
        pdf.cell(0, 10, fix_arabic(f"التاريخ: {main_date}"), ln=1, align="R")
        pdf.ln(5)

        # جدول الأدوية
        col_widths = [80, 35, 35, 35, 30, 30]  # 🔥 اسم الدواء أكبر
        headers = list(df.columns)

        # رؤوس الجدول بخلفية رمادي
        pdf.set_fill_color(220, 220, 220)
        pdf.set_font("Amiri", "B", 12)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 12, fix_arabic(header), border=1, align="C", fill=True)
        pdf.ln()

        # الصفوف
        pdf.set_font("Amiri", "B", 12)
        pdf.set_fill_color(255, 255, 255)  # باقي الجدول أبيض
        for _, row in df.iterrows():
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            # 🟢 اسم الدواء (multi_cell)
            pdf.multi_cell(col_widths[0], 10, fix_arabic(str(row[headers[0]])), border=1, align="R")
            # نرجع مكان المؤشر لبداية السطر + بعد أول عمود
            x_after_name = x_start + col_widths[0]
            y_end_name = pdf.get_y()
            row_height = y_end_name - y_start

            pdf.set_xy(x_after_name, y_start)

            # 🟢 باقي الأعمدة بنفس ارتفاع الصف
            for i in range(1, len(headers)):
                pdf.cell(col_widths[i], row_height, fix_arabic(str(row[headers[i]])), border=1, align="C")

            # ننقل للمكان تحت الصف بالكامل
            pdf.ln(row_height)
        total = pd.to_numeric(df["سعر الكمية"], errors="coerce").sum()
        pdf.set_font("Amiri", "B", 12)
        pdf.cell(0, 30, fix_arabic(f"الإجمالي: {round(total, 2)}"), ln=1, align="R")

        

        # إخراج PDF
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode("latin-1")
        else:
            pdf_bytes = pdf_output


        st.download_button(
            label="⬇️ تحميل إيصال PDF",
            data=pdf_bytes,
            file_name="client_receipt.pdf",
            mime="application/pdf"
        )

































       





















