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

# Palette constants
NAVY_BG = RGBColor(15, 23, 42)        # #0f172a Deep academic dark slate
NAVY_HEADER = RGBColor(30, 41, 59)    # #1e293b
CARD_BG = RGBColor(255, 255, 255)     # #ffffff
PAGE_BG = RGBColor(248, 250, 252)     # #f8fafc
PRIMARY_BLUE = RGBColor(37, 99, 235)  # #2563eb
ROYAL_BLUE = RGBColor(30, 58, 138)    # #1e3a8a
EMERALD = RGBColor(16, 185, 129)      # #10b981
AMBER = RGBColor(217, 119, 6)         # #d97706
BORDER_COLOR = RGBColor(226, 232, 240)# #e2e8f0
TEXT_MAIN = RGBColor(15, 23, 42)      # #0f172a
TEXT_MUTED = RGBColor(100, 116, 139)  # #64748b
TEXT_LIGHT = RGBColor(241, 245, 249)  # #f1f5f9
WHITE = RGBColor(255, 255, 255)

FONT_HEADING = "Segoe UI"
FONT_BODY = "Segoe UI"

def set_slide_background(slide, color):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    return bg

def add_header(slide, title_text, category_text="CAMPUS CONNECT ERP • SITCOE", slide_num=1):
    # Header bar container
    header_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.95))
    header_box.fill.solid()
    header_box.fill.fore_color.rgb = CARD_BG
    header_box.line.color.rgb = BORDER_COLOR
    header_box.line.width = Pt(1)

    # Category Pill / Tag
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.12)
    tf.margin_right = Inches(0.25)
    tf.margin_bottom = Inches(0.05)
    
    p0 = tf.paragraphs[0]
    p0.text = category_text.upper()
    p0.font.name = FONT_HEADING
    p0.font.size = Pt(9.5)
    p0.font.bold = True
    p0.font.color.rgb = PRIMARY_BLUE

    p1 = tf.add_paragraph()
    p1.text = title_text
    p1.font.name = FONT_HEADING
    p1.font.size = Pt(18)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_MAIN

    # Slide number badge on right
    num_box = slide.shapes.add_textbox(Inches(10.5), Inches(0.55), Inches(1.8), Inches(0.4))
    ntf = num_box.text_frame
    ntf.word_wrap = False
    np = ntf.paragraphs[0]
    np.alignment = PP_ALIGN.RIGHT
    np.text = f"Slide {slide_num} of 7"
    np.font.name = FONT_BODY
    np.font.size = Pt(11)
    np.font.bold = True
    np.font.color.rgb = TEXT_MUTED

def add_footer(slide, slide_num):
    ft = slide.shapes.add_textbox(Inches(0.8), Inches(7.1), Inches(11.733), Inches(0.3))
    ftf = ft.text_frame
    p = ftf.paragraphs[0]
    p.text = "Campus Connect ERP • Sharad Institute of Technology College of Engineering, Yadrav (SITCOE) • Live PostgreSQL Production System"
    p.font.name = FONT_BODY
    p.font.size = Pt(9)
    p.font.color.rgb = TEXT_MUTED

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Title Slide (Dark Academic Navy Theme)
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide1, NAVY_BG)

    # Accent Top Stripe
    stripe = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = PRIMARY_BLUE
    stripe.line.fill.background()

    # Left Branding & Title Content Box
    tb_left = slide1.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(6.8), Inches(5.8))
    tf1 = tb_left.text_frame
    tf1.word_wrap = True

    # Institution Pill
    p = tf1.paragraphs[0]
    p.text = "🏛️ SHARAD INSTITUTE OF TECHNOLOGY COLLEGE OF ENGINEERING"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(4)

    # Sub-department
    p = tf1.add_paragraph()
    p.text = "Department of Computer Science & Engineering • Academic Year 2025–26"
    p.font.name = FONT_BODY
    p.font.size = Pt(11)
    p.font.color.rgb = TEXT_LIGHT
    p.space_after = Pt(24)

    # Main Project Title
    p = tf1.add_paragraph()
    p.text = "Campus Connect ERP"
    p.font.name = FONT_HEADING
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.space_after = Pt(6)

    # Subtitle
    p = tf1.add_paragraph()
    p.text = "Integrated College Management & Academic Ledger System"
    p.font.name = FONT_HEADING
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_BLUE
    p.space_after = Pt(18)

    # Overview Description
    p = tf1.add_paragraph()
    p.text = "A production-grade, centralized enterprise portal orchestrating student attendance tracking, 4-tier continuous examination marks entry, automated grade card publication, coursework lifecycle, and role-governed campus administration."
    p.font.name = FONT_BODY
    p.font.size = Pt(12)
    p.font.color.rgb = RGBColor(203, 213, 225)
    p.space_after = Pt(22)

    # Badges Box / Technology Summary
    p = tf1.add_paragraph()
    p.text = "VERIFIED TECHNOLOGY STACK:"
    p.font.name = FONT_HEADING
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = RGBColor(148, 163, 184)
    p.space_after = Pt(6)

    p = tf1.add_paragraph()
    p.text = "• Backend: Python 3.11 • Flask Web Framework • SQLAlchemy 2.0 ORM\n• Database: PostgreSQL Cloud DB • Connection Pooling • Alembic\n• Frontend: Responsive HTML5 • Vanilla CSS3 • Vanilla JavaScript ES6\n• Deployment: Render Cloud Web Service • Gunicorn • ProxyFix Security"
    p.font.name = FONT_BODY
    p.font.size = Pt(10.5)
    p.font.color.rgb = RGBColor(226, 232, 240)
    p.space_after = Pt(20)

    # Repository & Project Info Box
    p = tf1.add_paragraph()
    p.text = "Project Repository: https://github.com/ayanmulani4867-cyber/Campus-mini2\nDeveloper Attribution: Ayan Mulani & Engineering Team | SITCOE Yadrav"
    p.font.name = FONT_BODY
    p.font.size = Pt(9.5)
    p.font.color.rgb = RGBColor(148, 163, 184)

    # Right Showcase: Actual Portal Login & Admin Dashboard Screenshot
    # Screenshot Frame Box
    frame = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.7), Inches(1.0), Inches(4.8), Inches(5.6))
    frame.fill.solid()
    frame.fill.fore_color.rgb = NAVY_HEADER
    frame.line.color.rgb = RGBColor(51, 65, 85)
    frame.line.width = Pt(1.5)

    frame_label = slide1.shapes.add_textbox(Inches(7.8), Inches(1.05), Inches(4.6), Inches(0.4))
    fl_tf = frame_label.text_frame
    fl_p = fl_tf.paragraphs[0]
    fl_p.text = "REAL RUNNING SYSTEM INTERFACE"
    fl_p.font.name = FONT_HEADING
    fl_p.font.size = Pt(9)
    fl_p.font.bold = True
    fl_p.font.color.rgb = PRIMARY_BLUE

    # Insert Real Screenshot 1: 01_login_portal.png
    img1_path = os.path.join(SCREENSHOTS_DIR, "01_login_portal.png")
    if os.path.exists(img1_path):
        slide1.shapes.add_picture(img1_path, Inches(7.85), Inches(1.4), width=Inches(4.5))

    # Real Screenshot 2 snippet: 02_admin_dashboard.png below
    img2_path = os.path.join(SCREENSHOTS_DIR, "02_admin_dashboard.png")
    if os.path.exists(img2_path):
        slide1.shapes.add_picture(img2_path, Inches(7.85), Inches(3.95), width=Inches(4.5))

    # Slide 1 number
    s1_num = slide1.shapes.add_textbox(Inches(11.0), Inches(6.9), Inches(1.5), Inches(0.3))
    s1_ntf = s1_num.text_frame
    s1_np = s1_ntf.paragraphs[0]
    s1_np.alignment = PP_ALIGN.RIGHT
    s1_np.text = "Slide 1 of 7"
    s1_np.font.size = Pt(10)
    s1_np.font.bold = True
    s1_np.font.color.rgb = RGBColor(148, 163, 184)


    # =========================================================================
    # SLIDE 2: Problem Statement and Objectives
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide2, PAGE_BG)
    add_header(slide2, "Problem Statement & Strategic Objectives", "PROJECT FOUNDATION", 2)
    add_footer(slide2, 2)

    # 2 Column Cards: Left (Problems), Right (Objectives)
    # Column 1: Current Challenges (Width: 5.6 Inches)
    card_prob = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.55), Inches(5.7), Inches(5.35))
    card_prob.fill.solid()
    card_prob.fill.fore_color.rgb = CARD_BG
    card_prob.line.color.rgb = BORDER_COLOR
    card_prob.line.width = Pt(1)

    ptf = card_prob.text_frame
    ptf.word_wrap = True
    ptf.margin_left = Inches(0.3)
    ptf.margin_right = Inches(0.3)
    ptf.margin_top = Inches(0.25)

    p = ptf.paragraphs[0]
    p.text = "🚨 ACADEMIC PAIN POINTS & CHALLENGES"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = RGBColor(220, 38, 38)
    p.space_after = Pt(14)

    problems = [
        ("Fragmented Academic Information",
         "Colleges traditionally store student records, enrollment lists, and course schedules across disparate offline registers and unlinked spreadsheets, leading to data synchronization bottlenecks."),
        ("Inefficient Attendance & Result Tracking",
         "Manual attendance logs make real-time roll-call auditing cumbersome. Continuous assessment (CA1, CA2, Mid-Sem, End-Sem) lacks automated total calculation, resulting in delayed grade finalization."),
        ("Manual Notice & Assignment Circulation",
         "Circulating physical circulars and collecting assignment submissions via email causes lost submissions, unverified deadlines, and absence of an auditable evaluation history."),
        ("Lack of Role-Governed Workspace Isolation",
         "Absence of granular Role-Based Access Control (RBAC) creates security hazards where administrative privileges, faculty assessment sheets, and student result cards are not strictly compartmentalized.")
    ]

    for title, desc in problems:
        p = ptf.add_paragraph()
        p.text = f"• {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = ptf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(10)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(10)

    # Column 2: Objectives & Engineering Solutions (Width: 5.7 Inches)
    card_obj = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.55), Inches(5.7), Inches(5.35))
    card_obj.fill.solid()
    card_obj.fill.fore_color.rgb = CARD_BG
    card_obj.line.color.rgb = BORDER_COLOR
    card_obj.line.width = Pt(1)

    otf = card_obj.text_frame
    otf.word_wrap = True
    otf.margin_left = Inches(0.3)
    otf.margin_right = Inches(0.3)
    otf.margin_top = Inches(0.25)

    p = otf.paragraphs[0]
    p.text = "🎯 CORE OBJECTIVES OF CAMPUS CONNECT ERP"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(14)

    objectives = [
        ("Centralized Academic Master Database",
         "Deploy a unified relational PostgreSQL schema managed via SQLAlchemy 2.0 ORM, integrating Students, Faculty, Courses, Departments, and Enrollments with zero demo/mock fallback."),
        ("Continuous 4-Tier Assessment & Grade Generation",
         "Provide faculty with dedicated grading sheets for CA1 (20), CA2 (20), Mid-Sem (30), and End-Sem (70), featuring approval workflows and instant SGPA/CGPA grade card generation."),
        ("Live Attendance Ledger & Eligibility Monitoring",
         "Digitize classroom roll-call with live attendance score computation, subject-wise breakdown, and automatic flagging of students falling below the mandatory 75% board threshold."),
        ("Multi-Tier Role-Based Access Control (RBAC)",
         "Enforce strict server-side session authentication with token isolation across Administrators, Faculty, and Students to guarantee data integrity and individual record privacy.")
    ]

    for title, desc in objectives:
        p = otf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = otf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(10)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(10)


    # =========================================================================
    # SLIDE 3: System Architecture and Technology Stack
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3, PAGE_BG)
    add_header(slide3, "System Architecture & Technology Stack", "TECHNICAL SPECIFICATION", 3)
    add_footer(slide3, 3)

    # 4 Architecture Columns (Width 2.75 each, Gap 0.24)
    layers = [
        {
            "num": "01",
            "layer": "CLIENT INTERFACE",
            "tech": "Frontend Architecture",
            "color": ROYAL_BLUE,
            "items": [
                ("HTML5 Semantic UI", "Accessible, structured document layout tailored for academic dashboards."),
                ("Vanilla CSS3", "Design system with customized slate tokens, CSS variables, zero Tailwind overhead."),
                ("Vanilla JavaScript (ES6)", "Lightweight, modular fetch client handling REST APIs and DOM rendering."),
                ("Multi-Tab Isolation", "Hybrid sessionStorage and localStorage token management preventing logout collisions.")
            ]
        },
        {
            "num": "02",
            "layer": "APPLICATION LAYER",
            "tech": "Flask REST Backend",
            "color": PRIMARY_BLUE,
            "items": [
                ("Python 3.11 + Flask", "Lightweight micro-framework utilizing the Application Factory design pattern."),
                ("Modular Blueprints", "Separation of concerns: auth, users, attendance, results, assignments, notices, events."),
                ("RBAC & Security Decorators", "@login_required & @role_required enforcing strict route authorization."),
                ("Password Security", "Werkzeug PBKDF2 hashing with salted credentials across all accounts.")
            ]
        },
        {
            "num": "03",
            "layer": "DATA PERSISTENCE",
            "tech": "PostgreSQL & SQLAlchemy",
            "color": EMERALD,
            "items": [
                ("PostgreSQL Database", "Relational database hosted on Render Cloud with high reliability."),
                ("SQLAlchemy 2.0 ORM", "Declarative schema models with cascade deletion and relational integrity."),
                ("Alembic Migrations", "Strict schema version control ensuring seamless zero-downtime upgrades."),
                ("Zero Mock Fallback", "All views directly bound to genuine SQL records with honest empty states.")
            ]
        },
        {
            "num": "04",
            "layer": "DEPLOYMENT & HOSTING",
            "tech": "Production DevOps",
            "color": AMBER,
            "items": [
                ("Render Web Service", "Automated continuous delivery synchronized with GitHub main branch."),
                ("Gunicorn WSGI Server", "Production multi-worker WSGI HTTP server handling concurrent requests."),
                ("ProxyFix Middleware", "Reverse proxy header correction for secure HTTPS redirection and cookies."),
                ("Environment Hygiene", "Strict credential isolation through environment variables (.env).")
            ]
        }
    ]

    col_w = Inches(2.75)
    gap = Inches(0.24)
    left_start = Inches(0.8)

    for i, lyr in enumerate(layers):
        x = left_start + i * (col_w + gap)
        y = Inches(1.55)
        h = Inches(4.0)

        box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, col_w, h)
        box.fill.solid()
        box.fill.fore_color.rgb = CARD_BG
        box.line.color.rgb = BORDER_COLOR
        box.line.width = Pt(1)

        # Header tag stripe inside box
        top_bar = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, col_w, Inches(0.6))
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = lyr["color"]
        top_bar.line.fill.background()

        tb = slide3.shapes.add_textbox(x, y + Inches(0.05), col_w, Inches(0.5))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = f"{lyr['num']} • {lyr['layer']}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = WHITE

        # Content
        c_tb = slide3.shapes.add_textbox(x + Inches(0.12), y + Inches(0.65), col_w - Inches(0.24), h - Inches(0.75))
        ctf = c_tb.text_frame
        ctf.word_wrap = True

        p = ctf.paragraphs[0]
        p.text = lyr["tech"]
        p.font.name = FONT_HEADING
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        p.space_after = Pt(8)

        for heading, body in lyr["items"]:
            p = ctf.add_paragraph()
            p.text = f"• {heading}:"
            p.font.name = FONT_HEADING
            p.font.size = Pt(9.5)
            p.font.bold = True
            p.font.color.rgb = TEXT_MAIN
            
            p = ctf.add_paragraph()
            p.text = f"  {body}"
            p.font.name = FONT_BODY
            p.font.size = Pt(8.5)
            p.font.color.rgb = TEXT_MUTED
            p.space_after = Pt(4)

    # Bottom Architecture Flow Diagram Banner
    flow_box = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(5.7), Inches(11.733), Inches(1.2))
    flow_box.fill.solid()
    flow_box.fill.fore_color.rgb = NAVY_BG
    flow_box.line.color.rgb = RGBColor(51, 65, 85)
    flow_box.line.width = Pt(1)

    ftb = slide3.shapes.add_textbox(Inches(0.9), Inches(5.75), Inches(11.533), Inches(1.1))
    ftf = ftb.text_frame
    ftf.word_wrap = True

    p = ftf.paragraphs[0]
    p.text = "DATA FLOW & REQUEST EXECUTION PIPELINE"
    p.font.name = FONT_HEADING
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(4)

    p = ftf.add_paragraph()
    p.text = "[Student / Faculty / Admin Client]  ──(HTTPS / REST JSON)──►  [Gunicorn WSGI + ProxyFix]  ──►  [Flask Application Factory & Route Blueprints]\n                                                                                                              │ (RBAC Decorators & Token Auth)\n                                                                                                              ▼\n[PostgreSQL Cloud Database (Render)]  ◄──(SQLAlchemy 2.0 ORM Engine & Session Pool)───  [Models: User, Attendance, Result, Assignment]"
    p.font.name = "Consolas"
    p.font.size = Pt(8.5)
    p.font.color.rgb = RGBColor(226, 232, 240)


    # =========================================================================
    # SLIDE 4: Admin Dashboard and User Management
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4, PAGE_BG)
    add_header(slide4, "Administrative Control & Campus User Directory", "ADMINISTRATION MODULE", 4)
    add_footer(slide4, 4)

    # Left: 2 Actual Screenshots (Stacked)
    # Screenshot 1: 02_admin_dashboard.png
    sc1_y = Inches(1.55)
    sc_w = Inches(6.0)
    if os.path.exists(img2_path):
        slide4.shapes.add_picture(img2_path, Inches(0.8), sc1_y, width=sc_w)

    # Screenshot 2: 03_user_directory.png
    img3_path = os.path.join(SCREENSHOTS_DIR, "03_user_directory.png")
    sc2_y = Inches(4.25)
    if os.path.exists(img3_path):
        slide4.shapes.add_picture(img3_path, Inches(0.8), sc2_y, width=sc_w)

    # Right: Feature Explanations & Verified Capabilities (Width: 5.5 Inches)
    right_box = slide4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.05), Inches(1.55), Inches(5.48), Inches(5.35))
    right_box.fill.solid()
    right_box.fill.fore_color.rgb = CARD_BG
    right_box.line.color.rgb = BORDER_COLOR
    right_box.line.width = Pt(1)

    rtf = right_box.text_frame
    rtf.word_wrap = True
    rtf.margin_left = Inches(0.3)
    rtf.margin_right = Inches(0.3)
    rtf.margin_top = Inches(0.25)

    p = rtf.paragraphs[0]
    p.text = "🏛️ CENTRALIZED CAMPUS GOVERNANCE"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_BLUE
    p.space_after = Pt(10)

    admin_features = [
        ("Institutional Overview & Live KPI Metrics",
         "The Admin Dashboard aggregates real-time metrics across the institution: Total Enrolled Students (2), Teaching Faculty (3), Active Courses (19), Engineering Departments (6), and 100% System Health."),
        ("Centralized Campus User Directory",
         "Consolidated member ledger linking authentication accounts directly with Student and Faculty profiles. Eliminates detached data records and guarantees profile referential integrity."),
        ("Multi-Field Full-Text Search",
         "Instant searching across student and faculty records by Full Name, Roll Number, PRN (e.g. 24101099, 24101005), Employee Code (FAC-TEST-01), or College Email address."),
        ("Granular Multi-Criteria Filtering",
         "Filter registered campus members dynamically by Role (Admin, Faculty, Student), Academic Department (Computer Science & Engineering), Semester, Class Division, and Status."),
        ("Authorized Member Actions & Lifecycle",
         "Administrators can inspect detailed member profiles, view official generated grade cards, manage academic enrollment status, and maintain system security.")
    ]

    for title, desc in admin_features:
        p = rtf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = rtf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(9.5)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)


    # =========================================================================
    # SLIDE 5: Academic Management (Attendance & Examination Results)
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5, PAGE_BG)
    add_header(slide5, "Academic Management: Attendance & Examination Results", "ACADEMIC LIFECYCLE", 5)
    add_footer(slide5, 5)

    # 3 Screenshots layout: Left Column has Attendance (04) & Faculty Marks (06); Middle/Right has Student Results (05) + Features
    # Top Left: 04_student_attendance.png
    img4_path = os.path.join(SCREENSHOTS_DIR, "04_student_attendance.png")
    if os.path.exists(img4_path):
        slide5.shapes.add_picture(img4_path, Inches(0.8), Inches(1.55), width=Inches(5.6))

    # Bottom Left: 06_faculty_results_management.png
    img6_path = os.path.join(SCREENSHOTS_DIR, "06_faculty_results_management.png")
    if os.path.exists(img6_path):
        slide5.shapes.add_picture(img6_path, Inches(0.8), Inches(4.25), width=Inches(5.6))

    # Top Right: 05_student_results.png
    img5_path = os.path.join(SCREENSHOTS_DIR, "05_student_results.png")
    if os.path.exists(img5_path):
        slide5.shapes.add_picture(img5_path, Inches(6.65), Inches(1.55), width=Inches(5.88))

    # Bottom Right: Feature Breakdown Card
    acad_card = slide5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.65), Inches(4.35), Inches(5.88), Inches(2.55))
    acad_card.fill.solid()
    acad_card.fill.fore_color.rgb = CARD_BG
    acad_card.line.color.rgb = BORDER_COLOR
    acad_card.line.width = Pt(1)

    atf = acad_card.text_frame
    atf.word_wrap = True
    atf.margin_left = Inches(0.25)
    atf.margin_right = Inches(0.25)
    atf.margin_top = Inches(0.18)

    p = atf.paragraphs[0]
    p.text = "📊 VERIFIED ACADEMIC EVALUATION WORKFLOW"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = ROYAL_BLUE
    p.space_after = Pt(6)

    acad_features = [
        ("Real-Time Attendance Ledger",
         "Live roll-call tracking per course (CS601 Software Eng, 23CS3601 ML, 23CS3602 Software Testing) with Present/Late/Absent metrics and automatic 75% board threshold compliance."),
        ("4-Tier Assessment System",
         "Faculty marks entry sheet covering CA1 (20 pts), CA2 (20 pts), Mid-Sem (30 pts), and End-Sem (70 pts) with draft saving and administrative approval workflows."),
        ("Official Student Grade Card",
         "Automated total computation (125/100 weighted scale), letter grading (Grade A), SGPA & CGPA calculation (8.93 First Class), and printable grade report generation.")
    ]

    for title, desc in acad_features:
        p = atf.add_paragraph()
        p.text = f"• {title}: {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(9)
        p.font.color.rgb = TEXT_MAIN
        p.space_after = Pt(4)


    # =========================================================================
    # SLIDE 6: Campus Collaboration (Notices, Events and Assignments)
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide6, PAGE_BG)
    add_header(slide6, "Campus Collaboration: Notices, Events & Coursework", "COLLABORATION & SUBMISSIONS", 6)
    add_footer(slide6, 6)

    # Left: Real Screenshots (08_assignments_management.png & 07_notices_bulletin.png)
    img8_path = os.path.join(SCREENSHOTS_DIR, "08_assignments_management.png")
    if os.path.exists(img8_path):
        slide6.shapes.add_picture(img8_path, Inches(0.8), Inches(1.55), width=Inches(5.8))

    img7_path = os.path.join(SCREENSHOTS_DIR, "07_notices_bulletin.png")
    if os.path.exists(img7_path):
        slide6.shapes.add_picture(img7_path, Inches(0.8), Inches(4.25), width=Inches(5.8))

    # Right: Feature Cards (Width 5.68 Inches)
    collab_box = slide6.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.85), Inches(1.55), Inches(5.68), Inches(5.35))
    collab_box.fill.solid()
    collab_box.fill.fore_color.rgb = CARD_BG
    collab_box.line.color.rgb = BORDER_COLOR
    collab_box.line.width = Pt(1)

    ctf = collab_box.text_frame
    ctf.word_wrap = True
    ctf.margin_left = Inches(0.3)
    ctf.margin_right = Inches(0.3)
    ctf.margin_top = Inches(0.25)

    p = ctf.paragraphs[0]
    p.text = "📢 CAMPUS COMMUNICATION & COURSEWORK"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = AMBER
    p.space_after = Pt(12)

    collab_features = [
        ("Coursework & Assignment Management",
         "Faculty can create course-specific assignments (e.g. CS601 'Module 8 Lab Assignment on Concurrency') with point allocations (10 pts), assigned divisions, and strict deadlines."),
        ("Student Submission & Tamper-Proof Locking",
         "Students submit solutions directly through their portal. Once submitted, submissions are timestamped and locked against further modification to ensure academic integrity."),
        ("Faculty Evaluation & Grading Queue",
         "Real-time submission ledger displays delivered coursework (1 Completed, 1 Awaiting Review), providing instructors with direct review and grading interfaces."),
        ("Zero Mock Data Notice Bulletin",
         "The notice board operates directly against the PostgreSQL database with zero placeholder fallbacks. Handles official announcements across Academic, Examination, and Cultural categories."),
        ("Campus Events Coordination",
         "Dynamic event tracking for inter-collegiate and departmental fests (e.g. 'Spring Cultural Fest Vibrance 2026' at Open Air Amphitheatre).")
    ]

    for title, desc in collab_features:
        p = ctf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = ctf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(9.5)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)


    # =========================================================================
    # SLIDE 7: Conclusion and Future Scope
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide7, PAGE_BG)
    add_header(slide7, "Project Conclusion, Impact & Future Roadmap", "PROJECT WRAP-UP", 7)
    add_footer(slide7, 7)

    # 2 Big Cards: Left (Verified Achievements), Right (Future Roadmap)
    # Left Card: Achievements (Width: 5.7 Inches)
    ach_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.55), Inches(5.7), Inches(4.35))
    ach_box.fill.solid()
    ach_box.fill.fore_color.rgb = CARD_BG
    ach_box.line.color.rgb = BORDER_COLOR
    ach_box.line.width = Pt(1)

    atf = ach_box.text_frame
    atf.word_wrap = True
    atf.margin_left = Inches(0.3)
    atf.margin_right = Inches(0.3)
    atf.margin_top = Inches(0.22)

    p = atf.paragraphs[0]
    p.text = "🏁 VERIFIED CAPABILITIES & ACHIEVEMENTS"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(10)

    achievements = [
        ("Fully Operational Enterprise System",
         "Successfully delivered a complete, working ERP system for Sharad Institute of Technology College of Engineering (SITCOE), verified on live PostgreSQL cloud storage."),
        ("Comprehensive Academic Lifecycle",
         "Unified attendance roll-call tracking, 4-tier continuous assessment (CA1, CA2, Mid-Sem, End-Sem), and official published grade cards within a single platform."),
        ("Zero Demo/Mock Fallbacks",
         "Strict data integrity across all modules—every view directly binds to genuine database tables with authentic empty states."),
        ("Multi-Role Security & Isolation",
         "Robust Role-Based Access Control (RBAC) with token session isolation, preventing multi-tab session conflicts between Admin, Faculty, and Student users.")
    ]

    for title, desc in achievements:
        p = atf.add_paragraph()
        p.text = f"✔ {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = atf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(9.5)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(6)

    # Right Card: Future Scope (Width: 5.7 Inches)
    scope_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(1.55), Inches(5.7), Inches(4.35))
    scope_box.fill.solid()
    scope_box.fill.fore_color.rgb = CARD_BG
    scope_box.line.color.rgb = BORDER_COLOR
    scope_box.line.width = Pt(1)

    stf = scope_box.text_frame
    stf.word_wrap = True
    stf.margin_left = Inches(0.3)
    stf.margin_right = Inches(0.3)
    stf.margin_top = Inches(0.22)

    p = stf.paragraphs[0]
    p.text = "🚀 FUTURE ROADMAP & PLANNED ENHANCEMENTS"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_BLUE
    p.space_after = Pt(10)

    future_scope = [
        ("Automated SMS Shortage Alerts (Planned)",
         "Integrate SMS gateways (Twilio / Fast2SMS) to automatically alert parents and students when overall attendance falls below the mandatory 75% threshold."),
        ("Web Push Notifications (Planned)",
         "Implement Service Worker push notifications for urgent circulars, impending assignment deadlines, and newly published examination grade cards."),
        ("Advanced Academic Analytics & NIRF Reporting (Planned)",
         "Build graphical department-wise analytics, batch pass-rate distributions, and automated CSV/PDF report generators for NIRF and NAAC accreditation."),
        ("Native Mobile Companion Application (Planned)",
         "Develop a Flutter/React Native mobile client utilizing the existing secure REST API endpoints for convenient student access on Android and iOS devices.")
    ]

    for title, desc in future_scope:
        p = stf.add_paragraph()
        p.text = f"★ {title}"
        p.font.name = FONT_HEADING
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = TEXT_MAIN
        
        p = stf.add_paragraph()
        p.text = f"  {desc}"
        p.font.name = FONT_BODY
        p.font.size = Pt(9.5)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(6)

    # Bottom Attribution Banner (Repository & Credits)
    attrib_box = slide7.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.05), Inches(11.7), Inches(0.9))
    attrib_box.fill.solid()
    attrib_box.fill.fore_color.rgb = NAVY_BG
    attrib_box.line.color.rgb = RGBColor(51, 65, 85)
    attrib_box.line.width = Pt(1)

    ab_tf = attrib_box.text_frame
    ab_tf.word_wrap = True
    ab_tf.margin_left = Inches(0.25)
    ab_tf.margin_top = Inches(0.12)

    p = ab_tf.paragraphs[0]
    p.text = "PROJECT REPOSITORY & CODEBASE:"
    p.font.name = FONT_HEADING
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = EMERALD
    p.space_after = Pt(2)

    p = ab_tf.add_paragraph()
    p.text = "GitHub Repository: https://github.com/ayanmulani4867-cyber/Campus-mini2  •  Branch: main  •  SITCOE Yadrav"
    p.font.name = FONT_BODY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Save presentation
    prs.save(OUTPUT_PPTX)
    print(f"Successfully generated presentation with {len(prs.slides)} slides at: {OUTPUT_PPTX}")

if __name__ == "__main__":
    build_presentation()
