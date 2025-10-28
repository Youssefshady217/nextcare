import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display


def fix_arabic(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))


st.title("📑 استخراج بيانات العميل + أول جدول + إنشاء إيصال PDF")

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
        elif idx == 24: # التاريخ
            main_date = line.replace("ﺍﻟﺘﺎﺭﻳﺦ", "").strip()

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

        keep_cols = [
            "ﺇﺳﻢ ﺍﻟﺨﺪﻣﺔ",          # اسم الدواء
            "ﺍﻟﻜﻤﻴﺔ ﺍﻟﻤﻄﻠﻮﺑﺔ",       # الكمية المطلوبة
            "ﺍﻟﻜﻤﻴﺔ ﺍﻟﻤﻮﺍﻓﻖ\nعليها",  # الكمية الموافق عليها
            "ﺳﻌﺮ ﺍﻟﻮﺣﺪﺓ",            # سعر الوحدة
            "ﺍﻟﺴﻌﺮ ﺍﻟﻤﻮﺍﻓق\nعليه",   # الإجمالي
            "ﺣﺼﺔ ﺍﻟﻤﺮﻳﺾ"             # حصة المريض
        ]
        df = df[[c for c in keep_cols if c in df.columns]]

        rename_map = {
            "ﺇﺳﻢ ﺍﻟﺨﺪﻣﺔ": "اسم الدواء",
            "ﺍﻟﻜﻤﻴﺔ ﺍﻟﻤﻄﻠﻮﺑﺔ": "الكمية المطلوبة",
            "ﺍﻟﻜﻤﻴﺔ ﺍﻟﻤﻮﺍﻓﻖ\nعليها": "الكمية الموافق عليها",
            "ﺳﻌﺮ ﺍﻟﻮﺣﺪﺓ": "سعر الوحدة",
            "ﺍﻟﺴﻌﺮ ﺍﻟﻤﻮﺍﻓق\nعليه": "الإجمالي",
            "ﺣﺼﺔ ﺍﻟﻤﺮﻳﺾ": "حصة المريض"
        }
        df = df.rename(columns=rename_map)

        st.subheader("📌 الجدول المستخرج")
        st.dataframe(df, use_container_width=True)

    # ------------------ إنشاء PDF ------------------
    if st.button("📄 توليد إيصال PDF") and df is not None:
        class PDF(FPDF):
            def header(self):
                try:
                    self.image("logo.png", 10, 8, 20)
                except:
                    pass
                self.set_font("Amiri", "", 16)
                self.cell(0, 10, fix_arabic("إيصال بيانات العميل"), ln=1, align="C")
                self.ln(10)

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
        

        # إخراج PDF
        pdf_buffer = BytesIO()
        pdf.output(pdf_buffer)
        pdf_buffer.seek(0)

        st.download_button(
            label="⬇️ تحميل إيصال PDF",
            data=pdf_buffer,
            file_name="client_receipt.pdf",
            mime="application/pdf"
        )
































       


