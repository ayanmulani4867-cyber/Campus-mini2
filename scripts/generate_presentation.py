import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
OUTPUT_PPTX = os.path.join(REPO_ROOT, "docs", "Campus_Connect_ERP_Presentation.pptx")

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
        MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.1)
    )
    header_box.fill.solid()
    header_box.fill.fore_color.rgb = NAVY_CARD if is_dark else WHITE
    header_box.line.color.rgb = BORDER_DARK if is_dark else BORDER_SUBTLE
    header_box.line.width = Pt(1)

    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.12)
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
    ft = slide.shapes.add_textbox(Inches(0.8), Inches(7.0), Inches(11.733), Inches(0.35))
    ftf = ft.text_frame
    p = ftf.paragraphs[0]
    p.text = "Campus Connect ERP • Sharad Institute of Technology College of Engineering (SITCOE) • Live PostgreSQL Production System"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10.5)
    p.font.color.rgb = TEXT_DIM if is_dark else TEXT_MUTED

def add_image_card(slide, img_path, left, top, width, caption_text, badge_text=None, is_dark=False):
    """Embeds an image inside a mathematically proportioned card frame with zero overflow."""
    img_pad = Inches(0.08)
    img_w = width - (img_pad * 2)
    # 16:10 screenshot ratio (1440x900)
    img_h = img_w * 0.625
    cap_h = Inches(0.56) if badge_text else Inches(0.36)
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
    cbtf.margin_top = Inches(0.04)
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
    p.space_after = Pt(22)

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

    # Viva-ready description: 14 pt
    p = tf1.add_paragraph()
    p.text = "A production-grade, centralized web application orchestrating roll-call attendance tracking, 4-tier continuous examination assessment, automated student grade card publication, and role-governed campus administration."
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
    p.text = "PROJECT DOMAIN: Web Applications • Academic ERP Architecture"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(4)

    p = ib_tf.add_paragraph()
    p.text = "• Technology Stack: Python 3.11 • Flask Web Framework • PostgreSQL • SQLAlchemy 2.0 ORM\n• Developer Attribution: Ayan Mulani (Project Lead) & Project Team\n• GitHub Codebase: https://github.com/ayanmulani4867-cyber/Campus-mini2"
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
    hf_p.text = "AUTHENTIC LIVE SYSTEM DASHBOARD"
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
    p.text = "Verified System Capabilities:"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.space_after = Pt(3)

    p = btf.add_paragraph()
    p.text = "✔ Real-Time PostgreSQL Database Connection\n✔ 3 Roles: Administrator, Faculty, Student\n✔ Zero Mock Data: Authentic Academic Records"
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
    add_header(slide2, "Problem Statement & Measurable Objectives", "PROJECT MOTIVATION & SCOPE", 2)
    add_footer(slide2, 2)

    # 2 Column Cards: Left (Problems), Right (Objectives)
    # Column 1: Problems Card (Width: 5.7 in)
    p_card = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.7), Inches(5.15))
    p_card.fill.solid()
    p_card.fill.fore_color.rgb = WHITE
    p_card.line.color.rgb = BORDER_SUBTLE
    p_card.line.width = Pt(1)

    ptf = p_card.text_frame
    ptf.word_wrap = True
    ptf.margin_left = Inches(0.3)
    ptf.margin_right = Inches(0.3)
    ptf.margin_top = Inches(0.22)

    p = ptf.paragraphs[0]
    p.text = "🚨 OPERATIONAL CHALLENGES IN CAMPUS ADMINISTRATION"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CORAL
    p.space_after = Pt(14)

    problems = [
        ("Fragmented Academic Records",
         "Student profiles, course enrollments, and department lists reside in disconnected offline registers and spreadsheets, causing data inconsistency and synchronization bottlenecks."),
        ("Laborious Attendance Tracking",
         "Manual classroom roll-calls require extensive paperwork, leading to delayed computation of attendance percentages and late identification of attendance shortages."),
        ("Disjoint Examination Scoring",
         "Multi-tier assessments (CA1, CA2, Mid-Sem, End-Sem) lack centralized tabulation, resulting in manual calculation errors and delayed publication of official student grade cards."),
        ("Absence of Role-Based Governance",
         "Without strict Role-Based Access Control (RBAC), administrative privileges, faculty grading sheets, and student academic reports are not securely compartmentalized.")
    ]

    for title, desc in problems:
        p = ptf.add_paragraph()
        p.text = f"• {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = ptf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(10)

    # Column 2: Objectives Card (Width: 5.7 in)
    o_card = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(5.15))
    o_card.fill.solid()
    o_card.fill.fore_color.rgb = WHITE
    o_card.line.color.rgb = BORDER_SUBTLE
    o_card.line.width = Pt(1)

    otf = o_card.text_frame
    otf.word_wrap = True
    otf.margin_left = Inches(0.3)
    otf.margin_right = Inches(0.3)
    otf.margin_top = Inches(0.22)

    p = otf.paragraphs[0]
    p.text = "🎯 CAMPUS CONNECT ERP OBJECTIVES & SOLUTIONS"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(14)

    objectives = [
        ("Centralized Relational Database",
         "Establish a unified PostgreSQL database via SQLAlchemy 2.0 ORM, integrating Students, Faculty, Courses, and Departments with zero reliance on placeholder demo data."),
        ("Real-Time Attendance Ledger",
         "Digitize classroom roll-call with live attendance score computation, subject-wise breakdown, and automatic flagging of students falling below the mandatory 75% board threshold."),
        ("Unified 4-Tier Assessment Engine",
         "Equip faculty with structured grading sheets for CA1 (20), CA2 (20), Mid-Sem (30), and End-Sem (70), featuring review submission and automated SGPA/CGPA grade card generation."),
        ("Strict Role-Based Access Control (RBAC)",
         "Enforce token-based session verification and server-side route guards across Administrators, Faculty, and Students to safeguard individual academic records and system security.")
    ]

    for title, desc in objectives:
        p = otf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = otf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(10)


    # =========================================================================
    # SLIDE 3: System Architecture and Technology Stack (Theme: Clean White & Cyan)
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3, PAGE_BG)
    add_header(slide3, "System Architecture & Verified Technology Stack", "TECHNICAL SPECIFICATION & FLOW", 3)
    add_footer(slide3, 3)

    # Top Section: 3-Tier Architecture Flow Visual (Height: 1.65 in)
    tiers = [
        ("01 • PRESENTATION TIER", "Client Browser Interface", "Responsive HTML5, Vanilla CSS3 (Custom Theme), Vanilla JavaScript (ES6 Fetch Client)", CYAN_PRIMARY),
        ("02 • APPLICATION TIER", "Python Flask REST Backend", "Application Factory Pattern, Blueprint Routes (Auth, Users, Attendance, Results), RBAC Decorators", NAVY_DEEP),
        ("03 • PERSISTENCE TIER", "PostgreSQL Cloud Database", "SQLAlchemy 2.0 ORM, Alembic Migrations, Declarative Models, Connection Pooling, Zero Mock Fallback", EMERALD)
    ]

    tier_w = Inches(3.6)
    tier_gap = Inches(0.46)
    for i, (tag, title, desc, color) in enumerate(tiers):
        tx = Inches(0.8) + i * (tier_w + tier_gap)
        t_box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, tx, Inches(1.65), tier_w, Inches(1.65))
        t_box.fill.solid()
        t_box.fill.fore_color.rgb = WHITE
        t_box.line.color.rgb = color
        t_box.line.width = Pt(1.5)

        tb_tf = t_box.text_frame
        tb_tf.word_wrap = True
        tb_tf.margin_left = Inches(0.18)
        tb_tf.margin_top = Inches(0.12)

        p = tb_tf.paragraphs[0]
        p.text = tag
        p.font.name = FONT_FAMILY
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(3)

        p = tb_tf.add_paragraph()
        p.text = title
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(4)

        p = tb_tf.add_paragraph()
        p.text = desc
        p.font.name = FONT_FAMILY
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_BODY

        # Arrow connector between tiers
        if i < 2:
            arr_box = slide3.shapes.add_textbox(tx + tier_w, Inches(2.2), tier_gap, Inches(0.5))
            ap = arr_box.text_frame.paragraphs[0]
            ap.alignment = PP_ALIGN.CENTER
            ap.text = "➔"
            ap.font.name = FONT_FAMILY
            ap.font.size = Pt(20)
            ap.font.bold = True
            ap.font.color.rgb = CYAN_PRIMARY

    # Bottom Section: 4 Verified Tech Cards (Top: 3.55 in, Height: 3.25 in)
    tech_cards = [
        {
            "tag": "FRONTEND STACK",
            "name": "Semantic Web UI",
            "color": CYAN_PRIMARY,
            "bullets": [
                ("HTML5 Semantic UI", "Clean document layout built for accessibility."),
                ("Vanilla CSS3 Tokens", "Slate & navy academic palette; zero framework bloat."),
                ("Vanilla JavaScript (ES6)", "Native fetch API client handling dynamic DOM updates."),
                ("Multi-Tab Isolation", "Session token isolation preventing accidental logouts.")
            ]
        },
        {
            "tag": "BACKEND FRAMEWORK",
            "name": "Python Flask Engine",
            "color": NAVY_DEEP,
            "bullets": [
                ("Python 3.11 Runtime", "High execution speed and modern async support."),
                ("Application Factory", "Modular create_app() design with clean configuration."),
                ("Modular Blueprints", "Separation of concerns: auth, users, attendance, results."),
                ("PBKDF2 Security", "Salted password hashing with Werkzeug security utilities.")
            ]
        },
        {
            "tag": "DATABASE & ORM",
            "name": "PostgreSQL & SQLAlchemy",
            "color": EMERALD,
            "bullets": [
                ("PostgreSQL Database", "Reliable relational cloud storage hosted on Render."),
                ("SQLAlchemy 2.0 ORM", "Declarative schema models with cascade deletion rules."),
                ("Alembic Migrations", "Controlled database schema upgrades and rollback safety."),
                ("Zero Mock Fallback", "Every view directly queries live SQL tables.")
            ]
        },
        {
            "tag": "DEVOPS & DEPLOYMENT",
            "name": "Production Cloud Stack",
            "color": CYAN_DEEP,
            "bullets": [
                ("Render Web Service", "Continuous deployment synced with GitHub main."),
                ("Gunicorn WSGI Server", "Multi-worker WSGI server managing concurrent requests."),
                ("ProxyFix Middleware", "Proper HTTPS reverse-proxy header handling."),
                ("Environment Hygiene", "Isolated configuration using environment variables (.env).")
            ]
        }
    ]

    col_w = Inches(2.75)
    gap = Inches(0.24)
    for i, tc in enumerate(tech_cards):
        cx = Inches(0.8) + i * (col_w + gap)
        c_box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx, Inches(3.55), col_w, Inches(3.25))
        c_box.fill.solid()
        c_box.fill.fore_color.rgb = WHITE
        c_box.line.color.rgb = BORDER_SUBTLE
        c_box.line.width = Pt(1)

        # Top Accent Header Bar
        hbar = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx, Inches(3.55), col_w, Inches(0.55))
        hbar.fill.solid()
        hbar.fill.fore_color.rgb = tc["color"]
        hbar.line.fill.background()

        h_tb = slide3.shapes.add_textbox(cx, Inches(3.6), col_w, Inches(0.45))
        hp = h_tb.text_frame.paragraphs[0]
        hp.alignment = PP_ALIGN.CENTER
        hp.text = tc["tag"]
        hp.font.name = FONT_FAMILY
        hp.font.size = Pt(11)
        hp.font.bold = True
        hp.font.color.rgb = WHITE

        # Body Content
        b_tb = slide3.shapes.add_textbox(cx + Inches(0.12), Inches(4.18), col_w - Inches(0.24), Inches(2.5))
        btf = b_tb.text_frame
        btf.word_wrap = True

        p = btf.paragraphs[0]
        p.text = tc["name"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(6)

        for heading, desc in tc["bullets"]:
            p = btf.add_paragraph()
            p.text = f"• {heading}: {desc}"
            p.font.name = FONT_FAMILY
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_BODY
            p.space_after = Pt(4)


    # =========================================================================
    # SLIDE 4: Dashboard and User Management (Theme: Clean White & Cyan)
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4, PAGE_BG)
    add_header(slide4, "Centralized Administration & Campus User Directory", "CORE MANAGEMENT MODULE", 4)
    add_footer(slide4, 4)

    # Left: Hero Screenshot (User Directory)
    img3_path = os.path.join(SCREENSHOTS_DIR, "03_user_directory.png")
    add_image_card(
        slide4, img3_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(6.3),
        caption_text="Figure 1: Campus User Directory displaying verified SITCOE student & faculty database records",
        badge_text="Live Relational Data: PRN 24101099, 24101005 • Faculty Code FAC-TEST-01 • Computer Science Dept"
    )

    # Relational Database Status Callout below image card
    db_stat = slide4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.3), Inches(6.3), Inches(0.55))
    db_stat.fill.solid()
    db_stat.fill.fore_color.rgb = WHITE
    db_stat.line.color.rgb = BORDER_SUBTLE
    db_stat.line.width = Pt(1)

    dstf = db_stat.text_frame
    dstf.margin_left = Inches(0.15)
    dstf.margin_top = Inches(0.08)
    p = dstf.paragraphs[0]
    p.text = "⚡ Relational Schema Status: 100% Synced • 2 Students • 3 Faculty • 19 Courses • 6 Depts"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10.5)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY

    # Right: Verified Capabilities Card (Width: 5.1 in, Top: 1.65 in, Height: 5.2 in)
    r_card = slide4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.4), Inches(1.65), Inches(5.1), Inches(5.2))
    r_card.fill.solid()
    r_card.fill.fore_color.rgb = WHITE
    r_card.line.color.rgb = BORDER_SUBTLE
    r_card.line.width = Pt(1)

    rtf = r_card.text_frame
    rtf.word_wrap = True
    rtf.margin_left = Inches(0.3)
    rtf.margin_right = Inches(0.3)
    rtf.margin_top = Inches(0.22)

    p = rtf.paragraphs[0]
    p.text = "🏛️ VERIFIED ADMINISTRATIVE CAPABILITIES"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(12)

    admin_features = [
        ("Institutional Health & KPI Metrics",
         "The Admin Dashboard aggregates real-time metrics across SITCOE: Total Enrolled Students (2), Teaching Faculty (3), Active Courses (19), and 6 Engineering Departments with 100% operational status."),
        ("Unified Campus Member Ledger",
         "Directly couples authentication credentials with Student and Faculty academic profiles. Eliminates orphan records and guarantees complete profile referential integrity."),
        ("Multi-Field Full-Text Search",
         "Enables immediate member lookup by Full Name, Roll Number, PRN (e.g. 24101099, 24101005), Employee Code (FAC-TEST-01), or College Email address."),
        ("Departmental Filtering & Role Governance",
         "Filter registered campus members dynamically by Role (Admin, Faculty, Student), Department (Computer Science & Engineering), Semester, Class Division, and Active Status.")
    ]

    for title, desc in admin_features:
        p = rtf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = rtf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(10)


    # =========================================================================
    # SLIDE 5: Academic Management (Attendance & Examination Results)
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5, PAGE_BG)
    add_header(slide5, "Academic Management: Attendance & Examination Scoring", "ACADEMIC WORKFLOWS", 5)
    add_footer(slide5, 5)

    # 2 Side-by-Side Clean Screenshots: Left (Student Grade Card), Right (Faculty Marks Entry)
    # Width: 5.6 in -> img_h: 3.40 in, total_h: ~4.12 in. Top: 1.65 in -> ends at ~5.77 in
    img5_path = os.path.join(SCREENSHOTS_DIR, "05_student_results.png")
    add_image_card(
        slide5, img5_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(5.6),
        caption_text="Figure 2: Official Published Student Grade Card (Automated SGPA & CGPA Calculation)",
        badge_text="Verified Student: Aarav Sharma (PRN 24101099) • SGPA 8.93 (First Class) • Grade A"
    )

    img6_path = os.path.join(SCREENSHOTS_DIR, "06_faculty_results_management.png")
    add_image_card(
        slide5, img6_path,
        left=Inches(6.9), top=Inches(1.65), width=Inches(5.6),
        caption_text="Figure 3: Faculty Continuous Assessment Sheet (CA1, CA2, Mid-Sem, End-Sem)",
        badge_text="Workflow: CS601 Software Eng (Div A) • Marks Entry & Review Submission Console"
    )

    # Bottom Academic Capabilities Strip (Top: 5.95 in, Height: 0.90 in, Width: 11.7 in)
    bot_card = slide5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(5.95), Inches(11.7), Inches(0.90))
    bot_card.fill.solid()
    bot_card.fill.fore_color.rgb = WHITE
    bot_card.line.color.rgb = BORDER_SUBTLE
    bot_card.line.width = Pt(1)

    btf = bot_card.text_frame
    btf.word_wrap = True
    btf.margin_left = Inches(0.2)
    btf.margin_top = Inches(0.08)

    p = btf.paragraphs[0]
    p.text = "VERIFIED ACADEMIC EVALUATION & ATTENDANCE WORKFLOW:"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(2)

    p = btf.add_paragraph()
    p.text = "• 4-Tier Assessment System: Faculty input raw scores for CA1 (20 pts), CA2 (20 pts), Mid-Sem (30 pts), and End-Sem (70 pts) with automated total calculation (125/100 scale).\n• Attendance Roll-Call Ledger: Course-wise session tracking (CS601, 23CS3601, 23CS3602) with automated 75% board threshold compliance monitoring.\n• Administrative Approval Workflow: Instructors save drafts and submit for review; Administrators approve and publish official, tamper-proof student grade reports."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_DARK


    # =========================================================================
    # SLIDE 6: Communication and Campus Services (Theme: Clean White & Cyan)
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide6, PAGE_BG)
    add_header(slide6, "Coursework Lifecycle & Campus Announcements", "COLLABORATION & SERVICES", 6)
    add_footer(slide6, 6)

    # Left: Real Screenshot (Coursework Assignments & Submissions)
    # Width: 6.1 in -> img_h: 3.71 in, total_h: ~4.39 in. Top: 1.65 in -> ends at ~6.04 in
    img8_path = os.path.join(SCREENSHOTS_DIR, "08_assignments_management.png")
    add_image_card(
        slide6, img8_path,
        left=Inches(0.8), top=Inches(1.65), width=Inches(6.1),
        caption_text="Figure 4: Coursework Assignment Management with submission locking & evaluation queue",
        badge_text="Active Coursework: CS601 'Module 8 Lab Assignment on Concurrency' • 10 pts • 1 Delivered"
    )

    # Notice snippet indicator below
    n_box = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.20), Inches(6.1), Inches(0.65))
    n_box.fill.solid()
    n_box.fill.fore_color.rgb = WHITE
    n_box.line.color.rgb = BORDER_SUBTLE
    n_box.line.width = Pt(1)

    np_tf = n_box.text_frame
    np_tf.margin_left = Inches(0.15)
    np_tf.margin_top = Inches(0.08)
    p = np_tf.paragraphs[0]
    p.text = "📢 Campus Notice Board & Cultural Events: Operates directly with PostgreSQL (zero mock data). Active event: Spring Cultural Fest 'Vibrance 2026'."
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10.5)
    p.font.color.rgb = TEXT_DARK

    # Right: Verified Capabilities Card (Width: 5.3 in, Top: 1.65 in, Height: 5.2 in)
    col_card = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.2), Inches(1.65), Inches(5.3), Inches(5.2))
    col_card.fill.solid()
    col_card.fill.fore_color.rgb = WHITE
    col_card.line.color.rgb = BORDER_SUBTLE
    col_card.line.width = Pt(1)

    ctf = col_card.text_frame
    ctf.word_wrap = True
    ctf.margin_left = Inches(0.3)
    ctf.margin_right = Inches(0.3)
    ctf.margin_top = Inches(0.22)

    p = ctf.paragraphs[0]
    p.text = "📁 VERIFIED COLLABORATION & CAMPUS SERVICES"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_PRIMARY
    p.space_after = Pt(14)

    collab_features = [
        ("Coursework Assignment Publishing",
         "Faculty can create course-specific assignments (e.g. CS601 'Module 8 Lab Assignment on Concurrency') with point allocations (10 pts), assigned divisions, and strict deadlines."),
        ("Tamper-Proof Submission Locking",
         "Students submit solutions directly through their portal. Once submitted, submissions are timestamped and locked against further modification to ensure academic integrity."),
        ("Faculty Evaluation Queue",
         "Real-time coursework ledger displays delivered submissions (1 Completed, 1 Awaiting Evaluation), providing instructors with direct review and grading interfaces."),
        ("Zero Mock Data Notice Bulletin",
         "The campus notice board operates directly against the PostgreSQL database with zero placeholder fallbacks. Handles official announcements across Academic, Examination, and Cultural categories.")
    ]

    for title, desc in collab_features:
        p = ctf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = TEXT_DARK
        
        p = ctf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_BODY
        p.space_after = Pt(10)


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

    add_header(slide7, "Project Conclusion, Impact & Future Roadmap", "PROJECT SYNTHESIS & VIVA SUMMARY", 7, is_dark=True)
    add_footer(slide7, 7, is_dark=True)

    # 2 Big Cards: Left (Verified Deliverables), Right (Future Roadmap)
    # Left Card: Achievements & Value (Width: 5.7 in)
    ach_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.7), Inches(4.25))
    ach_box.fill.solid()
    ach_box.fill.fore_color.rgb = NAVY_CARD
    ach_box.line.color.rgb = CYAN_DEEP
    ach_box.line.width = Pt(1.5)

    atf = ach_box.text_frame
    atf.word_wrap = True
    atf.margin_left = Inches(0.3)
    atf.margin_right = Inches(0.3)
    atf.margin_top = Inches(0.22)

    p = atf.paragraphs[0]
    p.text = "🏁 VERIFIED CAPABILITIES & PRACTICAL VALUE"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(12)

    achievements = [
        ("Fully Operational Enterprise System",
         "Successfully delivered a working college ERP for SITCOE, verified on live PostgreSQL cloud storage with complete schema referential integrity."),
        ("End-to-End Academic Digitization",
         "Unified attendance roll-call tracking, 4-tier continuous assessment (CA1, CA2, Mid-Sem, End-Sem), and official published grade cards within a single platform."),
        ("Zero Demo/Mock Fallbacks",
         "Strict data integrity across all modules—every view directly queries authentic database tables with legitimate empty states."),
        ("Multi-Role Security & Isolation",
         "Robust Role-Based Access Control (RBAC) with token session isolation, preventing multi-tab session conflicts between Admin, Faculty, and Student workspaces.")
    ]

    for title, desc in achievements:
        p = atf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = WHITE
        
        p = atf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DIM
        p.space_after = Pt(8)

    # Right Card: Realistic Future Roadmap (Width: 5.7 in)
    scope_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(4.25))
    scope_box.fill.solid()
    scope_box.fill.fore_color.rgb = NAVY_CARD
    scope_box.line.color.rgb = BORDER_DARK
    scope_box.line.width = Pt(1.5)

    stf = scope_box.text_frame
    stf.word_wrap = True
    stf.margin_left = Inches(0.3)
    stf.margin_right = Inches(0.3)
    stf.margin_top = Inches(0.22)

    p = stf.paragraphs[0]
    p.text = "🚀 FUTURE ROADMAP & PLANNED ENHANCEMENTS"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(12)

    future_scope = [
        ("Automated Parent SMS Alerts (Planned)",
         "Integrate SMS gateways (Twilio / Fast2SMS) to automatically alert parents and students when overall attendance falls below the mandatory 75% threshold."),
        ("Web Push Notifications (Planned)",
         "Implement Service Worker push notifications for urgent circulars, impending assignment deadlines, and newly published examination grade cards."),
        ("Academic Analytics & NIRF Reports (Planned)",
         "Build graphical department-wise analytics, batch pass-rate distributions, and automated CSV/PDF report generators for NIRF and NAAC accreditation reviews."),
        ("Native Mobile Companion App (Planned)",
         "Develop a cross-platform mobile client (Flutter / React Native) leveraging the existing secure REST API endpoints for convenient student access on mobile devices.")
    ]

    for title, desc in future_scope:
        p = stf.add_paragraph()
        p.text = f"★ {title}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = WHITE
        
        p = stf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DIM
        p.space_after = Pt(8)

    # Bottom Attribution Banner & Thank You (Top: 6.05 in, Height: 0.85 in)
    ab = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.05), Inches(11.7), Inches(0.85))
    ab.fill.solid()
    ab.fill.fore_color.rgb = RGBColor(11, 19, 43)
    ab.line.color.rgb = CYAN_DEEP
    ab.line.width = Pt(1)

    ab_tf = ab.text_frame
    ab_tf.word_wrap = True
    ab_tf.margin_left = Inches(0.25)
    ab_tf.margin_top = Inches(0.12)

    p = ab_tf.paragraphs[0]
    p.text = "CAMPUS CONNECT ERP • SITCOE YADRAV • THANK YOU!"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = CYAN_BRIGHT
    p.space_after = Pt(2)

    p = ab_tf.add_paragraph()
    p.text = "Repository: https://github.com/ayanmulani4867-cyber/Campus-mini2  •  Open for Viva Questions & Discussion"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Save presentation
    prs.save(OUTPUT_PPTX)
    print(f"Successfully generated presentation with {len(prs.slides)} slides at: {OUTPUT_PPTX}")

if __name__ == "__main__":
    build_presentation()
