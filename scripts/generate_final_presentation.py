import os
import sys
import shutil
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
OUTPUT_PPTX_DOCS = os.path.join(DOCS_DIR, "Campus_Connect_ERP_Presentation_Final.pptx")
OUTPUT_PDF_DOCS = os.path.join(DOCS_DIR, "Campus_Connect_ERP_Presentation_Final.pdf")
OUTPUT_PPTX_ROOT = os.path.join(REPO_ROOT, "Campus_Connect_ERP_Presentation_Final.pptx")
OUTPUT_PDF_ROOT = os.path.join(REPO_ROOT, "Campus_Connect_ERP_Presentation_Final.pdf")

# Palette constants: Premium Navy, White, Restrained Cyan Accents
NAVY_DEEP = RGBColor(15, 23, 42)       # #0f172a Deep Academic Navy
NAVY_CARD = RGBColor(30, 41, 59)       # #1e293b Slate 800 Card
WHITE = RGBColor(255, 255, 255)        # Pure White
PAGE_BG = RGBColor(248, 250, 252)      # #f8fafc Slate 50 Neutral Canvas
BORDER_SUBTLE = RGBColor(226, 232, 240)# #e2e8f0 Slate 200 Border
BORDER_DARK = RGBColor(51, 65, 85)     # #334155 Dark Border

# Accent Colors
CYAN_BRIGHT = RGBColor(6, 182, 212)    # #06b6d4 Electric Cyan
CYAN_PRIMARY = RGBColor(2, 132, 199)   # #0284c7 Vivid Sky/Cyan
CYAN_DEEP = RGBColor(8, 145, 178)      # #0891b2 Academic Teal/Cyan
EMERALD = RGBColor(16, 185, 129)       # #10b981 Emerald
CORAL = RGBColor(220, 38, 38)          # #dc2626 Coral Red

# Text Colors
TEXT_DARK = RGBColor(15, 23, 42)       # #0f172a Deep Slate Text
TEXT_BODY = RGBColor(51, 65, 85)       # #334155 Slate 700 Body Text
TEXT_MUTED = RGBColor(100, 116, 139)   # #64748b Slate 500 Subtitle/Caption
TEXT_LIGHT = RGBColor(241, 245, 249)   # #f1f5f9 Crisp Light Heading
TEXT_DIM = RGBColor(148, 163, 184)     # #94a3b8 Slate 400

FONT_FAMILY = "Segoe UI"

def set_slide_background(slide, color):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    return bg

def add_header(slide, title_text, category_text="CAMPUS CONNECT ERP • SITCOE", slide_num=1, is_dark=False):
    # Header bar container
    header_box = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.05)
    )
    header_box.fill.solid()
    header_box.fill.fore_color.rgb = NAVY_CARD if is_dark else WHITE
    header_box.line.color.rgb = BORDER_DARK if is_dark else BORDER_SUBTLE
    header_box.line.width = Pt(1)

    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.10)
    tf.margin_right = Inches(0.25)
    tf.margin_bottom = Inches(0.05)
    
    # Category Pill
    p0 = tf.paragraphs[0]
    p0.text = category_text.upper()
    p0.font.name = FONT_FAMILY
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = CYAN_BRIGHT if is_dark else CYAN_DEEP

    # Slide Title (28 pt bold)
    p1 = tf.add_paragraph()
    p1.text = title_text
    p1.font.name = FONT_FAMILY
    p1.font.size = Pt(28)
    p1.font.bold = True
    p1.font.color.rgb = WHITE if is_dark else TEXT_DARK

    # Slide number badge on right
    num_box = slide.shapes.add_textbox(Inches(10.5), Inches(0.55), Inches(1.8), Inches(0.45))
    ntf = num_box.text_frame
    ntf.word_wrap = False
    np = ntf.paragraphs[0]
    np.alignment = PP_ALIGN.RIGHT
    np.text = f"Slide {slide_num} of 7"
    np.font.name = FONT_FAMILY
    np.font.size = Pt(13)
    np.font.bold = True
    np.font.color.rgb = CYAN_BRIGHT if is_dark else CYAN_PRIMARY

def add_footer(slide, slide_num, is_dark=False):
    ft = slide.shapes.add_textbox(Inches(0.8), Inches(7.05), Inches(11.733), Inches(0.35))
    ftf = ft.text_frame
    p = ftf.paragraphs[0]
    p.text = "Campus Connect ERP • Sharad Institute of Technology College of Engineering (SITCOE) • Demonstration Test Environment"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_DIM if is_dark else TEXT_MUTED

def add_image_card(slide, img_path, left, top, width, caption_text, badge_text=None, is_dark=False):
    """Embeds an image inside a mathematically proportioned card frame with zero overflow."""
    img_pad = Inches(0.08)
    img_w = width - (img_pad * 2)
    # 16:10 screenshot ratio (1440x900)
    img_h = img_w * 0.625
    cap_h = Inches(0.52) if badge_text else Inches(0.34)
    total_h = img_h + cap_h + (img_pad * 2)

    # Outer frame
    frame = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, total_h)
    frame.fill.solid()
    frame.fill.fore_color.rgb = NAVY_CARD if is_dark else WHITE
    frame.line.color.rgb = BORDER_DARK if is_dark else BORDER_SUBTLE
    frame.line.width = Pt(1)

    # Place image
    if os.path.exists(img_path):
        slide.shapes.add_picture(
            img_path, left + img_pad, top + img_pad, width=img_w, height=img_h
        )

    # Caption text frame
    cb = slide.shapes.add_textbox(
        left + Inches(0.10), top + img_h + img_pad, width - Inches(0.20), cap_h
    )
    cbtf = cb.text_frame
    cbtf.word_wrap = True
    cbtf.margin_top = Inches(0.03)
    cbtf.margin_bottom = Inches(0.02)
    cbtf.margin_left = Inches(0.02)
    cbtf.margin_right = Inches(0.02)

    p = cbtf.paragraphs[0]
    p.text = caption_text
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10.5)
    p.font.bold = True
    p.font.color.rgb = WHITE if is_dark else TEXT_DARK

    if badge_text:
        p2 = cbtf.add_paragraph()
        p2.text = badge_text
        p2.font.name = FONT_FAMILY
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = CYAN_BRIGHT if is_dark else CYAN_DEEP

    return total_h

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Professional Cover (Theme: Deep Navy & Electric Cyan)
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide1, NAVY_DEEP)

    # Top Cyan Accent Band
    stripe = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = CYAN_BRIGHT
    stripe.line.fill.background()

    # Left Section: Typography & Attribution (Width: 6.8 in)
    tb_left = slide1.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(6.6), Inches(5.8))
    tf1 = tb_left.text_frame
    tf1.word_wrap = True

    # Institution Pill
    p = tf1.paragraphs[0]
    p.text = "🏛️ SHARAD INSTITUTE OF TECHNOLOGY COLLEGE OF ENGINEERING"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(4)

    # Department
    p = tf1.add_paragraph()
    p.text = "Department of Computer Science & Engineering • Academic Year 2025–26"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.color.rgb = TEXT_DIM
    p.space_after = Pt(24)

    # Title: 36 pt Bold
    p = tf1.add_paragraph()
    p.text = "Campus Connect ERP"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.space_after = Pt(6)

    # Subtitle: 20 pt Semi-bold Cyan
    p = tf1.add_paragraph()
    p.text = "Integrated Campus Management System"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(18)

    # Concise Viva Abstract (approx 25 words)
    p = tf1.add_paragraph()
    p.text = "A centralized, role-based college portal for real-time attendance roll-calls, 4-tier examination marks entry, automated grade calculation, and coursework management."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(14)
    p.font.color.rgb = RGBColor(203, 213, 225)
    p.space_after = Pt(24)

    # Project Info Box
    info_box = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.7), Inches(6.5), Inches(1.85))
    info_box.fill.solid()
    info_box.fill.fore_color.rgb = NAVY_CARD
    info_box.line.color.rgb = BORDER_DARK
    info_box.line.width = Pt(1)

    ib_tf = info_box.text_frame
    ib_tf.word_wrap = True
    ib_tf.margin_left = Inches(0.2)
    ib_tf.margin_top = Inches(0.12)

    p = ib_tf.paragraphs[0]
    p.text = "PROJECT OVERVIEW & TECHNOLOGY STACK"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(4)

    p = ib_tf.add_paragraph()
    p.text = "• Core Technologies: Python 3.11 • Flask Web Framework • PostgreSQL • SQLAlchemy 2.0 ORM\n• Developer Attribution: Ayan Mulani (Project Lead) & Project Team | SITCOE Yadrav\n• GitHub Repository: https://github.com/ayanmulani4867-cyber/Campus-mini2"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.color.rgb = TEXT_LIGHT

    # Right Section: Real Dashboard Screenshot Frame
    hero_frame = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.7), Inches(1.1), Inches(4.85), Inches(5.45))
    hero_frame.fill.solid()
    hero_frame.fill.fore_color.rgb = NAVY_CARD
    hero_frame.line.color.rgb = CYAN_DEEP
    hero_frame.line.width = Pt(1.5)

    hf_tb = slide1.shapes.add_textbox(Inches(7.8), Inches(1.15), Inches(4.65), Inches(0.4))
    hf_p = hf_tb.text_frame.paragraphs[0]
    hf_p.text = "AUTHENTIC SYSTEM DASHBOARD INTERFACE"
    hf_p.font.name = FONT_FAMILY
    hf_p.font.size = Pt(11)
    hf_p.font.bold = True
    hf_p.font.color.rgb = CYAN_BRIGHT

    img2_path = os.path.join(SCREENSHOTS_DIR, "02_admin_dashboard.png")
    if os.path.exists(img2_path):
        slide1.shapes.add_picture(img2_path, Inches(7.85), Inches(1.6), width=Inches(4.55))

    # Metric Badges under hero screenshot
    badge_tb = slide1.shapes.add_textbox(Inches(7.85), Inches(4.85), Inches(4.55), Inches(1.6))
    btf = badge_tb.text_frame
    btf.word_wrap = True
    p = btf.paragraphs[0]
    p.text = "Verified System Architecture:"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.space_after = Pt(3)

    p = btf.add_paragraph()
    p.text = "✔ Multi-Tier Role Governance: Admin, Faculty, and Student\n✔ Live Cloud Database: Relational PostgreSQL Schema\n✔ Demonstration Dataset: Test environment sample records"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.color.rgb = CYAN_BRIGHT

    # Slide 1 Number
    s1_num = slide1.shapes.add_textbox(Inches(11.0), Inches(6.8), Inches(1.5), Inches(0.35))
    s1_p = s1_num.text_frame.paragraphs[0]
    s1_p.alignment = PP_ALIGN.RIGHT
    s1_p.text = "Slide 1 of 7"
    s1_p.font.size = Pt(12)
    s1_p.font.bold = True
    s1_p.font.color.rgb = TEXT_DIM


    # =========================================================================
    # SLIDE 2: Problem Statement and Objectives (Theme: Clean White & Cyan)
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide2, PAGE_BG)
    add_header(slide2, "Problem Statement & Project Objectives", "PROJECT MOTIVATION & SCOPE", 2)
    add_footer(slide2, 2)

    # 2 Column Cards: Left (Problems), Right (Objectives) - 40% less text, spacious & readable!
    # Column 1: Problems Card (Width: 5.7 in)
    p_card = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.7), Inches(5.15))
    p_card.fill.solid()
    p_card.fill.fore_color.rgb = WHITE
    p_card.line.color.rgb = BORDER_SUBTLE
    p_card.line.width = Pt(1)

    ptf = p_card.text_frame
    ptf.word_wrap = True
    ptf.margin_left = Inches(0.35)
    ptf.margin_right = Inches(0.35)
    ptf.margin_top = Inches(0.28)

    p = ptf.paragraphs[0]
    p.text = "🚨 OPERATIONAL CHALLENGES (PROBLEM)"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CORAL
    p.space_after = Pt(20)

    problems = [
        ("Fragmented Academic Records",
         "Student profiles, course lists, and marks reside in disconnected physical registers and spreadsheets, causing data silos and duplication."),
        ("Manual Attendance & Grade Tabulation",
         "Paper-based roll-calls cause administrative delays, calculation errors, and slow identification of students falling below attendance thresholds."),
        ("Absence of Role-Based Workspace Isolation",
         "Unsecured access without strict Role-Based Access Control (RBAC) creates data privacy risks between administrators, faculty, and students.")
    ]

    for title, desc in problems:
        p = ptf.add_paragraph()
        p.text = f"• {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = ptf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(18)

    # Column 2: Objectives Card (Width: 5.7 in)
    o_card = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(5.15))
    o_card.fill.solid()
    o_card.fill.fore_color.rgb = WHITE
    o_card.line.color.rgb = BORDER_SUBTLE
    o_card.line.width = Pt(1)

    otf = o_card.text_frame
    otf.word_wrap = True
    otf.margin_left = Inches(0.35)
    otf.margin_right = Inches(0.35)
    otf.margin_top = Inches(0.28)

    p = otf.paragraphs[0]
    p.text = "🎯 CAMPUS CONNECT ERP (SOLUTION)"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(20)

    objectives = [
        ("Centralized Relational Database",
         "Unified PostgreSQL repository managed via SQLAlchemy 2.0 ORM, integrating students, faculty, departments, and course offerings."),
        ("Automated 4-Tier Evaluation Engine",
         "Structured scoring for CA1 (20), CA2 (20), Mid-Sem (30), and End-Sem (70) with automated SGPA/CGPA grade card generation."),
        ("Strict Role-Based Access Control (RBAC)",
         "Server-side session authentication with token isolation guaranteeing dedicated, secure workspaces for Admins, Faculty, and Students.")
    ]

    for title, desc in objectives:
        p = otf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = otf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(18)


    # =========================================================================
    # SLIDE 3: System Architecture (Theme: Clean White & Cyan Diagram)
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3, PAGE_BG)
    add_header(slide3, "System Architecture & Data Flow Diagram", "TECHNICAL ARCHITECTURE", 3)
    add_footer(slide3, 3)

    # 3-Tier Architecture Flowchart Boxes
    tiers = [
        {
            "tag": "CLIENT LAYER",
            "title": "Web Browser Interface",
            "color": CYAN_PRIMARY,
            "bullets": [
                "HTML5 Responsive Layouts",
                "Vanilla CSS3 Design System",
                "Vanilla JavaScript (ES6 Fetch)",
                "Multi-Tab Session Token Isolation"
            ]
        },
        {
            "tag": "APPLICATION LAYER",
            "title": "Python Flask REST Backend",
            "color": NAVY_DEEP,
            "bullets": [
                "Python 3.11 Microframework",
                "Modular Blueprints (Auth, Users, Results)",
                "Role-Based Access Decorators (RBAC)",
                "Werkzeug PBKDF2 Password Hashing"
            ]
        },
        {
            "tag": "DATA PERSISTENCE",
            "title": "PostgreSQL Cloud Database",
            "color": EMERALD,
            "bullets": [
                "PostgreSQL Relational DB (Render)",
                "SQLAlchemy 2.0 Declarative ORM",
                "Alembic Schema Version Migrations",
                "Foreign-Key Relational Integrity"
            ]
        }
    ]

    box_w = Inches(3.6)
    gap = Inches(0.46)
    for i, t in enumerate(tiers):
        bx = Inches(0.8) + i * (box_w + gap)
        box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, bx, Inches(1.65), box_w, Inches(2.75))
        box.fill.solid()
        box.fill.fore_color.rgb = WHITE
        box.line.color.rgb = t["color"]
        box.line.width = Pt(1.5)

        # Header Pill inside box
        hbar = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, bx, Inches(1.65), box_w, Inches(0.55))
        hbar.fill.solid()
        hbar.fill.fore_color.rgb = t["color"]
        hbar.line.fill.background()

        h_tb = slide3.shapes.add_textbox(bx, Inches(1.70), box_w, Inches(0.45))
        hp = h_tb.text_frame.paragraphs[0]
        hp.alignment = PP_ALIGN.CENTER
        hp.text = t["tag"]
        hp.font.name = FONT_FAMILY
        hp.font.size = Pt(11)
        hp.font.bold = True
        hp.font.color.rgb = WHITE

        # Content
        c_tb = slide3.shapes.add_textbox(bx + Inches(0.15), Inches(2.30), box_w - Inches(0.30), Inches(2.0))
        ctf = c_tb.text_frame
        ctf.word_wrap = True

        p = ctf.paragraphs[0]
        p.text = t["title"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(8)

        for bullet in t["bullets"]:
            p = ctf.add_paragraph()
            p.text = f"• {bullet}"
            p.font.name = FONT_FAMILY
            p.font.size = Pt(11.5)
            p.font.color.rgb = TEXT_BODY
            p.space_after = Pt(4)

        # Connector arrow
        if i < 2:
            arr_box = slide3.shapes.add_textbox(bx + box_w, Inches(2.65), gap, Inches(0.6))
            ap = arr_box.text_frame.paragraphs[0]
            ap.alignment = PP_ALIGN.CENTER
            ap.text = "➔"
            ap.font.name = FONT_FAMILY
            ap.font.size = Pt(22)
            ap.font.bold = True
            ap.font.color.rgb = CYAN_PRIMARY

    # Bottom Deployment & DevOps Strip (Top: 4.65 in, Height: 2.1 in)
    dep_card = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.65), Inches(11.733), Inches(2.1))
    dep_card.fill.solid()
    dep_card.fill.fore_color.rgb = WHITE
    dep_card.line.color.rgb = BORDER_SUBTLE
    dep_card.line.width = Pt(1)

    dtf = dep_card.text_frame
    dtf.word_wrap = True
    dtf.margin_left = Inches(0.3)
    dtf.margin_top = Inches(0.2)

    p = dtf.paragraphs[0]
    p.text = "CLOUD HOSTING & DEPLOYMENT PIPELINE"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(10)

    devops_points = [
        ("Render Cloud Web Service", "Automated continuous deployment configured and synchronized with the repository's main branch."),
        ("Gunicorn WSGI Production Server", "Multi-worker Python WSGI server handling concurrent HTTP requests with ProxyFix middleware."),
        ("Zero-Mock Relational Integrity", "Every application route executes authentic SQL queries against PostgreSQL tables; no hardcoded dummy data.")
    ]

    for title, desc in devops_points:
        p = dtf.add_paragraph()
        p.text = f"• {title}: "
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        # Append description inline
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.color.rgb = TEXT_BODY
        p.space_after = Pt(8)


    # =========================================================================
    # SLIDE 4: Dashboard and User Management (Theme: Visual Hero Focus)
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4, PAGE_BG)
    add_header(slide4, "Administrative Dashboard & User Directory", "ADMINISTRATION MODULE", 4)
    add_footer(slide4, 4)

    # Main Visual Focus: Real Application Screenshot (User Directory)
    # Width: 7.4 in, Top: 1.65 in
    img3_path = os.path.join(SCREENSHOTS_DIR, "03_user_directory.png")
    add_image_card(
        slide4, img3_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(7.4),
        caption_text="Figure 1: Campus User Directory — Centralized account governance & profile linking",
        badge_text="Demonstration Dataset: Role filtering (Admin, Faculty, Student) • Department search controls"
    )

    # Right: Short, High-Impact Points Panel (Width: 4.0 in)
    r_card = slide4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(8.5), Inches(1.65), Inches(4.033), Inches(5.2))
    r_card.fill.solid()
    r_card.fill.fore_color.rgb = WHITE
    r_card.line.color.rgb = BORDER_SUBTLE
    r_card.line.width = Pt(1)

    rtf = r_card.text_frame
    rtf.word_wrap = True
    rtf.margin_left = Inches(0.25)
    rtf.margin_right = Inches(0.25)
    rtf.margin_top = Inches(0.25)

    p = rtf.paragraphs[0]
    p.text = "VERIFIED CAPABILITIES"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(16)

    admin_points = [
        ("Unified Member Ledger",
         "Directly couples login credentials with student and faculty academic records to prevent orphan data."),
        ("Multi-Field Search & Filters",
         "Search registered members by name, roll, PRN, or employee ID; filter by department and semester."),
        ("Role-Based Governance",
         "Administrators manage account activation, inspect profiles, and trigger instant student grade cards.")
    ]

    for title, desc in admin_points:
        p = rtf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = rtf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12.5)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(16)

    p = rtf.add_paragraph()
    p.text = "* Screen captured from running ERP using demonstration test dataset."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_MUTED


    # =========================================================================
    # SLIDE 5: Academic Management (Attendance & Examination Results)
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5, PAGE_BG)
    add_header(slide5, "Academic Management: Attendance & Examination Results", "ACADEMIC LIFECYCLE", 5)
    add_footer(slide5, 5)

    # 2 Side-by-Side Screenshots: Left (Student Grade Card), Right (Faculty Marks Entry)
    img5_path = os.path.join(SCREENSHOTS_DIR, "05_student_results.png")
    add_image_card(
        slide5, img5_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(5.6),
        caption_text="Figure 2: Published Student Grade Card with SGPA & CGPA Calculation",
        badge_text="Sample Record: CA1 (18) + CA2 (19) + Mid (26) + End (62) = 125/140 Marks • Grade A • SGPA 8.93"
    )

    img6_path = os.path.join(SCREENSHOTS_DIR, "06_faculty_results_management.png")
    add_image_card(
        slide5, img6_path,
        left=Inches(6.9), top=Inches(1.65), width=Inches(5.6),
        caption_text="Figure 3: Faculty Continuous Assessment Sheet (CA1, CA2, Mid-Sem, End-Sem)",
        badge_text="Workflow: CS601 Software Eng (Div A) • Draft Saving ➔ Review Submission ➔ Approval"
    )

    # Bottom Math & Verification Card (Top: 5.95 in, Height: 0.90 in)
    bot_card = slide5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(5.95), Inches(11.733), Inches(0.90))
    bot_card.fill.solid()
    bot_card.fill.fore_color.rgb = WHITE
    bot_card.line.color.rgb = BORDER_SUBTLE
    bot_card.line.width = Pt(1)

    btf = bot_card.text_frame
    btf.word_wrap = True
    btf.margin_left = Inches(0.2)
    btf.margin_top = Inches(0.08)

    p = btf.paragraphs[0]
    p.text = "MATHEMATICAL CALCULATION & VERIFIED ASSESSMENT RULES:"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(2)

    p = btf.add_paragraph()
    p.text = "• 4-Tier Assessment Math: CA1 (20) + CA2 (20) + Mid-Sem (30) + End-Sem (70) = 140 Total Maximum Marks. Obtained: 125/140 = 89.29% (Grade A, Passed First Class).\n• Attendance Roll-Call Ledger: Course-wise session tracking (CS601, ML, Software Testing) with automated 75% university eligibility threshold monitoring."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_DARK


    # =========================================================================
    # SLIDE 6: Communication and Campus Services (Theme: Visual Hero Focus)
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide6, PAGE_BG)
    add_header(slide6, "Coursework Lifecycle & Campus Announcements", "COLLABORATION & SERVICES", 6)
    add_footer(slide6, 6)

    # Main Visual Focus: Coursework Assignments Screenshot
    img8_path = os.path.join(SCREENSHOTS_DIR, "08_assignments_management.png")
    add_image_card(
        slide6, img8_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(7.4),
        caption_text="Figure 4: Coursework Assignment Management with submission locking & evaluation queue",
        badge_text="Active Coursework: CS601 'Module 8 Lab Assignment on Concurrency' (10 pts) • 1 Delivered Submission"
    )

    # Right: Short, High-Impact Points Panel (Width: 4.0 in)
    col_card = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(8.5), Inches(1.65), Inches(4.033), Inches(5.2))
    col_card.fill.solid()
    col_card.fill.fore_color.rgb = WHITE
    col_card.line.color.rgb = BORDER_SUBTLE
    col_card.line.width = Pt(1)

    ctf = col_card.text_frame
    ctf.word_wrap = True
    ctf.margin_left = Inches(0.25)
    ctf.margin_right = Inches(0.25)
    ctf.margin_top = Inches(0.25)

    p = ctf.paragraphs[0]
    p.text = "COLLABORATION WORKFLOWS"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(16)

    collab_points = [
        ("Assignment Publishing",
         "Faculty create course assignments with point allocations, division targets, and strict submission deadlines."),
        ("Tamper-Proof Locking",
         "Students upload solutions via their portal; submissions are timestamped and locked against post-deadline editing."),
        ("Zero-Mock Circulars",
         "Official notices and campus events (e.g. Spring Cultural Fest 'Vibrance 2026') served directly from PostgreSQL.")
    ]

    for title, desc in collab_points:
        p = ctf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = ctf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12.5)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(16)

    p = ctf.add_paragraph()
    p.text = "* All modules query genuine database tables in the demonstration environment."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_MUTED


    # =========================================================================
    # SLIDE 7: Conclusion and Future Scope (Theme: Deep Navy & Electric Cyan)
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide7, NAVY_DEEP)

    # Top Cyan Accent Band
    stripe7 = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    stripe7.fill.solid()
    stripe7.fill.fore_color.rgb = CYAN_BRIGHT
    stripe7.line.fill.background()

    add_header(slide7, "Project Outcomes, Roadmap & Conclusion", "PROJECT SYNTHESIS & VIVA SUMMARY", 7, is_dark=True)
    add_footer(slide7, 7, is_dark=True)

    # Left Card: Exactly Three Core Outcomes (Width: 5.7 in)
    ach_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.7), Inches(4.15))
    ach_box.fill.solid()
    ach_box.fill.fore_color.rgb = NAVY_CARD
    ach_box.line.color.rgb = CYAN_DEEP
    ach_box.line.width = Pt(1.5)

    atf = ach_box.text_frame
    atf.word_wrap = True
    atf.margin_left = Inches(0.35)
    atf.margin_right = Inches(0.35)
    atf.margin_top = Inches(0.25)

    p = atf.paragraphs[0]
    p.text = "🏁 THREE CORE PROJECT OUTCOMES"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(16)

    outcomes = [
        ("Unified Academic Operations",
         "Successfully integrated roll-call attendance, 4-tier continuous examination assessment, and official grade card publication into a single platform."),
        ("Strict Role-Based Security",
         "Enforced Role-Based Access Control (RBAC) with session token isolation, providing secure, partitioned workspaces for Administrators, Faculty, and Students."),
        ("Production Relational Architecture",
         "Implemented a robust PostgreSQL schema via SQLAlchemy 2.0 ORM with complete referential integrity and zero reliance on mock/demo data fallbacks.")
    ]

    for title, desc in outcomes:
        p = atf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = WHITE
        
        p = atf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12.5)
        p.font.color.rgb = TEXT_DIM
        p.space_after = Pt(14)

    # Right Card: Exactly Two Future Improvements (Width: 5.7 in)
    scope_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(4.15))
    scope_box.fill.solid()
    scope_box.fill.fore_color.rgb = NAVY_CARD
    scope_box.line.color.rgb = BORDER_DARK
    scope_box.line.width = Pt(1.5)

    stf = scope_box.text_frame
    stf.word_wrap = True
    stf.margin_left = Inches(0.35)
    stf.margin_right = Inches(0.35)
    stf.margin_top = Inches(0.25)

    p = stf.paragraphs[0]
    p.text = "🚀 TWO PLANNED FUTURE ENHANCEMENTS"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(16)

    improvements = [
        ("Automated Parent SMS Alerts (Planned)",
         "Integrate an SMS gateway (Twilio / Fast2SMS) to automatically alert parents and students when attendance drops below the 75% university eligibility threshold."),
        ("Accreditation & Analytics Reporting (Planned)",
         "Build graphical department-wise analytics and automated PDF/Excel report exports for NAAC and NIRF institutional accreditation reviews.")
    ]

    for title, desc in improvements:
        p = stf.add_paragraph()
        p.text = f"★ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = WHITE
        
        p = stf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12.5)
        p.font.color.rgb = TEXT_DIM
        p.space_after = Pt(20)

    # Bottom Attribution Banner & Polished Thank You
    ab = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(5.95), Inches(11.733), Inches(0.95))
    ab.fill.solid()
    ab.fill.fore_color.rgb = RGBColor(11, 19, 43)
    ab.line.color.rgb = CYAN_DEEP
    ab.line.width = Pt(1)

    ab_tf = ab.text_frame
    ab_tf.word_wrap = True
    ab_tf.margin_left = Inches(0.25)
    ab_tf.margin_top = Inches(0.14)

    p = ab_tf.paragraphs[0]
    p.text = "CAMPUS CONNECT ERP • SITCOE YADRAV • THANK YOU!"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(3)

    p = ab_tf.add_paragraph()
    p.text = "GitHub Repository: https://github.com/ayanmulani4867-cyber/Campus-mini2  •  Open for Viva Questions & Discussion"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Save presentation to docs/Campus_Connect_ERP_Presentation_Final.pptx
    prs.save(OUTPUT_PPTX_DOCS)
    print(f"Saved PPTX to: {OUTPUT_PPTX_DOCS}")

    # Copy to root as well
    shutil.copyfile(OUTPUT_PPTX_DOCS, OUTPUT_PPTX_ROOT)
    print(f"Copied PPTX to: {OUTPUT_PPTX_ROOT}")

    # Export matching PDF using aspose.slides
    try:
        import aspose.slides as slides
        pres_pdf = slides.Presentation(OUTPUT_PPTX_DOCS)
        pres_pdf.save(OUTPUT_PDF_DOCS, slides.export.SaveFormat.PDF)
        print(f"Saved PDF to: {OUTPUT_PDF_DOCS}")
        shutil.copyfile(OUTPUT_PDF_DOCS, OUTPUT_PDF_ROOT)
        print(f"Copied PDF to: {OUTPUT_PDF_ROOT}")
    except Exception as e:
        print(f"PDF export error: {e}")

if __name__ == "__main__":
    build_presentation()
