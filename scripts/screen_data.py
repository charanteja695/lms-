# scripts/screen_data.py
# Comprehensive metadata and structure for all 78 screens across all 7 categories

CATEGORIES = [
    {
        "id": "A",
        "title": "Shared Screens",
        "role": "Shared (All Roles)",
        "screens": [
            {
                "id": "shared-login",
                "title": "Login",
                "badge": "Authentication",
                "desc": "Secure multi-role authentication portal with SSO, institutional login tabs, and remember-me security features.",
                "type": "auth",
                "category": "Shared"
            },
            {
                "id": "shared-forgot-password",
                "title": "Forgot Password",
                "badge": "Account Recovery",
                "desc": "Self-service password recovery with email verification and rate-limited token delivery.",
                "type": "auth",
                "category": "Shared"
            },
            {
                "id": "shared-reset-password",
                "title": "Reset Password",
                "badge": "Security",
                "desc": "Password update screen with real-time complexity validation and active session termination toggles.",
                "type": "auth",
                "category": "Shared"
            },
            {
                "id": "shared-notifications",
                "title": "Notifications",
                "badge": "Communications",
                "desc": "Unified notification inbox with filter tabs (All, System, Courses, Exams) and granular preference controls.",
                "type": "general",
                "category": "Shared"
            },
            {
                "id": "shared-user-profile",
                "title": "User Profile",
                "badge": "Identity",
                "desc": "Personal profile management with avatar uploader, institutional affiliation details, and contact settings.",
                "type": "general",
                "category": "Shared"
            },
            {
                "id": "shared-account-settings",
                "title": "Account Settings",
                "badge": "Preferences",
                "desc": "System preferences including timezone, language, display density, and notification channels.",
                "type": "general",
                "category": "Shared"
            },
            {
                "id": "shared-security-settings",
                "title": "Security Settings",
                "badge": "Security",
                "desc": "2-Factor Authentication (TOTP/SMS), password alteration, and active login sessions management.",
                "type": "general",
                "category": "Shared"
            }
        ]
    },
    {
        "id": "B",
        "title": "Admin Portal",
        "role": "Administrator",
        "screens": [
            {
                "id": "admin-dashboard",
                "title": "Admin Dashboard",
                "badge": "Core Overview",
                "desc": "Executive LMS overview with real-time MRR, active students, course completion rates, and institutional growth metrics.",
                "type": "dashboard",
                "category": "Admin"
            },
            {
                "id": "admin-courses-overview",
                "title": "Course Management Overview",
                "badge": "Curriculum",
                "desc": "High-level summary of published, in-review, and draft courses with category analytics and fast creation triggers.",
                "type": "courses",
                "category": "Admin"
            },
            {
                "id": "admin-all-courses",
                "title": "All Courses",
                "badge": "Directory",
                "desc": "Comprehensive searchable catalog of courses with status badges, price models, enrollment tallies, and batch actions.",
                "type": "courses",
                "category": "Admin"
            },
            {
                "id": "admin-create-basic",
                "title": "Create Course – Basic Information",
                "badge": "Wizard Step 1",
                "desc": "Step 1 of 5: Title, code, thumbnail uploader with instant preview, descriptions, category, difficulty, and learning tags.",
                "type": "wizard",
                "category": "Admin"
            },
            {
                "id": "admin-create-pricing",
                "title": "Course Pricing – Individual and Institutional",
                "badge": "Wizard Step 2",
                "desc": "Step 2 of 5: Dual pricing configuration for direct B2C sales and bulk institutional tier pricing with live dynamic calculator.",
                "type": "wizard",
                "category": "Admin"
            },
            {
                "id": "admin-create-modules",
                "title": "Module and Chapter Builder",
                "badge": "Wizard Step 3",
                "desc": "Step 3 of 5: Drag-and-drop course hierarchy builder, video durations, PDF attachments, and green #096644 Add Module action.",
                "type": "wizard",
                "category": "Admin"
            },
            {
                "id": "admin-create-assessments",
                "title": "Assessment Builder",
                "badge": "Wizard Step 4",
                "desc": "Step 4 of 5: Interactive test builder for chapter quizzes and module milestones with passing score thresholds.",
                "type": "wizard",
                "category": "Admin"
            },
            {
                "id": "admin-question-bank",
                "title": "Question Management",
                "badge": "Assessment Bank",
                "desc": "Centralized question repository supporting MCQ, multiple-select, true/false, and code test cases.",
                "type": "assessments",
                "category": "Admin"
            },
            {
                "id": "admin-proctored-config",
                "title": "Final Proctored Exam Configuration",
                "badge": "Proctoring",
                "desc": "Strict proctoring parameter configuration: webcam AI tracking, microphone thresholds, tab-switch limits, and exam windows.",
                "type": "assessments",
                "category": "Admin"
            },
            {
                "id": "admin-review-publish",
                "title": "Review and Publish Course",
                "badge": "Wizard Step 5",
                "desc": "Step 5 of 5: Validation summary, pricing review, syllabus audit, draft saving, and live catalog publishing.",
                "type": "wizard",
                "category": "Admin"
            },
            {
                "id": "admin-course-studio",
                "title": "Course Studio",
                "badge": "Content Studio",
                "desc": "Media transcoding pipeline, interactive video preview with timestamps, chapter markers, and subtitle management.",
                "type": "media",
                "category": "Admin"
            },
            {
                "id": "admin-course-requests",
                "title": "Course Requests and Approvals",
                "badge": "Workflow",
                "desc": "Faculty and institutional course submission review queue with diff viewer and editorial feedback tools.",
                "type": "workflow",
                "category": "Admin"
            },
            {
                "id": "admin-user-management",
                "title": "User Management",
                "badge": "Administration",
                "desc": "Role-filtered global user directory with status toggles, batch invitations, and institutional tagging.",
                "type": "users",
                "category": "Admin"
            },
            {
                "id": "admin-roles-permissions",
                "title": "Role and Permissions",
                "badge": "RBAC",
                "desc": "Fine-grained permission matrix across Superadmin, Content Creator, Institution Admin, Faculty, and Student roles.",
                "type": "users",
                "category": "Admin"
            },
            {
                "id": "admin-billing",
                "title": "Billing and Transactions",
                "badge": "Finance",
                "desc": "Platform financial ledger, B2C payment gateway settlements, institutional wire invoices, and refund manager.",
                "type": "finance",
                "category": "Admin"
            },
            {
                "id": "admin-price-history",
                "title": "Price Change History",
                "badge": "Audit Log",
                "desc": "Immutable price audit records recording old price, revised price, authorizing admin, and timestamp.",
                "type": "finance",
                "category": "Admin"
            },
            {
                "id": "admin-analytics",
                "title": "Analytics and Reports",
                "badge": "Intelligence",
                "desc": "Visual analytics covering retention curves, drop-off rates, assessment scores, and exportable CSV reports.",
                "type": "analytics",
                "category": "Admin"
            },
            {
                "id": "admin-media-library",
                "title": "Media Library",
                "badge": "Storage",
                "desc": "Asset storage explorer displaying storage quotas, CDN status, video compressions, and multi-file uploader.",
                "type": "media",
                "category": "Admin"
            },
            {
                "id": "admin-proctoring-admin",
                "title": "Proctoring Administration",
                "badge": "Supervision",
                "desc": "Real-time AI proctoring monitor, incident anomaly flags, video verification clips, and exam violation logs.",
                "type": "proctoring",
                "category": "Admin"
            },
            {
                "id": "admin-support-admin",
                "title": "Support Administration",
                "badge": "Operations",
                "desc": "Global helpdesk ticket triage queue with priority routing, SLA violation warnings, and assigned agent rosters.",
                "type": "support",
                "category": "Admin"
            },
            {
                "id": "admin-platform-settings",
                "title": "Platform Settings",
                "badge": "Configuration",
                "desc": "White-label branding controls, logo upload, email templates, API keys, and system maintenance switches.",
                "type": "config",
                "category": "Admin"
            }
        ]
    },
    {
        "id": "C",
        "title": "Institution Head Portal",
        "role": "Institution Head",
        "screens": [
            {
                "id": "head-dashboard",
                "title": "Institution Dashboard",
                "badge": "Institution HQ",
                "desc": "Campus-wide overview: total active seat capacity, student pass rates, package expiration timers, and quick actions.",
                "type": "dashboard",
                "category": "Institution"
            },
            {
                "id": "head-explore-courses",
                "title": "Explore Courses",
                "badge": "Catalog",
                "desc": "Enterprise course catalog with bulk tier discounts, curriculum specifications, and quote builder actions.",
                "type": "courses",
                "category": "Institution"
            },
            {
                "id": "head-course-details",
                "title": "Course Details",
                "badge": "Curriculum",
                "desc": "Institutional syllabus overview, instructor qualifications, lab requirements, and seat requisition modal.",
                "type": "courses",
                "category": "Institution"
            },
            {
                "id": "head-purchase-request",
                "title": "Institution Purchase Request",
                "badge": "Procurement",
                "desc": "Interactive procurement calculator: select seats, target departments, start dates, and submit formal quote request.",
                "type": "procurement",
                "category": "Institution"
            },
            {
                "id": "head-quotation-review",
                "title": "Quotation Review",
                "badge": "Approval",
                "desc": "Admin-issued formal price proposal review with institutional volume discount breakdown and digital signing.",
                "type": "procurement",
                "category": "Institution"
            },
            {
                "id": "head-payment-screen",
                "title": "Payment Screen",
                "badge": "Settlement",
                "desc": "Institutional payment checkout supporting Corporate NetBanking, NEFT/RTGS virtual accounts, and Purchase Order upload.",
                "type": "procurement",
                "category": "Institution"
            },
            {
                "id": "head-my-purchases",
                "title": "My Purchases",
                "badge": "Entitlements",
                "desc": "Active institutional license packages, seat usage bars, validity periods, and downloadable tax invoices.",
                "type": "procurement",
                "category": "Institution"
            },
            {
                "id": "head-seat-management",
                "title": "Seat Management",
                "badge": "Allocation",
                "desc": "Interactive seat allocation engine: single student assignment, CSV bulk upload, license transfer, and revocation.",
                "type": "students",
                "category": "Institution"
            },
            {
                "id": "head-student-management",
                "title": "Student Management",
                "badge": "Directory",
                "desc": "Institutional student directory with department tags, active package enrollments, and real-time progress indicators.",
                "type": "students",
                "category": "Institution"
            },
            {
                "id": "head-batch-management",
                "title": "Batch Management",
                "badge": "Cohort",
                "desc": "Cohort creation wizard: group students into academic terms, assign mentor faculty, and set target milestones.",
                "type": "students",
                "category": "Institution"
            },
            {
                "id": "head-reports",
                "title": "Institution Reports",
                "badge": "Analytics",
                "desc": "Accreditation-ready performance reports: batch completion velocity, exam distribution, and PDF export.",
                "type": "analytics",
                "category": "Institution"
            }
        ]
    },
    {
        "id": "D",
        "title": "Staff Portal",
        "role": "Staff / Faculty",
        "screens": [
            {
                "id": "staff-dashboard",
                "title": "Staff Dashboard",
                "badge": "Faculty HQ",
                "desc": "Faculty command center: active cohorts, upcoming grading duties, student doubts queue, and live session links.",
                "type": "dashboard",
                "category": "Staff"
            },
            {
                "id": "staff-my-courses",
                "title": "My Courses",
                "badge": "Teaching",
                "desc": "Catalog of courses taught by the instructor with direct shortcuts to gradebooks, announcements, and chapters.",
                "type": "courses",
                "category": "Staff"
            },
            {
                "id": "staff-batch-details",
                "title": "Batch Details",
                "badge": "Cohort View",
                "desc": "Detailed cohort roster view, attendance logs, chapter completion heatmap, and broadcast announcements.",
                "type": "students",
                "category": "Staff"
            },
            {
                "id": "staff-student-details",
                "title": "Student Details",
                "badge": "Individual Progress",
                "desc": "Individual student diagnostic: module scores, video watch time, assignment attempts, and customized mentor notes.",
                "type": "students",
                "category": "Staff"
            },
            {
                "id": "staff-assessments",
                "title": "Assessments",
                "badge": "Evaluation",
                "desc": "Assessment grading hub: review subjective responses, coding exercise submissions, and verify auto-graded tests.",
                "type": "assessments",
                "category": "Staff"
            },
            {
                "id": "staff-results",
                "title": "Results",
                "badge": "Gradebook",
                "desc": "Comprehensive class gradebook with weighted averages, letter grades, percentile ranks, and CSV grade export.",
                "type": "assessments",
                "category": "Staff"
            },
            {
                "id": "staff-profile",
                "title": "Staff Profile",
                "badge": "Academic Bio",
                "desc": "Faculty profile, office hours schedule, subject specializations, research publications, and student ratings.",
                "type": "profile",
                "category": "Staff"
            }
        ]
    },
    {
        "id": "E",
        "title": "Student Portal",
        "role": "Student",
        "screens": [
            {
                "id": "student-dashboard",
                "title": "Student Dashboard",
                "badge": "Learning HQ",
                "desc": "Personalized student dashboard: In-progress courses, upcoming deadlines, weekly study streak, and institutional package banner.",
                "type": "dashboard",
                "category": "Student"
            },
            {
                "id": "student-explore",
                "title": "Explore Courses",
                "badge": "Marketplace",
                "desc": "Course exploration with search filters, instructor ratings, duration, difficulty, and clear enrollment triggers.",
                "type": "courses",
                "category": "Student"
            },
            {
                "id": "student-course-details",
                "title": "Course Details",
                "badge": "Overview",
                "desc": "Comprehensive syllabus preview, video trailer, faculty profile, and institutional 'Access via Package' or 'Enroll Now' button.",
                "type": "courses",
                "category": "Student"
            },
            {
                "id": "student-checkout",
                "title": "Individual Course Checkout",
                "badge": "Payment",
                "desc": "Secure individual checkout page with order summary, tax breakdown, UPI/card payment methods, and instant access guarantee.",
                "type": "checkout",
                "category": "Student"
            },
            {
                "id": "student-my-courses",
                "title": "My Courses",
                "badge": "Enrolled",
                "desc": "Active student library with progress percentages, completed checkmarks, and one-click 'Continue Learning' action.",
                "type": "courses",
                "category": "Student"
            },
            {
                "id": "student-learning-player",
                "title": "Learning Player",
                "badge": "Video & LMS",
                "desc": "Complete LMS player with video player, 100% completion verified badge, curriculum sidebar, notes, resources, and speed controls.",
                "type": "learning",
                "category": "Student"
            },
            {
                "id": "student-chapter-test",
                "title": "Chapter Test",
                "badge": "Quiz",
                "desc": "Interactive chapter quiz with question counter, countdown timer, multiple-choice selector, and instant explanation.",
                "type": "assessment",
                "category": "Student"
            },
            {
                "id": "student-module-test",
                "title": "Module Test",
                "badge": "Milestone Test",
                "desc": "Multi-topic assessment with question palette navigation, flag for review, and completion confirmation dialog.",
                "type": "assessment",
                "category": "Student"
            },
            {
                "id": "student-exam-instructions",
                "title": "Final Exam Instructions",
                "badge": "Guidelines",
                "desc": "Strict proctoring rules, passing threshold (75%), webcam requirements, and mandatory acceptance checkbox.",
                "type": "proctored",
                "category": "Student"
            },
            {
                "id": "student-cam-mic-check",
                "title": "Camera and Microphone Pre-check",
                "badge": "Diagnostics",
                "desc": "Interactive hardware check: live camera feed preview with AI face detection box, mic audio level meter, and system speed verification.",
                "type": "proctored",
                "category": "Student"
            },
            {
                "id": "student-proctored-exam",
                "title": "Final Proctored Examination",
                "badge": "Active Exam",
                "desc": "Secure exam environment: countdown timer, floating live webcam AI stream, fullscreen deterrent lock, question palette, and autosave.",
                "type": "proctored",
                "category": "Student"
            },
            {
                "id": "student-exam-results",
                "title": "Exam Results",
                "badge": "Scorecard",
                "desc": "Detailed scorecard: 92/100 score, 'PASSED' distinction banner, module-wise performance breakdown, and certificate unlock button.",
                "type": "proctored",
                "category": "Student"
            },
            {
                "id": "student-my-certificates",
                "title": "My Certificates",
                "badge": "Credentials",
                "desc": "Earned certificates gallery with issue dates, verifiable credential hashes, PDF download, and LinkedIn share button.",
                "type": "certificate",
                "category": "Student"
            },
            {
                "id": "student-certificate-view",
                "title": "Certificate View",
                "badge": "High-Res Diploma",
                "desc": "High-resolution digital certificate view featuring gold seal, QR verification code, authorized signatures, and print action.",
                "type": "certificate",
                "category": "Student"
            },
            {
                "id": "student-cert-verification",
                "title": "Certificate Verification",
                "badge": "Public Auth",
                "desc": "Public credential verification portal confirming student authenticity, issue timestamp, course code, and digital cryptographic hash.",
                "type": "certificate",
                "category": "Student"
            },
            {
                "id": "student-payment-history",
                "title": "Individual Payment History",
                "badge": "Receipts",
                "desc": "Personal purchase ledger for individual students: invoices, transaction IDs, payment methods, and downloadable GST receipts.",
                "type": "checkout",
                "category": "Student"
            },
            {
                "id": "student-ai-tutor",
                "title": "AI Tutor",
                "badge": "24/7 Mentor",
                "desc": "Context-aware AI study assistant providing real-time code explanations, concept simplifications, and practice quizzes.",
                "type": "ai",
                "category": "Student"
            },
            {
                "id": "student-code-workspace",
                "title": "Code Execution Workspace",
                "badge": "Interactive IDE",
                "desc": "Browser-based coding environment with syntax highlighting, stdin inputs, run button, and terminal console output.",
                "type": "ide",
                "category": "Student"
            }
        ]
    },
    {
        "id": "F",
        "title": "Career and Placement Portal",
        "role": "Student & Career Services",
        "screens": [
            {
                "id": "career-dashboard",
                "title": "Career Dashboard",
                "badge": "Placement HQ",
                "desc": "Career command centre: job application tracker, interview invitations, resume ATS rating score, and recruiter views.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-jobs",
                "title": "Job Marketplace",
                "badge": "Hiring Portal",
                "desc": "Curated tech and engineering jobs with skill match scores, company ratings, salary ranges, and quick apply tags.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-job-details",
                "title": "Job Details",
                "badge": "Opportunity",
                "desc": "Role breakdown, tech stack requirements, compensation package, candidate fit analysis (94% match), and 1-click application.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-resume-centre",
                "title": "Resume Centre",
                "badge": "Documents",
                "desc": "Resume repository with ATS score indicators, format checks, version control, and tailored variations for specific roles.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-ai-resume-builder",
                "title": "AI Resume Builder",
                "badge": "AI Optimization",
                "desc": "Intelligent builder automatically importing verified LMS projects, certifications, and technical skills into ATS-ready format.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-resume-analysis",
                "title": "Resume Analysis",
                "badge": "ATS Diagnostics",
                "desc": "Detailed resume audit report: keyword density match, formatting score (89/100), weak bullet points, and AI recommendations.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-job-application",
                "title": "Job Application",
                "badge": "Submission",
                "desc": "Streamlined application submission: attach verified certificate, select tailored resume, write custom note, and review.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-company-mgmt",
                "title": "Hiring Company Management",
                "badge": "Recruiter Hub",
                "desc": "Corporate partner portal: company profile setup, job requisition management, and candidate applicant pool pipeline.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-ai-interviewer",
                "title": "AI Interviewer",
                "badge": "Mock Session",
                "desc": "Interactive mock technical and behavioral interview with voice input, real-time audio analysis, and response timer.",
                "type": "career",
                "category": "Career"
            },
            {
                "id": "career-interview-feedback",
                "title": "Interview Feedback",
                "badge": "Scorecard",
                "desc": "Comprehensive post-interview analysis: technical depth (92%), communication cadence (86%), confidence, and improvement roadmap.",
                "type": "career",
                "category": "Career"
            }
        ]
    },
    {
        "id": "G",
        "title": "Support and Ticket Management",
        "role": "Support (All Roles)",
        "screens": [
            {
                "id": "support-centre",
                "title": "Support Centre",
                "badge": "Helpdesk",
                "desc": "Self-service helpdesk with searchable knowledge base articles, active ticket summary cards, and quick ticket submission.",
                "type": "support",
                "category": "Support"
            },
            {
                "id": "support-create-ticket",
                "title": "Create Support Ticket",
                "badge": "Issue Filing",
                "desc": "Structured support request form: category (Billing, Video, Proctoring, LMS bug), priority, attachment uploader, and details.",
                "type": "support",
                "category": "Support"
            },
            {
                "id": "support-ticket-details",
                "title": "Ticket Details",
                "badge": "Case View",
                "desc": "Ticket timeline view with status pill ('In Progress'), SLA timer, assigned technician, and chronological audit events.",
                "type": "support",
                "category": "Support"
            },
            {
                "id": "support-conversation",
                "title": "Support Conversation",
                "badge": "Live Thread",
                "desc": "Two-way threaded discussion between user and ExamLMS specialist with rich media previews and instant resolution actions.",
                "type": "support",
                "category": "Support"
            }
        ]
    }
]

ALL_SCREENS = []
for cat in CATEGORIES:
    for s in cat["screens"]:
        ALL_SCREENS.append(s)

print(f"Total categories: {len(CATEGORIES)}")
print(f"Total screens registered: {len(ALL_SCREENS)}")
