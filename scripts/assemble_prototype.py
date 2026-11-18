"""
Assembles ExamLMS_Complete_UI_Prototype.html
"""
import os
import sys

from screen_data import CATEGORIES, ALL_SCREENS
from screen_templates import get_screen_html

def build_complete_prototype_file():
    output_path = "ExamLMS_Complete_UI_Prototype.html"
    
    # Base layout
    import build_prototype_html
    header_html = build_prototype_html.build_prototype()
    
    # Screens HTML
    screens_content = ""
    for s in ALL_SCREENS:
        screens_content += get_screen_html(s)
        
    # Modals & Overlays
    modals_html = """
    </div> <!-- end content-area -->
  </main>
</div> <!-- end app-container -->

<!-- Add Module Modal -->
<div id="add-module-modal" class="modal-backdrop">
  <div class="modal-dialog">
    <div class="modal-header">
      <h3 style="font-size: 16px;">Add New Curriculum Module</h3>
      <button class="icon-btn" onclick="closeModal('add-module-modal')">✕</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">Module Title *</label>
        <input type="text" id="new-module-title" class="form-control" placeholder="e.g., Module 3: Advanced RAG and Agentic Workflows">
      </div>
      <div class="form-group">
        <label class="form-label">Module Objectives</label>
        <textarea class="form-control" placeholder="Key learning outcomes for this module..."></textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Order Priority Index</label>
        <input type="number" class="form-control" value="3">
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('add-module-modal')">Cancel</button>
      <button class="btn btn-custom-green" onclick="saveNewModule()">Create Module</button>
    </div>
  </div>
</div>

<!-- Course Preview Modal -->
<div id="preview-modal" class="modal-backdrop">
  <div class="modal-dialog" style="max-width: 750px;">
    <div class="modal-header">
      <h3 style="font-size: 16px;">Catalog Course Card Preview</h3>
      <button class="icon-btn" onclick="closeModal('preview-modal')">✕</button>
    </div>
    <div class="modal-body">
      <div style="border: 1px solid var(--card-border); border-radius: var(--radius); overflow: hidden; background: white; box-shadow: var(--shadow-sm);">
        <div style="height: 180px; background: linear-gradient(135deg, #1E1B4B, #312E81); display: flex; align-items: center; justify-content: center; color: white; font-size: 42px;">
          🤖
        </div>
        <div style="padding: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span class="badge badge-primary">Artificial Intelligence</span>
            <span style="font-weight: 700; color: var(--primary); font-size: 16px;">₹999</span>
          </div>
          <h4 style="font-size: 17px; margin-bottom: 6px;">Advanced Full Stack AI Engineering</h4>
          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 14px;">Master modern full-stack development, LangChain, vector databases, and autonomous AI agents.</p>
          <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--card-border); padding-top: 12px;">
            <span>⏱️ 12h 45m Total Duration</span>
            <span>⭐ 4.9 (420 reviews)</span>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('preview-modal')">Close Preview</button>
    </div>
  </div>
</div>

<!-- Toast Notification -->
<div id="toast-pill" class="toast-pill">
  <span id="toast-icon">✨</span>
  <span id="toast-msg">Notification message</span>
</div>

<!-- Client-side Navigation Router and State -->
<script>
  // All 78 screens metadata for search
  const SCREENS_DATA = [
"""
    for s in ALL_SCREENS:
        modals_html += f'    {{ id: "{s["id"]}", title: "{s["title"]}", category: "{s["category"]}", badge: "{s["badge"]}" }},\n'
    
    modals_html += """
  ];

  // Role Configuration and Nav Menus
  const ROLE_MENUS = {
    admin: {
      name: "Super Administrator",
      title: "Administrator",
      avatar: "AD",
      defaultScreen: "admin-dashboard",
      sections: [
        {
          label: "Core Management",
          items: [
            { id: "admin-dashboard", label: "Dashboard", icon: "📊" },
            { id: "admin-courses-overview", label: "Course Management", icon: "📚" },
            { id: "admin-all-courses", label: "All Courses", icon: "📋" },
            { id: "admin-create-basic", label: "+ Create Course (5 Steps)", icon: "✨", badge: "Wizard" },
            { id: "admin-course-requests", label: "Approvals Queue", icon: "⏳", badge: "3" }
          ]
        },
        {
          label: "Assessments & Proctors",
          items: [
            { id: "admin-question-bank", label: "Question Bank", icon: "❓" },
            { id: "admin-proctored-config", label: "Proctor Configuration", icon: "🛡️" },
            { id: "admin-proctoring-admin", label: "Live Proctor Monitor", icon: "🔴" }
          ]
        },
        {
          label: "Users & RBAC",
          items: [
            { id: "admin-user-management", label: "User Directory", icon: "👥" },
            { id: "admin-roles-permissions", label: "Roles & Permissions", icon: "🔑" }
          ]
        },
        {
          label: "Finance & Reports",
          items: [
            { id: "admin-billing", label: "Billing & Transactions", icon: "💳" },
            { id: "admin-price-history", label: "Price Audit Log", icon: "📈" },
            { id: "admin-analytics", label: "Analytics & Reports", icon: "📊" },
            { id: "admin-media-library", label: "Media Library", icon: "📁" }
          ]
        },
        {
          label: "Platform & Support",
          items: [
            { id: "admin-support-admin", label: "Support Tickets", icon: "🎫" },
            { id: "admin-platform-settings", label: "Platform Settings", icon: "⚙️" },
            { id: "shared-login", label: "Sign Out / Auth", icon: "🚪" }
          ]
        }
      ]
    },
    head: {
      name: "Dr. Vikram Malhotra",
      title: "Institution Head",
      avatar: "VM",
      defaultScreen: "head-dashboard",
      sections: [
        {
          label: "Campus Portal",
          items: [
            { id: "head-dashboard", label: "Institution HQ", icon: "🏛️" },
            { id: "head-explore-courses", label: "Course Marketplace", icon: "🌐" },
            { id: "head-purchase-request", label: "Requisition Seats", icon: "📝" },
            { id: "head-quotation-review", label: "Review Quotations", icon: "📄", badge: "1 New" },
            { id: "head-my-purchases", label: "My Packages & Seats", icon: "📦" }
          ]
        },
        {
          label: "Students & Batches",
          items: [
            { id: "head-seat-management", label: "Seat Allocations", icon: "💺" },
            { id: "head-student-management", label: "Student Roster", icon: "🎓" },
            { id: "head-batch-management", label: "Cohort Batches", icon: "👥" },
            { id: "head-reports", label: "Accreditation Reports", icon: "📊" }
          ]
        },
        {
          label: "Support & Account",
          items: [
            { id: "support-centre", label: "Help & Support", icon: "🎫" },
            { id: "shared-user-profile", label: "My Profile", icon: "👤" },
            { id: "shared-login", label: "Sign Out", icon: "🚪" }
          ]
        }
      ]
    },
    staff: {
      name: "Prof. Robert Chen",
      title: "Faculty Instructor",
      avatar: "RC",
      defaultScreen: "staff-dashboard",
      sections: [
        {
          label: "Teaching Workspace",
          items: [
            { id: "staff-dashboard", label: "Faculty Dashboard", icon: "👨‍🏫" },
            { id: "staff-my-courses", label: "Assigned Courses", icon: "📚" },
            { id: "staff-batch-details", label: "Cohort Attendance", icon: "👥" },
            { id: "staff-student-details", label: "Student Diagnostics", icon: "🔍" }
          ]
        },
        {
          label: "Grading & Exams",
          items: [
            { id: "staff-assessments", label: "Pending Evaluations", icon: "📝", badge: "14" },
            { id: "staff-results", label: "Class Gradebook", icon: "🏆" }
          ]
        },
        {
          label: "Account",
          items: [
            { id: "staff-profile", label: "Faculty Bio", icon: "👤" },
            { id: "shared-login", label: "Sign Out", icon: "🚪" }
          ]
        }
      ]
    },
    student: {
      name: "Alex Johnson",
      title: "Institutional Student",
      avatar: "AJ",
      defaultScreen: "student-dashboard",
      sections: [
        {
          label: "My Learning Hub",
          items: [
            { id: "student-dashboard", label: "Dashboard", icon: "🏠" },
            { id: "student-my-courses", label: "Enrolled Courses", icon: "📚" },
            { id: "student-learning-player", label: "Continue Learning", icon: "▶", badge: "100%" },
            { id: "student-explore", label: "Explore Catalog", icon: "🔍" },
            { id: "student-course-details", label: "Course Details", icon: "📖" }
          ]
        },
        {
          label: "Testing & Certification",
          items: [
            { id: "student-chapter-test", label: "Chapter Quiz", icon: "⏱️" },
            { id: "student-exam-instructions", label: "Proctored Exam Rules", icon: "📜" },
            { id: "student-cam-mic-check", label: "Cam & Mic Pre-check", icon: "📷" },
            { id: "student-proctored-exam", label: "Live Proctored Exam", icon: "🔒", badge: "LIVE" },
            { id: "student-my-certificates", label: "My Certificates", icon: "🎓" }
          ]
        },
        {
          label: "Career & Tools",
          items: [
            { id: "career-dashboard", label: "Career & Placement", icon: "💼" },
            { id: "career-jobs", label: "Job Marketplace", icon: "🎯" },
            { id: "career-ai-resume-builder", label: "AI Resume Builder", icon: "✨" },
            { id: "student-ai-tutor", label: "AI 24/7 Tutor", icon: "🤖" },
            { id: "student-code-workspace", label: "Code Playground", icon: "💻" }
          ]
        },
        {
          label: "Account & Support",
          items: [
            { id: "student-payment-history", label: "Payment Receipts", icon: "🧾" },
            { id: "support-centre", label: "Student Support", icon: "🎫" },
            { id: "shared-login", label: "Sign Out", icon: "🚪" }
          ]
        }
      ]
    }
  };

  let currentRole = "admin";
  let currentScreen = "admin-dashboard";

  function switchRole(role) {
    if (!ROLE_MENUS[role]) return;
    currentRole = role;
    document.getElementById("role-select").value = role;
    
    const meta = ROLE_MENUS[role];
    document.getElementById("sidebar-role-display").innerText = meta.title;
    document.getElementById("top-user-name").innerText = meta.name;
    document.getElementById("top-user-role").innerText = meta.title;
    document.getElementById("top-avatar-initials").innerText = meta.avatar;

    renderSidebar(meta);
    navigate(meta.defaultScreen);
  }

  function renderSidebar(meta) {
    const container = document.getElementById("sidebar-nav-container");
    let navHtml = "";

    meta.sections.forEach(sec => {
      navHtml += `<div class="nav-section-label">${sec.label}</div>`;
      navHtml += `<ul class="nav-menu">`;
      sec.items.forEach(it => {
        navHtml += `
          <li class="nav-item">
            <a class="nav-link ${it.id === currentScreen ? 'active' : ''}" onclick="navigate('${it.id}')" id="nav-${it.id}">
              <span>${it.icon}</span>
              <span>${it.label}</span>
              ${it.badge ? `<span class="nav-badge ${it.badge === 'LIVE' ? 'purple' : ''}">${it.badge}</span>` : ''}
            </a>
          </li>
        `;
      });
      navHtml += `</ul>`;
    });

    container.innerHTML = navHtml;
  }

  function navigate(screenId) {
    const target = document.getElementById("screen-" + screenId);
    if (!target) {
      console.warn("Screen not found:", screenId);
      return;
    }

    // Hide all
    document.querySelectorAll(".screen-view").forEach(el => el.classList.remove("active"));
    target.classList.add("active");
    currentScreen = screenId;

    // Update active nav class
    document.querySelectorAll(".nav-link").forEach(el => el.classList.remove("active"));
    const activeLink = document.getElementById("nav-" + screenId);
    if (activeLink) activeLink.classList.add("active");

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleGlobalSearch(val) {
    const pop = document.getElementById("search-results-popover");
    if (!val || val.trim().length === 0) {
      pop.style.display = "none";
      return;
    }

    const q = val.toLowerCase().trim();
    const matches = SCREENS_DATA.filter(s => 
      s.title.toLowerCase().includes(q) || 
      s.category.toLowerCase().includes(q) || 
      s.badge.toLowerCase().includes(q)
    ).slice(0, 8);

    if (matches.length === 0) {
      pop.innerHTML = `<div style="padding: 12px; color: var(--text-muted); font-size: 13px;">No matching screens found for "${val}"</div>`;
      pop.style.display = "block";
      return;
    }

    pop.innerHTML = matches.map(m => `
      <div class="search-result-item" onclick="navigate('${m.id}'); document.getElementById('search-results-popover').style.display='none'; document.getElementById('global-search-input').value='';">
        <div>
          <span style="font-weight: 600; color: var(--text-primary);">${m.title}</span>
          <span style="font-size: 11px; color: var(--text-secondary); margin-left: 6px;">(${m.category})</span>
        </div>
        <span class="badge badge-primary">${m.badge}</span>
      </div>
    `).join("");

    pop.style.display = "block";
  }

  function showToast(msg) {
    const pill = document.getElementById("toast-pill");
    document.getElementById("toast-msg").innerText = msg;
    pill.classList.add("show");
    setTimeout(() => pill.classList.remove("show"), 2800);
  }

  function showAddModuleModal() {
    document.getElementById("add-module-modal").classList.add("active");
  }
  function closeModal(id) {
    document.getElementById(id).classList.remove("active");
  }
  function saveNewModule() {
    closeModal("add-module-modal");
    showToast("New Module Created Successfully!");
  }
  function showPreviewModal() {
    document.getElementById("preview-modal").classList.add("active");
  }

  function calculateInstPricing() {
    const seats = parseInt(document.getElementById("calc-seats-input").value) || 0;
    const rate = parseInt(document.getElementById("base-rate-input").value) || 499;
    const total = seats * rate;
    document.getElementById("calc-result-display").innerText = "₹" + total.toLocaleString("en-IN") + " total";
  }

  function handleStudentEnroll() {
    showToast("Enrolling via Institutional Seat Package...");
    setTimeout(() => {
      navigate("student-learning-player");
      showToast("Enrollment Verified! 100% Video Progress Active.");
    }, 600);
  }

  function runCodeSimulator() {
    const consoleBox = document.getElementById("console-output-box");
    consoleBox.innerText = "$ python main.py\\n[Executing AST...]\\nComputed Vector Similarity: 0.9942\\nMatch Status: Highly Relevant Context Retrieved!\\nProcess finished with exit code 0";
    showToast("Code executed successfully!");
  }

  function resetCodeSimulator() {
    document.getElementById("console-output-box").innerText = "$ Ready for execution...";
  }

  // Initialize on load
  window.addEventListener("DOMContentLoaded", () => {
    switchRole("admin");
  });
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header_html + screens_content + modals_html)
        
    print(f"Successfully generated {output_path} ({os.path.getsize(output_path):,} bytes)")

if __name__ == "__main__":
    build_complete_prototype_file()
