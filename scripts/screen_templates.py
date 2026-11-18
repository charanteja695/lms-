"""
Main script to assemble the complete ExamLMS Redesign Suite.
Generates:
1. ExamLMS_Complete_UI_Prototype.html
2. design_doc_source.html
Then calls Node.js/Playwright to export ExamLMS_Complete_UI_Design.pdf
"""
import os
import sys

from screen_data import CATEGORIES, ALL_SCREENS

def get_screen_html(screen):
    sid = screen["id"]
    title = screen["title"]
    badge = screen["badge"]
    desc = screen["desc"]
    cat = screen["category"]
    
    # Generic header for each screen inside content area
    header_html = f"""
      <div class="page-header">
        <div class="page-title-group">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span class="badge badge-primary">{cat}</span>
            <span class="badge badge-neutral">{badge}</span>
          </div>
          <h1>{title}</h1>
          <p>{desc}</p>
        </div>
        <div class="action-group">
    """
    
    # Specific action buttons per screen
    if "admin-create" in sid or sid == "admin-review-publish":
        header_html += """
          <button class="btn btn-secondary btn-sm" onclick="showToast('Draft progress saved')">💾 Save Draft</button>
          <button class="btn btn-primary btn-sm" onclick="showPreviewModal()">👁️ Preview Course</button>
        """
    elif sid == "admin-all-courses" or sid == "admin-courses-overview":
        header_html += """
          <button class="btn btn-primary" onclick="navigate('admin-create-basic')">+ Create Course</button>
        """
    elif sid == "head-explore-courses" or sid == "head-course-details":
        header_html += """
          <button class="btn btn-primary" onclick="navigate('head-purchase-request')">📋 Request Bulk Quote</button>
        """
    elif sid == "head-purchase-request":
        header_html += """
          <button class="btn btn-success" onclick="navigate('head-quotation-review')">Submit Purchase Request</button>
        """
    elif sid == "head-quotation-review":
        header_html += """
          <button class="btn btn-primary" onclick="navigate('head-payment-screen')">Accept Quote & Proceed to Payment</button>
        """
    elif sid == "student-course-details":
        header_html += """
          <button class="btn btn-success btn-lg" onclick="handleStudentEnroll()">🚀 Enroll Now (College Package)</button>
          <button class="btn btn-secondary btn-lg" onclick="navigate('student-checkout')">💳 Buy Individual Access</button>
        """
    elif sid == "student-learning-player":
        header_html += """
          <span class="badge badge-success" style="font-size: 13px; padding: 6px 12px;">✅ 100% Video Progress Verified</span>
          <button class="btn btn-primary btn-sm" onclick="navigate('student-chapter-test')">Take Chapter Quiz →</button>
        """
    elif sid == "student-exam-instructions":
        header_html += """
          <button class="btn btn-primary btn-lg" onclick="navigate('student-cam-mic-check')">Proceed to System Check →</button>
        """
    elif sid == "student-cam-mic-check":
        header_html += """
          <button class="btn btn-success btn-lg" onclick="navigate('student-proctored-exam')">Enter Proctored Exam Room 🔒</button>
        """
    elif sid == "student-proctored-exam":
        header_html += """
          <button class="btn btn-danger btn-sm" onclick="navigate('student-exam-results')">Finish & Submit Exam</button>
        """
    elif sid == "student-code-workspace":
        header_html += """
          <button class="btn btn-custom-green" onclick="runCodeSimulator()">▶ Run Code</button>
          <button class="btn btn-secondary" onclick="resetCodeSimulator()">Reset</button>
        """
    elif sid == "support-centre":
        header_html += """
          <button class="btn btn-primary" onclick="navigate('support-create-ticket')">+ Create Ticket</button>
        """
    else:
        header_html += """
          <button class="btn btn-secondary btn-sm" onclick="showToast('Exporting data...')">📥 Export CSV</button>
          <button class="btn btn-primary btn-sm" onclick="showToast('Action triggered')">⚡ Quick Action</button>
        """
    header_html += "</div></div>"
    
    # Body HTML depending on screen ID
    body_html = ""
    
    # Check wizard screens
    if "admin-create" in sid or sid == "admin-review-publish":
        step_active = 1
        if "pricing" in sid: step_active = 2
        elif "modules" in sid: step_active = 3
        elif "assessments" in sid: step_active = 4
        elif "review" in sid: step_active = 5
        
        stepper = f"""
        <div class="stepper-nav">
          <div class="step-pill {'completed' if step_active > 1 else ('active' if step_active == 1 else '')}" onclick="navigate('admin-create-basic')">
            <span class="step-num">{'✓' if step_active > 1 else '1'}</span>
            <span>1. Basic Information</span>
          </div>
          <div class="step-pill {'completed' if step_active > 2 else ('active' if step_active == 2 else '')}" onclick="navigate('admin-create-pricing')">
            <span class="step-num">{'✓' if step_active > 2 else '2'}</span>
            <span>2. Pricing</span>
          </div>
          <div class="step-pill {'completed' if step_active > 3 else ('active' if step_active == 3 else '')}" onclick="navigate('admin-create-modules')">
            <span class="step-num">{'✓' if step_active > 3 else '3'}</span>
            <span>3. Modules & Chapters</span>
          </div>
          <div class="step-pill {'completed' if step_active > 4 else ('active' if step_active == 4 else '')}" onclick="navigate('admin-create-assessments')">
            <span class="step-num">{'✓' if step_active > 4 else '4'}</span>
            <span>4. Tests & Assessments</span>
          </div>
          <div class="step-pill {'active' if step_active == 5 else ''}" onclick="navigate('admin-review-publish')">
            <span class="step-num">5</span>
            <span>5. Review & Publish</span>
          </div>
        </div>
        """
        body_html += stepper
    
    # Screen-specific unique interactive bodies
    if sid == "shared-login":
        body_html += """
        <div style="max-width: 480px; margin: 30px auto;">
          <div class="card" style="padding: 32px; box-shadow: var(--shadow-lg);">
            <div style="text-align: center; margin-bottom: 24px;">
              <div class="brand-logo" style="margin: 0 auto 12px auto; width: 48px; height: 48px; font-size: 22px;">E</div>
              <h2 style="font-size: 22px;">Sign in to ExamLMS</h2>
              <p style="color: var(--text-secondary); font-size: 13.5px; margin-top: 4px;">Select your role to test instant single-click prototype login</p>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 20px;">
              <button class="btn btn-secondary btn-sm" onclick="switchRole('admin'); navigate('admin-dashboard'); showToast('Logged in as Administrator');">🛡️ Admin</button>
              <button class="btn btn-secondary btn-sm" onclick="switchRole('head'); navigate('head-dashboard'); showToast('Logged in as Institution Head');">🏛️ College Head</button>
              <button class="btn btn-secondary btn-sm" onclick="switchRole('staff'); navigate('staff-dashboard'); showToast('Logged in as Faculty Staff');">👨‍🏫 Faculty</button>
              <button class="btn btn-secondary btn-sm" onclick="switchRole('student'); navigate('student-dashboard'); showToast('Logged in as Student');">🎓 Student</button>
            </div>

            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input type="email" class="form-control" value="alex.johnson@apextech.edu" placeholder="you@institution.edu">
            </div>
            <div class="form-group">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <label class="form-label" style="margin: 0;">Password</label>
                <a href="javascript:navigate('shared-forgot-password')" style="color: var(--primary); font-size: 12px; text-decoration: none; font-weight: 500;">Forgot password?</a>
              </div>
              <input type="password" class="form-control" value="••••••••••••">
            </div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
              <input type="checkbox" id="remember-me" checked>
              <label for="remember-me" style="font-size: 13px; color: var(--text-secondary);">Remember this device for 30 days</label>
            </div>
            <button class="btn btn-primary" style="width: 100%; padding: 12px;" onclick="navigate('student-dashboard'); showToast('Welcome back, Alex!')">Sign In to Learning Portal</button>

            <div style="margin: 20px 0; text-align: center; position: relative;">
              <hr style="border: 0; border-top: 1px solid var(--card-border);">
              <span style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: white; padding: 0 10px; font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Or continue with</span>
            </div>

            <div style="display: flex; gap: 10px;">
              <button class="btn btn-secondary" style="flex: 1;" onclick="showToast('SAML SSO Initiated')">🏛️ Institutional SAML</button>
              <button class="btn btn-secondary" style="flex: 1;" onclick="showToast('Google Workspace SSO')">🌐 Google</button>
            </div>
          </div>
        </div>
        """
    elif sid == "shared-forgot-password":
        body_html += """
        <div style="max-width: 440px; margin: 40px auto;">
          <div class="card" style="padding: 32px;">
            <h2 style="font-size: 20px; margin-bottom: 8px;">Reset your password</h2>
            <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Enter your verified institutional or personal email address to receive password recovery instructions.</p>
            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input type="email" class="form-control" placeholder="name@institution.edu">
            </div>
            <button class="btn btn-primary" style="width: 100%; margin-bottom: 14px;" onclick="navigate('shared-reset-password'); showToast('Reset link sent to email');">Send Recovery Link</button>
            <div style="text-align: center;">
              <a href="javascript:navigate('shared-login')" style="color: var(--primary); text-decoration: none; font-size: 13px; font-weight: 500;">← Back to Sign In</a>
            </div>
          </div>
        </div>
        """
    elif sid == "shared-reset-password":
        body_html += """
        <div style="max-width: 440px; margin: 40px auto;">
          <div class="card" style="padding: 32px;">
            <h2 style="font-size: 20px; margin-bottom: 8px;">Create new password</h2>
            <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Ensure your new password contains at least 8 characters, 1 number, and a symbol.</p>
            <div class="form-group">
              <label class="form-label">New Password</label>
              <input type="password" class="form-control" value="SecureP@ss2026">
            </div>
            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input type="password" class="form-control" value="SecureP@ss2026">
            </div>
            <div style="margin-bottom: 20px; padding: 10px; background: var(--success-light); border-radius: var(--radius-sm); font-size: 12px; color: var(--success);">
              ✅ Password strength: <strong>Strong</strong> (Entropy: 84 bits)
            </div>
            <button class="btn btn-primary" style="width: 100%;" onclick="navigate('shared-login'); showToast('Password updated successfully!');">Update Password & Sign In</button>
          </div>
        </div>
        """
    elif sid == "shared-notifications":
        body_html += """
        <div class="card">
          <div style="display: flex; gap: 8px; border-bottom: 1px solid var(--card-border); padding-bottom: 12px; margin-bottom: 16px;">
            <button class="btn btn-primary btn-sm">All (6)</button>
            <button class="btn btn-secondary btn-sm">Unread (2)</button>
            <button class="btn btn-secondary btn-sm">Exams & Proctors</button>
            <button class="btn btn-secondary btn-sm">Course Updates</button>
            <button class="btn btn-secondary btn-sm" style="margin-left: auto;" onclick="showToast('All notifications marked as read')">Mark All as Read</button>
          </div>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px; background: var(--primary-light); border-radius: var(--radius-sm); border-left: 4px solid var(--primary);">
              <div>
                <div style="font-weight: 600; color: var(--text-primary); font-size: 13.5px;">🎓 Final Proctored Exam Scheduled</div>
                <div style="color: var(--text-secondary); font-size: 12.5px;">Your Final Proctored Exam for 'Advanced Full Stack AI Engineering' opens tomorrow at 10:00 AM.</div>
              </div>
              <div style="text-align: right;">
                <span class="badge badge-primary">High Priority</span>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">10 mins ago</div>
              </div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px; background: white; border: 1px solid var(--card-border); border-radius: var(--radius-sm);">
              <div>
                <div style="font-weight: 600; color: var(--text-primary); font-size: 13.5px;">✅ Video Completion Milestone Saved</div>
                <div style="color: var(--text-secondary); font-size: 12.5px;">Chapter 4.2 'Vector Database Indexing' reached 100% completion. Monotonic state locked.</div>
              </div>
              <div style="text-align: right;">
                <span class="badge badge-success">Milestone</span>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">2 hours ago</div>
              </div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px; background: white; border: 1px solid var(--card-border); border-radius: var(--radius-sm);">
              <div>
                <div style="font-weight: 600; color: var(--text-primary); font-size: 13.5px;">🏛️ Institutional Package Renewal Approved</div>
                <div style="color: var(--text-secondary); font-size: 12.5px;">Apex Institute of Technology renewed 250 student seats for Academic Session 2026–2027.</div>
              </div>
              <div style="text-align: right;">
                <span class="badge badge-neutral">Institutional</span>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Yesterday</div>
              </div>
            </div>
          </div>
        </div>
        """
    elif sid == "shared-user-profile":
        body_html += """
        <div class="grid-3">
          <div class="card" style="text-align: center;">
            <div class="user-avatar" style="width: 80px; height: 80px; font-size: 28px; margin: 0 auto 16px auto;">AJ</div>
            <h2 style="font-size: 18px;">Alex Johnson</h2>
            <p style="color: var(--text-secondary); font-size: 13px;">alex.johnson@apextech.edu</p>
            <div style="margin: 12px 0;"><span class="badge badge-primary">Institutional Student</span></div>
            <p style="font-size: 12px; color: var(--text-muted);">Apex Institute of Technology<br>Department of Computer Science</p>
            <hr style="margin: 16px 0; border: 0; border-top: 1px solid var(--card-border);">
            <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="showToast('Upload dialog opened')">Upload New Avatar</button>
          </div>
          <div class="card" style="grid-column: span 2;">
            <h3 class="card-title" style="margin-bottom: 16px;">Personal Information</h3>
            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">First Name</label>
                <input type="text" class="form-control" value="Alex">
              </div>
              <div class="form-group">
                <label class="form-label">Last Name</label>
                <input type="text" class="form-control" value="Johnson">
              </div>
              <div class="form-group">
                <label class="form-label">Student ID / Roll No</label>
                <input type="text" class="form-control" value="APEX-2024-CS-0418" disabled>
              </div>
              <div class="form-group">
                <label class="form-label">Contact Number</label>
                <input type="text" class="form-control" value="+91 98765 43210">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Bio / Academic Interests</label>
              <textarea class="form-control">Junior year Computer Science student specializing in Large Language Models, Distributed Systems, and Full Stack Architecture.</textarea>
            </div>
            <button class="btn btn-primary" onclick="showToast('Profile information saved!')">Save Profile Changes</button>
          </div>
        </div>
        """
    elif sid == "shared-account-settings":
        body_html += """
        <div class="card" style="max-width: 800px;">
          <h3 class="card-title" style="margin-bottom: 16px;">Account Preferences</h3>
          <div class="form-group">
            <label class="form-label">Display Language</label>
            <select class="form-control">
              <option selected>English (United States)</option>
              <option>English (United Kingdom)</option>
              <option>Spanish (Español)</option>
              <option>French (Français)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Timezone</label>
            <select class="form-control">
              <option selected>(GMT+05:30) India Standard Time (Kolkata)</option>
              <option>(GMT+00:00) UTC</option>
              <option>(GMT-05:00) Eastern Time (US & Canada)</option>
              <option>(GMT-08:00) Pacific Time (US & Canada)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Email Notification Digests</label>
            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px;">
              <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
                <input type="checkbox" checked> Send instant email when proctored exam grade is posted
              </label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
                <input type="checkbox" checked> Weekly course progress digest
              </label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
                <input type="checkbox"> Career placement job alert emails
              </label>
            </div>
          </div>
          <button class="btn btn-primary" onclick="showToast('Preferences updated')">Save Preferences</button>
        </div>
        """
    elif sid == "shared-security-settings":
        body_html += """
        <div class="card" style="max-width: 800px;">
          <h3 class="card-title" style="margin-bottom: 16px;">Two-Factor Authentication (2FA)</h3>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px; background: #F8FAFC; border: 1px solid var(--card-border); border-radius: var(--radius-sm); margin-bottom: 24px;">
            <div>
              <div style="font-weight: 600;">Authenticator App (TOTP)</div>
              <div style="font-size: 12.5px; color: var(--text-secondary);">Use Google Authenticator or 1Password to protect your account during exam logins.</div>
            </div>
            <button class="btn btn-outline-primary btn-sm" onclick="showToast('2FA setup QR generated')">Configure 2FA</button>
          </div>

          <h3 class="card-title" style="margin-bottom: 16px;">Active Sessions</h3>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Device & Browser</th>
                  <th>IP Address</th>
                  <th>Location</th>
                  <th>Last Active</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>💻 Chrome on Windows 11 (Current)</td>
                  <td>122.161.49.210</td>
                  <td>New Delhi, India</td>
                  <td><span class="badge badge-success">Online</span></td>
                  <td>-</td>
                </tr>
                <tr>
                  <td>📱 Safari on iPhone 15 Pro</td>
                  <td>49.36.18.94</td>
                  <td>New Delhi, India</td>
                  <td>3 hours ago</td>
                  <td><button class="btn btn-danger btn-sm" onclick="showToast('Session terminated')">Revoke</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        """
    elif sid == "admin-dashboard":
        body_html += """
        <div class="grid-4">
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Total Revenue</span>
              <div class="stat-icon purple">₹</div>
            </div>
            <div class="stat-value">₹48,24,950</div>
            <div class="stat-trend positive">↑ 18.4% <span class="stat-trend-context">vs last month</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Active Students</span>
              <div class="stat-icon blue">🎓</div>
            </div>
            <div class="stat-value">14,820</div>
            <div class="stat-trend positive">↑ 8.2% <span class="stat-trend-context">new enrollments</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Total Courses</span>
              <div class="stat-icon green">📚</div>
            </div>
            <div class="stat-value">128</div>
            <div class="stat-trend positive">↑ 12 <span class="stat-trend-context">published this term</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Partner Colleges</span>
              <div class="stat-icon amber">🏛️</div>
            </div>
            <div class="stat-value">42</div>
            <div class="stat-trend positive">↑ 4 <span class="stat-trend-context">new MOUs signed</span></div>
          </div>
        </div>

        <div class="grid-3">
          <div class="card" style="grid-column: span 2;">
            <div class="card-header">
              <h3 class="card-title">Enrollment & Revenue Growth (2026)</h3>
              <span class="badge badge-success">Platform Active</span>
            </div>
            <div style="height: 220px; display: flex; align-items: flex-end; gap: 14px; padding: 20px 10px; background: #F8FAFC; border-radius: var(--radius-sm);">
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 90px; background: #635BFF; border-radius: 4px;"></div>
                <span style="font-size: 11px; color: var(--text-muted);">Jun</span>
              </div>
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 115px; background: #635BFF; border-radius: 4px;"></div>
                <span style="font-size: 11px; color: var(--text-muted);">Jul</span>
              </div>
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 140px; background: #635BFF; border-radius: 4px;"></div>
                <span style="font-size: 11px; color: var(--text-muted);">Aug</span>
              </div>
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 165px; background: #635BFF; border-radius: 4px;"></div>
                <span style="font-size: 11px; color: var(--text-muted);">Sep</span>
              </div>
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 190px; background: #635BFF; border-radius: 4px;"></div>
                <span style="font-size: 11px; color: var(--text-muted);">Oct</span>
              </div>
              <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div style="width: 100%; height: 210px; background: linear-gradient(180deg, #635BFF, #4F46E5); border-radius: 4px;"></div>
                <span style="font-size: 11px; font-weight: 700; color: var(--primary);">Nov</span>
              </div>
            </div>
          </div>

          <div class="card">
            <h3 class="card-title" style="margin-bottom: 14px;">Institutional Quotas</h3>
            <div style="display: flex; flex-direction: column; gap: 14px;">
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <span>Apex Tech Institute</span>
                  <span style="font-weight: 600;">1,280 / 1,500 Seats</span>
                </div>
                <div class="player-progress-bar" style="height: 8px;"><div class="player-progress-fill" style="width: 85%;"></div></div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <span>National Science Academy</span>
                  <span style="font-weight: 600;">890 / 1,000 Seats</span>
                </div>
                <div class="player-progress-bar" style="height: 8px;"><div class="player-progress-fill" style="width: 89%;"></div></div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <span>Global Polytechnic</span>
                  <span style="font-weight: 600;">450 / 500 Seats</span>
                </div>
                <div class="player-progress-bar" style="height: 8px;"><div class="player-progress-fill" style="width: 90%;"></div></div>
              </div>
            </div>
            <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 18px;" onclick="navigate('admin-billing')">View Full Ledger</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Recent Courses & Approvals Queue</h3>
            <button class="btn btn-primary btn-sm" onclick="navigate('admin-all-courses')">View All Courses</button>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Course Code & Title</th>
                  <th>Category</th>
                  <th>Individual Price</th>
                  <th>Institutional Rate</th>
                  <th>Enrolled</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>CS-AI-401</strong>: Advanced Full Stack AI Engineering</td>
                  <td>Artificial Intelligence</td>
                  <td>₹999</td>
                  <td>₹499 / seat</td>
                  <td>1,842</td>
                  <td><span class="badge badge-success">Published</span></td>
                  <td><button class="btn btn-secondary btn-sm" onclick="navigate('admin-create-basic')">Edit</button></td>
                </tr>
                <tr>
                  <td><strong>DEV-302</strong>: Cloud Native Microservices Architecture</td>
                  <td>DevOps & Cloud</td>
                  <td>₹1,499</td>
                  <td>₹599 / seat</td>
                  <td>940</td>
                  <td><span class="badge badge-success">Published</span></td>
                  <td><button class="btn btn-secondary btn-sm" onclick="navigate('admin-create-basic')">Edit</button></td>
                </tr>
                <tr>
                  <td><strong>SEC-501</strong>: Ethical Hacking & Red Teaming</td>
                  <td>Cybersecurity</td>
                  <td>₹1,999</td>
                  <td>₹750 / seat</td>
                  <td>320</td>
                  <td><span class="badge badge-warning">In Review</span></td>
                  <td><button class="btn btn-primary btn-sm" onclick="navigate('admin-course-requests')">Review</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        """
    elif sid == "admin-create-basic":
        body_html += """
        <div class="card" style="max-width: 900px;">
          <h3 class="card-title" style="margin-bottom: 16px;">Course Overview & Basic Information</h3>
          <div class="grid-2">
            <div class="form-group">
              <label class="form-label">Course Title *</label>
              <input type="text" class="form-control" value="Advanced Full Stack AI Engineering">
            </div>
            <div class="form-group">
              <label class="form-label">Course Code *</label>
              <input type="text" class="form-control" value="CS-AI-401">
            </div>
            <div class="form-group">
              <label class="form-label">Primary Category</label>
              <select class="form-control">
                <option selected>Artificial Intelligence & Data Science</option>
                <option>Full Stack Web Development</option>
                <option>Cloud Infrastructure & DevOps</option>
                <option>Cybersecurity & Forensics</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Difficulty Level</label>
              <select class="form-control">
                <option>Beginner</option>
                <option selected>Intermediate to Advanced</option>
                <option>Professional Specialist</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Short Summary (Shown on marketplace cards)</label>
            <input type="text" class="form-control" value="Master modern full-stack development, LangChain, vector databases, and autonomous AI agents.">
          </div>
          <div class="form-group">
            <label class="form-label">Comprehensive Course Description</label>
            <textarea class="form-control" rows="4">An intensive industrial certification curriculum covering end-to-end LLM orchestration, FastAPI microservices, React 19 frontend integration, and enterprise AI security practices.</textarea>
          </div>
          <div class="form-group">
            <label class="form-label">Course Thumbnail</label>
            <div style="border: 2px dashed #CBD5E1; border-radius: var(--radius); padding: 24px; text-align: center; background: #F8FAFC;">
              <div style="font-size: 32px; margin-bottom: 8px;">🖼️</div>
              <div style="font-weight: 600; font-size: 13.5px;">Click to upload or drag image file here</div>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">PNG, JPG, or WEBP up to 5MB (16:9 ratio recommended)</div>
              <div style="margin-top: 12px;"><span class="badge badge-success">✓ Preview: thumbnail_ai_engineering.png</span></div>
            </div>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px;">
            <button class="btn btn-secondary" onclick="navigate('admin-all-courses')">Cancel</button>
            <button class="btn btn-primary" onclick="navigate('admin-create-pricing')">Next: Course Pricing →</button>
          </div>
        </div>
        """
    elif sid == "admin-create-pricing":
        body_html += """
        <div class="card" style="max-width: 900px;">
          <h3 class="card-title" style="margin-bottom: 16px;">Dual Pricing Model: B2C & Institutional B2B</h3>
          
          <div style="background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: var(--radius); padding: 16px; margin-bottom: 24px;">
            <div style="font-weight: 700; color: var(--primary); margin-bottom: 4px;">📌 Important Business Rule</div>
            <div style="font-size: 13px; color: var(--text-primary);">Individual students pay direct retail checkout price. Institutional students access this course through their college active seat package without any individual checkout!</div>
          </div>

          <div class="grid-2">
            <!-- Individual Pricing Card -->
            <div style="border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px;">
              <h4 style="font-size: 15px; margin-bottom: 12px;">Individual Retail (B2C)</h4>
              <div class="form-group">
                <label class="form-label">Regular List Price (₹)</label>
                <input type="number" class="form-control" value="1499">
              </div>
              <div class="form-group">
                <label class="form-label">Discounted Selling Price (₹)</label>
                <input type="number" class="form-control" value="999">
              </div>
              <div class="form-group">
                <label class="form-label">Tax / GST (18%)</label>
                <input type="text" class="form-control" value="Inclusive in final checkout" disabled>
              </div>
            </div>

            <!-- Institutional Bulk Tier Card -->
            <div style="border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px; background: #FAFCFE;">
              <h4 style="font-size: 15px; margin-bottom: 12px;">Institutional Bulk Pricing (B2B)</h4>
              <div class="form-group">
                <label class="form-label">Base Rate Per Seat (₹)</label>
                <input type="number" id="base-rate-input" class="form-control" value="499" oninput="calculateInstPricing()">
              </div>
              <div class="form-group">
                <label class="form-label">Minimum Purchase Quantity</label>
                <input type="number" class="form-control" value="20" disabled>
              </div>
              <div class="form-group">
                <label class="form-label">Sample Tier Calculator</label>
                <div style="display: flex; gap: 8px;">
                  <input type="number" id="calc-seats-input" class="form-control" value="50" oninput="calculateInstPricing()" placeholder="Seats">
                  <div style="padding: 10px 14px; background: white; border: 1px solid var(--card-border); border-radius: var(--radius-sm); font-weight: 700; white-space: nowrap; color: var(--primary);" id="calc-result-display">₹24,950 total</div>
                </div>
              </div>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; margin-top: 24px;">
            <button class="btn btn-secondary" onclick="navigate('admin-create-basic')">← Previous: Basic Info</button>
            <button class="btn btn-primary" onclick="navigate('admin-create-modules')">Next: Modules & Chapters →</button>
          </div>
        </div>
        """
    elif sid == "admin-create-modules":
        body_html += """
        <div class="card" style="max-width: 900px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">Curriculum Structure: Modules & Chapters</h3>
              <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">Organize video lectures, notes, code walkthroughs, and lab exercises.</p>
            </div>
            <button class="btn btn-custom-green btn-sm" onclick="showAddModuleModal()">+ Add New Module</button>
          </div>

          <!-- Module 1 -->
          <div style="border: 1px solid var(--card-border); border-radius: var(--radius); margin-bottom: 16px; overflow: hidden;">
            <div style="background: #F8FAFC; padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--card-border);">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-weight: 700; color: var(--primary);">Module 1:</span>
                <span style="font-weight: 600;">Foundations of Modern AI Architecture</span>
                <span class="badge badge-neutral" style="font-size: 11px;">4 Chapters • 1h 45m</span>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-secondary btn-sm" onclick="showAddChapterModal('Module 1')">+ Add Chapter</button>
                <button class="btn btn-secondary btn-sm">Edit</button>
              </div>
            </div>
            <div style="padding: 10px 18px;">
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #F1F5F9;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span>🎬</span>
                  <span style="font-size: 13.5px;">1.1 Evolution of Transformer Models & Attention</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; font-size: 12.5px; color: var(--text-secondary);">
                  <span>18m 42s</span>
                  <span class="badge badge-success">HD 1080p</span>
                </div>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #F1F5F9;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span>🎬</span>
                  <span style="font-size: 13.5px;">1.2 LLM Tokenization, Embeddings & Context Windows</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; font-size: 12.5px; color: var(--text-secondary);">
                  <span>24m 10s</span>
                  <span class="badge badge-success">HD 1080p</span>
                </div>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span>📄</span>
                  <span style="font-size: 13.5px;">1.3 Reference Architecture Blueprint (PDF Guide)</span>
                </div>
                <span class="badge badge-neutral">Downloadable PDF</span>
              </div>
            </div>
          </div>

          <!-- Module 2 -->
          <div style="border: 1px solid var(--card-border); border-radius: var(--radius); margin-bottom: 24px; overflow: hidden;">
            <div style="background: #F8FAFC; padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--card-border);">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-weight: 700; color: var(--primary);">Module 2:</span>
                <span style="font-weight: 600;">Vector Databases & Semantic Retrieval (RAG)</span>
                <span class="badge badge-neutral" style="font-size: 11px;">5 Chapters • 2h 20m</span>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-secondary btn-sm" onclick="showAddChapterModal('Module 2')">+ Add Chapter</button>
                <button class="btn btn-secondary btn-sm">Edit</button>
              </div>
            </div>
            <div style="padding: 10px 18px;">
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #F1F5F9;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span>🎬</span>
                  <span style="font-size: 13.5px;">2.1 Pinecone, Milvus & pgvector Setup</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; font-size: 12.5px; color: var(--text-secondary);">
                  <span>32m 05s</span>
                  <span class="badge badge-success">HD 1080p</span>
                </div>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span>🎬</span>
                  <span style="font-size: 13.5px;">2.2 Hybrid Search with BM25 & Dense Vectors</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; font-size: 12.5px; color: var(--text-secondary);">
                  <span>28m 18s</span>
                  <span class="badge badge-success">HD 1080p</span>
                </div>
              </div>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between;">
            <button class="btn btn-secondary" onclick="navigate('admin-create-pricing')">← Previous: Pricing</button>
            <button class="btn btn-primary" onclick="navigate('admin-create-assessments')">Next: Tests & Assessments →</button>
          </div>
        </div>
        """
    elif sid == "admin-create-assessments":
        body_html += """
        <div class="card" style="max-width: 900px;">
          <h3 class="card-title" style="margin-bottom: 16px;">Assessment Strategy & Passing Thresholds</h3>
          <div class="table-container" style="margin-bottom: 24px;">
            <table>
              <thead>
                <tr>
                  <th>Assessment Name</th>
                  <th>Associated Milestone</th>
                  <th>Questions</th>
                  <th>Time Limit</th>
                  <th>Pass Mark</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Chapter 1.2 Knowledge Check</td>
                  <td>Module 1, Chapter 2</td>
                  <td>5 MCQs</td>
                  <td>10 mins</td>
                  <td>70%</td>
                  <td><span class="badge badge-success">Configured</span></td>
                </tr>
                <tr>
                  <td>Module 1 Milestone Assessment</td>
                  <td>Module 1 Completion</td>
                  <td>15 MCQs</td>
                  <td>30 mins</td>
                  <td>75%</td>
                  <td><span class="badge badge-success">Configured</span></td>
                </tr>
                <tr>
                  <td>Module 2 Practical Coding Test</td>
                  <td>Module 2 Completion</td>
                  <td>2 Coding Labs</td>
                  <td>45 mins</td>
                  <td>80%</td>
                  <td><span class="badge badge-success">Configured</span></td>
                </tr>
                <tr>
                  <td>Final Proctored Examination</td>
                  <td>Full Course Certification</td>
                  <td>25 Questions + AI Proctor</td>
                  <td>60 mins</td>
                  <td>75%</td>
                  <td><span class="badge badge-primary">Proctored</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <button class="btn btn-secondary" onclick="navigate('admin-create-modules')">← Previous: Modules</button>
            <button class="btn btn-primary" onclick="navigate('admin-review-publish')">Next: Review & Publish →</button>
          </div>
        </div>
        """
    elif sid == "admin-review-publish":
        body_html += """
        <div class="card" style="max-width: 900px;">
          <div style="background: var(--success-light); border: 1px solid rgba(22, 163, 123, 0.2); border-radius: var(--radius); padding: 18px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <h4 style="color: var(--success); font-size: 16px;">Ready for Publication!</h4>
              <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">All 5 steps validated successfully. No missing dependencies or broken assets.</p>
            </div>
            <span class="badge badge-success" style="font-size: 12px; padding: 6px 12px;">Pre-flight Checks Passed</span>
          </div>

          <div class="grid-2">
            <div style="border: 1px solid var(--card-border); border-radius: var(--radius); padding: 18px;">
              <h4 style="font-size: 14px; color: var(--text-secondary); text-transform: uppercase;">Curriculum Scope</h4>
              <div style="font-size: 20px; font-weight: 700; margin: 8px 0;">2 Modules • 9 Chapters</div>
              <ul style="font-size: 13px; color: var(--text-secondary); margin-left: 18px; line-height: 1.8;">
                <li>HD Transcoded Video Lectures</li>
                <li>Downloadable Architectural Blueprints</li>
                <li>Module 1 & 2 Milestone Tests</li>
                <li>Final AI Proctored Examination</li>
              </ul>
            </div>
            <div style="border: 1px solid var(--card-border); border-radius: var(--radius); padding: 18px;">
              <h4 style="font-size: 14px; color: var(--text-secondary); text-transform: uppercase;">Pricing Configuration</h4>
              <div style="font-size: 20px; font-weight: 700; margin: 8px 0; color: var(--primary);">₹999 B2C / ₹499 B2B</div>
              <ul style="font-size: 13px; color: var(--text-secondary); margin-left: 18px; line-height: 1.8;">
                <li>Direct Individual Checkout enabled</li>
                <li>Institutional Seat Quota Licensing enabled</li>
                <li>GST 18% Compliant Tax Invoicing</li>
                <li>No forced subscriptions for students</li>
              </ul>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; margin-top: 28px;">
            <button class="btn btn-secondary" onclick="navigate('admin-create-assessments')">← Previous: Assessments</button>
            <div style="display: flex; gap: 10px;">
              <button class="btn btn-secondary" onclick="showToast('Course saved to Drafts')">Save as Draft</button>
              <button class="btn btn-primary" onclick="showToast('Course Published to Catalog!'); navigate('admin-all-courses')">🚀 Publish Course to Catalog</button>
            </div>
          </div>
        </div>
        """
    elif sid == "head-dashboard":
        body_html += """
        <div style="background: white; border: 1px solid var(--card-border); border-radius: var(--radius); padding: 22px; margin-bottom: 22px; display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div style="width: 50px; height: 50px; background: #EEF2FF; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px;">🏛️</div>
            <div>
              <h2 style="font-size: 20px;">Apex Institute of Technology</h2>
              <p style="color: var(--text-secondary); font-size: 13px;">Enterprise Campus License • ID: INST-8821 • Valid through Dec 31, 2026</p>
            </div>
          </div>
          <button class="btn btn-primary" onclick="navigate('head-purchase-request')">Requisition Additional Seats</button>
        </div>

        <div class="grid-4">
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Enrolled Students</span>
              <div class="stat-icon blue">🎓</div>
            </div>
            <div class="stat-value">1,420</div>
            <div class="stat-trend positive">↑ 140 <span class="stat-trend-context">this month</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Allocated Seats</span>
              <div class="stat-icon purple">💺</div>
            </div>
            <div class="stat-value">1,280 / 1,500</div>
            <div class="stat-trend positive">85.3% <span class="stat-trend-context">utilization</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Active Packages</span>
              <div class="stat-icon green">📦</div>
            </div>
            <div class="stat-value">6</div>
            <div class="stat-trend positive"><span class="stat-trend-context">All active & valid</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Avg Pass Rate</span>
              <div class="stat-icon amber">🏆</div>
            </div>
            <div class="stat-value">91.4%</div>
            <div class="stat-trend positive">↑ 4.2% <span class="stat-trend-context">in final exams</span></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Active Institutional Packages</h3>
              <button class="btn btn-secondary btn-sm" onclick="navigate('head-my-purchases')">View All</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 14px;">
              <div style="padding: 12px; background: #F8FAFC; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
                <div style="display: flex; justify-content: space-between; font-weight: 600; font-size: 13.5px; margin-bottom: 6px;">
                  <span>Full Stack AI Engineering 2026</span>
                  <span class="badge badge-success">480 / 500 Seats Used</span>
                </div>
                <div class="player-progress-bar" style="height: 6px;"><div class="player-progress-fill" style="width: 96%;"></div></div>
              </div>
              <div style="padding: 12px; background: #F8FAFC; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
                <div style="display: flex; justify-content: space-between; font-weight: 600; font-size: 13.5px; margin-bottom: 6px;">
                  <span>Cloud DevOps & Kubernetes</span>
                  <span class="badge badge-success">350 / 400 Seats Used</span>
                </div>
                <div class="player-progress-bar" style="height: 6px;"><div class="player-progress-fill" style="width: 87.5%;"></div></div>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <h3 class="card-title">Quick Student Actions</h3>
              <button class="btn btn-primary btn-sm" onclick="navigate('head-seat-management')">Manage Seats</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <button class="btn btn-secondary" style="justify-content: flex-start; padding: 12px;" onclick="showToast('CSV Roster Upload Dialog Opened')">📤 Bulk Import Student Roster (CSV)</button>
              <button class="btn btn-secondary" style="justify-content: flex-start; padding: 12px;" onclick="navigate('head-batch-management')">👥 Create New Student Academic Cohort</button>
              <button class="btn btn-secondary" style="justify-content: flex-start; padding: 12px;" onclick="navigate('head-reports')">📊 Download UGC/NAAC Accreditation Report</button>
            </div>
          </div>
        </div>
        """
    elif sid == "student-dashboard":
        body_html += """
        <!-- Institutional Access Banner -->
        <div style="background: linear-gradient(135deg, #4F46E5, #635BFF); color: white; border-radius: var(--radius); padding: 24px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; box-shadow: var(--shadow-md);">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
              <span class="badge" style="background: rgba(255, 255, 255, 0.2); color: white;">🏛️ Institutional Access Active</span>
              <span style="font-size: 12px; opacity: 0.9;">Apex Institute of Technology</span>
            </div>
            <h2 style="color: white; font-size: 22px; margin-bottom: 4px;">Welcome back, Alex!</h2>
            <p style="opacity: 0.9; font-size: 13.5px;">You have full institutional entitlement to all enrolled technical courses and proctored examinations.</p>
          </div>
          <button class="btn" style="background: white; color: var(--primary); font-weight: 700;" onclick="navigate('student-learning-player')">▶ Resume Learning</button>
        </div>

        <div class="grid-4">
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Enrolled Courses</span>
              <div class="stat-icon blue">📚</div>
            </div>
            <div class="stat-value">3</div>
            <div class="stat-trend positive"><span class="stat-trend-context">Institutional License</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Hours Learned</span>
              <div class="stat-icon purple">⏱️</div>
            </div>
            <div class="stat-value">38.4h</div>
            <div class="stat-trend positive">↑ 4.2h <span class="stat-trend-context">this week</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Completed Chapters</span>
              <div class="stat-icon green">✅</div>
            </div>
            <div class="stat-value">24 / 32</div>
            <div class="stat-trend positive">75% <span class="stat-trend-context">overall rate</span></div>
          </div>
          <div class="stat-card">
            <div class="stat-card-top">
              <span class="stat-label">Earned Certificates</span>
              <div class="stat-icon amber">🏆</div>
            </div>
            <div class="stat-value">2</div>
            <div class="stat-trend positive"><span class="stat-trend-context">Verified Credentials</span></div>
          </div>
        </div>

        <!-- In-Progress Course Card with 100% Progress Milestone Proof -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">Currently Enrolled Courses</h3>
              <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">Pick up right where you left off</p>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="navigate('student-my-courses')">View My Library</button>
          </div>
          
          <div style="border: 1px solid var(--card-border); border-radius: var(--radius); padding: 18px; display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; background: #FAFCFE;">
            <div style="display: flex; align-items: center; gap: 16px;">
              <div style="width: 70px; height: 70px; background: #EEF2FF; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 32px;">🤖</div>
              <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                  <span class="badge badge-primary">Institutional Access</span>
                  <span class="badge badge-success">Chapter 4.2: 100% Complete</span>
                </div>
                <h4 style="font-size: 16px; font-weight: 700;">CS-AI-401: Advanced Full Stack AI Engineering</h4>
                <p style="font-size: 13px; color: var(--text-secondary);">Module 4: Autonomous Multi-Agent Swarms & Evaluation</p>
              </div>
            </div>
            <div style="min-width: 220px;">
              <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px; font-weight: 600;">
                <span>Total Course Progress</span>
                <span style="color: var(--primary);">88%</span>
              </div>
              <div class="player-progress-bar" style="height: 8px;"><div class="player-progress-fill" style="width: 88%;"></div></div>
            </div>
            <button class="btn btn-primary" onclick="navigate('student-learning-player')">Continue Learning →</button>
          </div>
        </div>
        """
    elif sid == "student-learning-player":
        body_html += """
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 22px;">
          <div>
            <!-- Video Player -->
            <div class="video-mockup-frame">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="badge" style="background: rgba(0,0,0,0.6); color: white;">4.2 Vector Database Indexing & HNSW</span>
                <span class="badge badge-success">Monotonic Progress: 100% Locked</span>
              </div>
              <div style="text-align: center; cursor: pointer;">
                <div style="width: 64px; height: 64px; background: rgba(99, 91, 255, 0.9); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto; font-size: 26px; box-shadow: 0 0 20px rgba(99, 91, 255, 0.6);">▶</div>
              </div>
              <div>
                <div class="player-progress-bar" style="margin-bottom: 8px;">
                  <div class="player-progress-fill" style="width: 100%;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; opacity: 0.9;">
                  <span>18:42 / 18:42 (100% Watched)</span>
                  <span>1080p HD • Speed 1.0x</span>
                </div>
              </div>
            </div>

            <!-- Video Tabs -->
            <div class="card" style="margin-top: 18px;">
              <div style="display: flex; gap: 12px; border-bottom: 1px solid var(--card-border); padding-bottom: 12px; margin-bottom: 16px;">
                <button class="btn btn-primary btn-sm">Overview & Notes</button>
                <button class="btn btn-secondary btn-sm" onclick="showToast('Discussion thread loaded')">Q&A Discussion (14)</button>
                <button class="btn btn-secondary btn-sm" onclick="showToast('Resource file downloaded')">Resources & Slides</button>
                <button class="btn btn-secondary btn-sm" onclick="navigate('student-ai-tutor')">🤖 Ask AI Tutor</button>
              </div>
              <h3 style="font-size: 16px; margin-bottom: 8px;">About This Chapter</h3>
              <p style="font-size: 13.5px; color: var(--text-secondary); line-height: 1.6;">In this lesson, we explore Hierarchical Navigable Small World (HNSW) graphs, metric distance spaces (Cosine, Euclidean, Dot Product), and how to optimize vector recall under millisecond latency requirements.</p>
            </div>
          </div>

          <!-- Curriculum Sidebar -->
          <div class="card" style="padding: 16px; max-height: 680px; overflow-y: auto;">
            <h3 class="card-title" style="margin-bottom: 12px;">Course Curriculum</h3>
            
            <div style="margin-bottom: 14px;">
              <div style="font-size: 12.5px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">MODULE 1: AI FOUNDATIONS</div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; background: var(--success-light); border-radius: 6px; font-size: 12.5px;">
                  <span>✓ 1.1 Transformer Models</span>
                  <span style="font-size: 11px; color: var(--success); font-weight: 700;">100%</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; background: var(--success-light); border-radius: 6px; font-size: 12.5px;">
                  <span>✓ 1.2 Embeddings & Tokens</span>
                  <span style="font-size: 11px; color: var(--success); font-weight: 700;">100%</span>
                </div>
              </div>
            </div>

            <div style="margin-bottom: 14px;">
              <div style="font-size: 12.5px; font-weight: 700; color: var(--primary); margin-bottom: 6px;">MODULE 2: VECTOR DATABASES</div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; background: var(--primary-light); border-radius: 6px; font-size: 12.5px; font-weight: 600; border-left: 3px solid var(--primary);">
                  <span>▶ 2.1 pgvector Setup</span>
                  <span style="font-size: 11px; color: var(--primary); font-weight: 700;">100%</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; background: white; border: 1px solid var(--card-border); border-radius: 6px; font-size: 12.5px;">
                  <span>🎬 2.2 Hybrid Search</span>
                  <span style="font-size: 11px; color: var(--text-muted);">28m</span>
                </div>
              </div>
            </div>

            <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--card-border);">
              <button class="btn btn-primary" style="width: 100%;" onclick="navigate('student-chapter-test')">Take Chapter 2 Test →</button>
            </div>
          </div>
        </div>
        """
    elif sid == "student-cam-mic-check":
        body_html += """
        <div class="card" style="max-width: 800px; margin: 0 auto;">
          <h3 class="card-title" style="margin-bottom: 8px;">Hardware & Environmental Pre-Flight Check</h3>
          <p style="font-size: 13.5px; color: var(--text-secondary); margin-bottom: 24px;">The AI Proctor verifies that your camera, microphone, internet bandwidth, and operating environment meet examination accreditation standards.</p>

          <div class="grid-2" style="margin-bottom: 24px;">
            <!-- Simulated Video Box -->
            <div style="background: #0F172A; border-radius: var(--radius); aspect-ratio: 4/3; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; overflow: hidden; border: 2px solid #10B981;">
              <div style="font-size: 48px; margin-bottom: 8px;">👤</div>
              <div style="width: 160px; height: 160px; border: 2px dashed #10B981; border-radius: 8px; position: absolute; pointer-events: none;"></div>
              <span class="badge badge-success" style="position: absolute; bottom: 12px; left: 12px;">✅ Face Centered & Identified</span>
            </div>

            <!-- Checklist -->
            <div style="display: flex; flex-direction: column; gap: 12px; justify-content: center;">
              <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--success-light); border-radius: var(--radius-sm);">
                <span style="font-size: 18px;">📷</span>
                <div>
                  <div style="font-weight: 600; font-size: 13px;">Webcam Stream (1080p)</div>
                  <div style="font-size: 11.5px; color: var(--success);">Integrated HD Camera: Active</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--success-light); border-radius: var(--radius-sm);">
                <span style="font-size: 18px;">🎙️</span>
                <div>
                  <div style="font-weight: 600; font-size: 13px;">Microphone Input Level</div>
                  <div style="font-size: 11.5px; color: var(--success);">Optimal audio input detected (42 dB)</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--success-light); border-radius: var(--radius-sm);">
                <span style="font-size: 18px;">⚡</span>
                <div>
                  <div style="font-weight: 600; font-size: 13px;">Network Latency</div>
                  <div style="font-size: 11.5px; color: var(--success);">18ms ping • 84 Mbps download</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--success-light); border-radius: var(--radius-sm);">
                <span style="font-size: 18px;">🖥️</span>
                <div>
                  <div style="font-weight: 600; font-size: 13px;">Single Display Lock</div>
                  <div style="font-size: 11.5px; color: var(--success);">1 external monitor disconnected</div>
                </div>
              </div>
            </div>
          </div>

          <div style="text-align: right;">
            <button class="btn btn-success btn-lg" onclick="navigate('student-proctored-exam')">All Checks Passed • Enter Exam Room 🔒</button>
          </div>
        </div>
        """
    elif sid == "student-proctored-exam":
        body_html += """
        <div style="border: 2px solid #EF4444; border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow-lg);">
          <!-- Top Proctor Bar -->
          <div class="proctored-header">
            <div style="display: flex; align-items: center; gap: 12px;">
              <span class="badge badge-danger" style="font-size: 12px;">🔴 LIVE PROCTORED SESSION</span>
              <span style="font-size: 13.5px; font-weight: 600;">CS-AI-401 Final Examination</span>
            </div>
            <div class="proctored-timer">
              <span>⏱️ Time Remaining:</span>
              <span id="exam-timer">44:18</span>
            </div>
            <div style="font-size: 12.5px; color: #9CA3AF;">Autosaved: Just now</div>
          </div>

          <div style="display: grid; grid-template-columns: 3fr 1fr; background: white; min-height: 520px;">
            <!-- Question Body -->
            <div style="padding: 28px; border-right: 1px solid var(--card-border);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
                <span style="font-size: 13px; font-weight: 700; color: var(--primary);">QUESTION 4 OF 25</span>
                <button class="btn btn-secondary btn-sm" onclick="showToast('Flagged for review')">🚩 Mark for Review</button>
              </div>

              <h3 style="font-size: 17px; margin-bottom: 14px; line-height: 1.5;">Which of the following index strategies is optimal for low-latency approximate nearest neighbor (ANN) retrieval in high-dimensional vector spaces?</h3>

              <div style="display: flex; flex-direction: column; gap: 10px; margin: 20px 0;">
                <label style="display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--card-border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s ease;" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--card-border)'">
                  <input type="radio" name="exam-q4" checked>
                  <span style="font-size: 14px;"><strong>A)</strong> HNSW (Hierarchical Navigable Small World) with M=16 and efSearch=64</span>
                </label>
                <label style="display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--card-border); border-radius: var(--radius-sm); cursor: pointer;" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--card-border)'">
                  <input type="radio" name="exam-q4">
                  <span style="font-size: 14px;"><strong>B)</strong> Flat Exact Inverted File Scan (IVFFlat with nlist=1)</span>
                </label>
                <label style="display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--card-border); border-radius: var(--radius-sm); cursor: pointer;" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--card-border)'">
                  <input type="radio" name="exam-q4">
                  <span style="font-size: 14px;"><strong>C)</strong> B-Tree indexing on normalized vectors</span>
                </label>
                <label style="display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--card-border); border-radius: var(--radius-sm); cursor: pointer;" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--card-border)'">
                  <input type="radio" name="exam-q4">
                  <span style="font-size: 14px;"><strong>D)</strong> Linear Euclidean Brute-Force scan</span>
                </label>
              </div>

              <div style="display: flex; justify-content: space-between; margin-top: 30px;">
                <button class="btn btn-secondary">← Previous Question</button>
                <button class="btn btn-primary" onclick="showToast('Answer recorded')">Save & Next Question →</button>
              </div>
            </div>

            <!-- Proctor Stream & Palette -->
            <div style="padding: 20px; background: #F8FAFC; display: flex; flex-direction: column; gap: 20px;">
              <div style="display: flex; flex-direction: column; align-items: center;">
                <div class="webcam-stream-mock">
                  <div style="font-size: 28px;">👤</div>
                  <div style="position: absolute; top: 4px; right: 4px; width: 8px; height: 8px; background: #EF4444; border-radius: 50%;"></div>
                  <span style="position: absolute; bottom: 2px; font-size: 9px; color: #10B981; font-weight: 700;">AI PROCTOR ACTIVE</span>
                </div>
                <span style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">Webcam Feed Monitored</span>
              </div>

              <div>
                <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 8px;">QUESTION PALETTE</div>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px;">
                  <button class="btn btn-success btn-sm" style="padding: 4px;">1</button>
                  <button class="btn btn-success btn-sm" style="padding: 4px;">2</button>
                  <button class="btn btn-success btn-sm" style="padding: 4px;">3</button>
                  <button class="btn btn-primary btn-sm" style="padding: 4px;">4</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">5</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">6</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">7</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">8</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">9</button>
                  <button class="btn btn-secondary btn-sm" style="padding: 4px;">10</button>
                </div>
              </div>

              <div style="margin-top: auto;">
                <button class="btn btn-danger" style="width: 100%;" onclick="navigate('student-exam-results')">Finish & Submit Exam</button>
              </div>
            </div>
          </div>
        </div>
        """
    elif sid == "student-exam-results":
        body_html += """
        <div class="card" style="max-width: 760px; margin: 0 auto; text-align: center; padding: 36px;">
          <div style="width: 72px; height: 72px; background: var(--success-light); color: var(--success); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 36px; margin: 0 auto 16px auto;">🏆</div>
          <span class="badge badge-success" style="font-size: 13px; padding: 6px 14px;">Official Proctored Result</span>
          <h2 style="font-size: 26px; margin: 12px 0 6px 0;">Congratulations, Alex! You Passed!</h2>
          <p style="color: var(--text-secondary); font-size: 14px; margin-bottom: 24px;">Your examination session was authenticated and validated by AI proctoring logs.</p>

          <div class="grid-3" style="text-align: left; margin-bottom: 28px;">
            <div style="background: #F8FAFC; border: 1px solid var(--card-border); border-radius: var(--radius); padding: 16px;">
              <span style="font-size: 12px; color: var(--text-secondary);">FINAL SCORE</span>
              <div style="font-size: 28px; font-weight: 800; color: var(--success);">92 / 100</div>
              <span style="font-size: 12px; color: var(--success);">Distinction Honors</span>
            </div>
            <div style="background: #F8FAFC; border: 1px solid var(--card-border); border-radius: var(--radius); padding: 16px;">
              <span style="font-size: 12px; color: var(--text-secondary);">PASSING CRITERIA</span>
              <div style="font-size: 28px; font-weight: 800; color: var(--text-primary);">75%</div>
              <span style="font-size: 12px; color: var(--text-muted);">Exceeded by +17%</span>
            </div>
            <div style="background: #F8FAFC; border: 1px solid var(--card-border); border-radius: var(--radius); padding: 16px;">
              <span style="font-size: 12px; color: var(--text-secondary);">PROCTOR INTEGRITY</span>
              <div style="font-size: 28px; font-weight: 800; color: var(--primary);">100%</div>
              <span style="font-size: 12px; color: var(--primary);">0 Infractions</span>
            </div>
          </div>

          <div style="display: flex; justify-content: center; gap: 12px;">
            <button class="btn btn-primary btn-lg" onclick="navigate('student-certificate-view')">🎓 View & Download Verified Certificate</button>
            <button class="btn btn-secondary btn-lg" onclick="navigate('student-dashboard')">Return to Dashboard</button>
          </div>
        </div>
        """
    elif sid == "student-certificate-view":
        body_html += """
        <div class="card" style="max-width: 880px; margin: 0 auto; padding: 40px; border: 8px solid #F1F5F9; position: relative; background: #FFFFFF; box-shadow: var(--shadow-lg);">
          <div style="border: 2px solid #E2E8F0; padding: 36px; text-align: center; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
              <div style="font-weight: 800; font-size: 20px; color: var(--primary);">ExamLMS Academic Board</div>
              <div style="font-size: 12px; color: var(--text-muted);">Credential ID: CERT-2026-9812-AI</div>
            </div>

            <div style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.15em; color: var(--text-secondary); margin-bottom: 8px;">Certificate of Industrial Proficiency</div>
            <h1 style="font-size: 32px; color: var(--text-primary); margin-bottom: 12px; font-family: 'Plus Jakarta Sans', serif;">Alex Johnson</h1>
            <p style="font-size: 15px; color: var(--text-secondary); max-width: 600px; margin: 0 auto 24px auto;">has successfully fulfilled all curriculum, lab milestones, and the proctored examination for</p>
            <h2 style="font-size: 22px; color: var(--primary); margin-bottom: 24px;">Advanced Full Stack AI Engineering</h2>

            <div style="display: flex; justify-content: space-around; align-items: flex-end; margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0;">
              <div>
                <div style="font-family: cursive; font-size: 20px; color: #1E293B;">Dr. Sarah Jenkins</div>
                <div style="border-top: 1px solid #94A3B8; width: 140px; margin: 4px auto;"></div>
                <div style="font-size: 11px; color: var(--text-muted);">Director of Academic Accreditation</div>
              </div>
              <div style="width: 70px; height: 70px; border-radius: 50%; border: 3px double #F59E0B; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #D97706;">
                ★
              </div>
              <div>
                <div style="font-family: cursive; font-size: 20px; color: #1E293B;">Prof. Robert Chen</div>
                <div style="border-top: 1px solid #94A3B8; width: 140px; margin: 4px auto;"></div>
                <div style="font-size: 11px; color: var(--text-muted);">Lead Systems Instructor</div>
              </div>
            </div>
          </div>

          <div style="display: flex; justify-content: center; gap: 12px; margin-top: 24px;">
            <button class="btn btn-primary" onclick="showToast('Downloading High-Res PDF Certificate...')">📥 Download Official PDF</button>
            <button class="btn btn-secondary" onclick="navigate('student-cert-verification')">🔍 Verify on Public Ledger</button>
            <button class="btn btn-secondary" onclick="showToast('Shared to LinkedIn Profile')">🔗 Share to LinkedIn</button>
          </div>
        </div>
        """
    elif sid == "student-code-workspace":
        body_html += """
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; height: 600px;">
          <!-- Editor Panel -->
          <div style="background: #1E1E2E; border-radius: var(--radius); display: flex; flex-direction: column; overflow: hidden; border: 1px solid #313244;">
            <div style="background: #181825; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #313244;">
              <span style="font-size: 12.5px; font-weight: 600; color: #CDD6F4;">main.py (Python 3.11 Environment)</span>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-custom-green btn-sm" onclick="runCodeSimulator()">▶ Run Code</button>
              </div>
            </div>
            <textarea id="code-editor-box" style="flex: 1; background: transparent; color: #A6ADC8; font-family: monospace; font-size: 13px; padding: 16px; border: none; outline: none; resize: none; line-height: 1.6;">
import numpy as np
from typing import List

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    \"\"\"Compute cosine similarity between two dense embeddings.\"\"\"
    vec1 = np.array(v1)
    vec2 = np.array(v2)
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

# Test Embeddings
query = [0.24, 0.81, 0.12, 0.95]
doc_chunk = [0.21, 0.79, 0.15, 0.92]

sim_score = cosine_similarity(query, doc_chunk)
print(f"Computed Vector Similarity: {sim_score:.4f}")
if sim_score > 0.85:
    print("Match Status: Highly Relevant Context Retrieved!")
</textarea>
          </div>

          <!-- Console Terminal -->
          <div style="background: #11111B; border-radius: var(--radius); display: flex; flex-direction: column; overflow: hidden; border: 1px solid #313244;">
            <div style="background: #181825; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #313244;">
              <span style="font-size: 12.5px; font-weight: 600; color: #A6ADC8;">Terminal Execution Output</span>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('console-output-box').innerText = '$ Ready for execution...'">Clear</button>
            </div>
            <pre id="console-output-box" style="flex: 1; padding: 16px; color: #A6E3A1; font-family: monospace; font-size: 13px; line-height: 1.6; margin: 0; overflow-y: auto;">
$ python main.py
[Compiling Python AST...]
Computed Vector Similarity: 0.9942
Match Status: Highly Relevant Context Retrieved!
Process finished with exit code 0 (Execution time: 0.042s)
</pre>
          </div>
        </div>
        """
    else:
        # Default high-fidelity realistic table/card view for all remaining screens
        body_html += f"""
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">{title} - Detailed Management</h3>
              <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">{desc}</p>
            </div>
            <div style="display: flex; gap: 8px;">
              <input type="text" class="form-control" placeholder="Filter records..." style="width: 220px; font-size: 12.5px; padding: 6px 10px;">
              <button class="btn btn-primary btn-sm" onclick="showToast('Record filtered')">Filter</button>
            </div>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Entity Identifier</th>
                  <th>Primary Attribute</th>
                  <th>Department / Cohort</th>
                  <th>Metric / Value</th>
                  <th>Lifecycle Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>REC-2026-001</strong></td>
                  <td>Advanced Full Stack AI Engineering</td>
                  <td>Computer Science Dept</td>
                  <td>₹24,950 / 50 seats</td>
                  <td><span class="badge badge-success">Active & Verified</span></td>
                  <td><button class="btn btn-secondary btn-sm" onclick="showToast('View record details')">Inspect</button></td>
                </tr>
                <tr>
                  <td><strong>REC-2026-002</strong></td>
                  <td>Cloud DevOps Microservices</td>
                  <td>Software Engineering</td>
                  <td>₹18,500 / 35 seats</td>
                  <td><span class="badge badge-primary">Processing</span></td>
                  <td><button class="btn btn-secondary btn-sm" onclick="showToast('View record details')">Inspect</button></td>
                </tr>
                <tr>
                  <td><strong>REC-2026-003</strong></td>
                  <td>Cybersecurity & Red Teaming</td>
                  <td>Information Security</td>
                  <td>₹32,000 / 40 seats</td>
                  <td><span class="badge badge-warning">Pending Review</span></td>
                  <td><button class="btn btn-secondary btn-sm" onclick="showToast('View record details')">Inspect</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        """
        
    return f"""
    <div id="screen-{sid}" class="screen-view">
      {header_html}
      {body_html}
    </div>
    """

print("Screen template generator ready.")
