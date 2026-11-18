"""
Generator for ExamLMS_Complete_UI_Prototype.html
Self-contained, interactive single-file prototype with role switcher, responsive sidebar,
and full rich UI for all 78 screens.
"""
import sys
import os

# Import screens
sys.path.append(os.path.dirname(__file__))
from screen_data import CATEGORIES, ALL_SCREENS

def build_prototype():
    # Construct screens HTML
    # We will build rich, realistic mockups for each screen based on its id and type.
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ExamLMS - Enterprise Learning & Proctored Assessment Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #635BFF;
      --primary-hover: #5046E5;
      --primary-light: rgba(99, 91, 255, 0.08);
      --primary-border: rgba(99, 91, 255, 0.2);
      --sidebar: #111827;
      --sidebar-hover: #1F2937;
      --sidebar-text: #9CA3AF;
      --sidebar-text-active: #FFFFFF;
      --bg-page: #F8FAFC;
      --card-bg: #FFFFFF;
      --card-border: #E2E8F0;
      --text-primary: #111827;
      --text-secondary: #64748B;
      --text-muted: #94A3B8;
      --success: #16A37B;
      --success-light: rgba(22, 163, 123, 0.1);
      --danger: #DC2626;
      --danger-light: rgba(220, 38, 38, 0.1);
      --warning: #D97706;
      --warning-light: rgba(217, 119, 6, 0.1);
      --info: #2563EB;
      --info-light: rgba(37, 99, 235, 0.1);
      --radius: 12px;
      --radius-sm: 8px;
      --radius-lg: 16px;
      --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
      --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.05);
      --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
      --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--bg-page);
      color: var(--text-primary);
      display: flex;
      min-height: 100vh;
      overflow-x: hidden;
      font-size: 14px;
      line-height: 1.5;
    }

    h1, h2, h3, h4, h5, h6 {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      font-weight: 700;
      color: var(--text-primary);
    }

    /* Layout Structure */
    #app-container {
      display: flex;
      width: 100%;
      min-height: 100vh;
    }

    /* Sidebar */
    #sidebar {
      width: 256px;
      background-color: var(--sidebar);
      color: var(--sidebar-text);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      border-right: 1px solid #1F2937;
      transition: all 0.2s ease;
      z-index: 100;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
    }

    #sidebar::-webkit-scrollbar {
      width: 4px;
    }
    #sidebar::-webkit-scrollbar-thumb {
      background: #374151;
      border-radius: 4px;
    }

    .brand-header {
      padding: 20px 20px 16px 20px;
      border-bottom: 1px solid #1F2937;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-logo {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #635BFF, #8B5CF6);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 800;
      font-size: 18px;
      box-shadow: 0 4px 10px rgba(99, 91, 255, 0.4);
    }

    .brand-text h2 {
      font-size: 17px;
      color: white;
      letter-spacing: -0.02em;
      margin: 0;
      line-height: 1.2;
    }
    .brand-text span {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #9CA3AF;
      font-weight: 600;
    }

    .role-badge-pill {
      margin: 14px 16px 6px 16px;
      padding: 8px 12px;
      background: #1F2937;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: space-between;
      border: 1px solid #374151;
    }
    .role-badge-left {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      font-weight: 600;
      color: #F3F4F6;
    }
    .role-indicator-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10B981;
      box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
    }

    .nav-section-label {
      padding: 16px 20px 6px 20px;
      font-size: 10.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #6B7280;
    }

    .nav-menu {
      list-style: none;
      padding: 0 10px;
      margin-bottom: 12px;
    }

    .nav-item {
      margin-bottom: 2px;
    }

    .nav-link {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 9px 12px;
      border-radius: var(--radius-sm);
      color: var(--sidebar-text);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.15s ease;
      cursor: pointer;
      position: relative;
    }

    .nav-link:hover {
      background-color: var(--sidebar-hover);
      color: white;
    }

    .nav-link.active {
      background: rgba(99, 91, 255, 0.18);
      color: #FFFFFF;
      font-weight: 600;
    }

    .nav-link.active::before {
      content: "";
      position: absolute;
      left: 0;
      top: 6px;
      bottom: 6px;
      width: 3.5px;
      background-color: var(--primary);
      border-radius: 0 4px 4px 0;
    }

    .nav-link svg {
      width: 17px;
      height: 17px;
      flex-shrink: 0;
      opacity: 0.8;
    }
    .nav-link.active svg {
      color: var(--primary);
      opacity: 1;
    }

    .nav-badge {
      margin-left: auto;
      font-size: 10px;
      padding: 2px 7px;
      border-radius: 10px;
      background: #374151;
      color: #D1D5DB;
      font-weight: 600;
    }
    .nav-badge.purple {
      background: var(--primary);
      color: white;
    }

    /* Main Area */
    #main-wrapper {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
      background: var(--bg-page);
    }

    /* Top Navigation Header */
    #top-nav {
      height: 68px;
      background: white;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      position: sticky;
      top: 0;
      z-index: 50;
      box-shadow: var(--shadow-sm);
    }

    .top-nav-left {
      display: flex;
      align-items: center;
      gap: 20px;
      flex: 1;
      max-width: 580px;
    }

    .search-box {
      position: relative;
      width: 100%;
      max-width: 380px;
    }
    .search-box input {
      width: 100%;
      padding: 8px 14px 8px 36px;
      border-radius: 20px;
      border: 1px solid #CBD5E1;
      background: #F8FAFC;
      font-size: 13px;
      outline: none;
      transition: all 0.15s ease;
      color: var(--text-primary);
    }
    .search-box input:focus {
      background: white;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 91, 255, 0.15);
    }
    .search-box svg {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      width: 15px;
      height: 15px;
      color: #94A3B8;
    }

    /* Search Dropdown Modal */
    #search-results-popover {
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      right: 0;
      background: white;
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-lg);
      max-height: 380px;
      overflow-y: auto;
      z-index: 200;
    }
    .search-result-item {
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #F1F5F9;
      cursor: pointer;
      font-size: 13px;
      transition: background 0.15s ease;
    }
    .search-result-item:hover {
      background: #F8FAFC;
    }

    .top-nav-right {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    /* Role Selector Dropdown */
    .role-switcher-container {
      display: flex;
      align-items: center;
      gap: 8px;
      background: #F1F5F9;
      padding: 4px 6px 4px 12px;
      border-radius: 24px;
      border: 1px solid #E2E8F0;
    }
    .role-switcher-label {
      font-size: 11.5px;
      font-weight: 600;
      color: #64748B;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .role-select {
      background: white;
      border: 1px solid #CBD5E1;
      padding: 6px 12px;
      border-radius: 18px;
      font-size: 12.5px;
      font-weight: 600;
      color: var(--text-primary);
      cursor: pointer;
      outline: none;
      box-shadow: var(--shadow-sm);
    }
    .role-select:focus {
      border-color: var(--primary);
    }

    /* Top icon buttons */
    .icon-btn {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      border: 1px solid var(--card-border);
      background: white;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #64748B;
      cursor: pointer;
      transition: all 0.15s ease;
      position: relative;
    }
    .icon-btn:hover {
      background: #F8FAFC;
      color: var(--text-primary);
      border-color: #CBD5E1;
    }
    .icon-btn .badge-dot {
      position: absolute;
      top: 6px;
      right: 6px;
      width: 8px;
      height: 8px;
      background: var(--danger);
      border-radius: 50%;
      border: 2px solid white;
    }

    .user-profile-btn {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 5px 12px 5px 5px;
      border-radius: 24px;
      border: 1px solid var(--card-border);
      background: white;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .user-profile-btn:hover {
      border-color: #CBD5E1;
      background: #F8FAFC;
    }
    .user-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, #4F46E5, #06B6D4);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 13px;
    }
    .user-info-text {
      text-align: left;
      line-height: 1.2;
    }
    .user-name {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--text-primary);
    }
    .user-role-label {
      font-size: 10.5px;
      color: var(--text-secondary);
    }

    /* Screen Container */
    #content-area {
      padding: 28px;
      flex: 1;
      max-width: 1440px;
      margin: 0 auto;
      width: 100%;
    }

    .screen-view {
      display: none;
      animation: fadeIn 0.15s ease forwards;
    }
    .screen-view.active {
      display: block;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(3px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Common UI Kit Components */
    .page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 24px;
      gap: 16px;
      flex-wrap: wrap;
    }
    .page-title-group h1 {
      font-size: 24px;
      letter-spacing: -0.02em;
      margin-bottom: 4px;
    }
    .page-title-group p {
      font-size: 13.5px;
      color: var(--text-secondary);
    }

    .action-group {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 9px 18px;
      font-size: 13.5px;
      font-weight: 600;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.15s ease;
      border: 1px solid transparent;
      outline: none;
      text-decoration: none;
    }
    .btn-primary {
      background-color: var(--primary);
      color: white;
      box-shadow: 0 1px 2px rgba(99, 91, 255, 0.2);
    }
    .btn-primary:hover {
      background-color: var(--primary-hover);
    }
    .btn-secondary {
      background-color: white;
      color: var(--text-primary);
      border-color: #CBD5E1;
    }
    .btn-secondary:hover {
      background-color: #F8FAFC;
      border-color: #94A3B8;
    }
    .btn-outline-primary {
      background-color: transparent;
      color: var(--primary);
      border-color: var(--primary-border);
    }
    .btn-outline-primary:hover {
      background-color: var(--primary-light);
      border-color: var(--primary);
    }
    .btn-success {
      background-color: var(--success);
      color: white;
    }
    .btn-success:hover {
      background-color: #059669;
    }
    .btn-danger {
      background-color: var(--danger);
      color: white;
    }
    .btn-danger:hover {
      background-color: #B91C1C;
    }
    .btn-custom-green {
      background-color: #096644;
      color: white;
    }
    .btn-custom-green:hover {
      background-color: #075237;
    }
    .btn-sm {
      padding: 6px 12px;
      font-size: 12.5px;
      border-radius: 6px;
    }
    .btn-lg {
      padding: 12px 24px;
      font-size: 15px;
      border-radius: 10px;
    }

    /* Cards */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-sm);
      padding: 22px;
      margin-bottom: 22px;
    }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 18px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-primary);
    }

    /* Grid Layouts */
    .grid-4 {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-bottom: 22px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      margin-bottom: 22px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 18px;
      margin-bottom: 22px;
    }

    /* Stat Card */
    .stat-card {
      background: white;
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      box-shadow: var(--shadow-sm);
    }
    .stat-card-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .stat-label {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .stat-icon {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .stat-icon.purple { background: var(--primary-light); color: var(--primary); }
    .stat-icon.green { background: var(--success-light); color: var(--success); }
    .stat-icon.blue { background: var(--info-light); color: var(--info); }
    .stat-icon.amber { background: var(--warning-light); color: var(--warning); }
    .stat-value {
      font-size: 26px;
      font-weight: 800;
      color: var(--text-primary);
      font-family: 'Plus Jakarta Sans', sans-serif;
      letter-spacing: -0.02em;
    }
    .stat-trend {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
    }
    .stat-trend.positive { color: var(--success); }
    .stat-trend.negative { color: var(--danger); }
    .stat-trend-context { color: var(--text-muted); }

    /* Tables */
    .table-container {
      width: 100%;
      overflow-x: auto;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13.5px;
    }
    thead {
      background: #F8FAFC;
      border-bottom: 1px solid var(--card-border);
    }
    th {
      padding: 12px 16px;
      font-weight: 600;
      color: var(--text-secondary);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid #F1F5F9;
      color: var(--text-primary);
    }
    tbody tr:last-child td {
      border-bottom: none;
    }
    tbody tr:hover {
      background: #FAFCFE;
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 9px;
      border-radius: 12px;
      font-size: 11.5px;
      font-weight: 600;
    }
    .badge-success { background: var(--success-light); color: var(--success); }
    .badge-primary { background: var(--primary-light); color: var(--primary); }
    .badge-warning { background: var(--warning-light); color: var(--warning); }
    .badge-danger { background: var(--danger-light); color: var(--danger); }
    .badge-neutral { background: #F1F5F9; color: #475569; }

    /* Forms */
    .form-group {
      margin-bottom: 18px;
    }
    .form-label {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary);
    }
    .form-control {
      width: 100%;
      padding: 10px 14px;
      border-radius: var(--radius-sm);
      border: 1px solid #CBD5E1;
      font-size: 13.5px;
      outline: none;
      transition: all 0.15s ease;
      background: white;
      color: var(--text-primary);
    }
    .form-control:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 91, 255, 0.15);
    }
    textarea.form-control {
      min-height: 100px;
      resize: vertical;
    }

    /* Stepper Navigation (Course Creation) */
    .stepper-nav {
      display: flex;
      align-items: center;
      background: white;
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 10px;
      margin-bottom: 24px;
      gap: 8px;
      overflow-x: auto;
    }
    .step-pill {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 600;
      color: #64748B;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
      text-decoration: none;
      background: transparent;
      border: 1px solid transparent;
    }
    .step-pill:hover {
      background: #F8FAFC;
      color: var(--text-primary);
    }
    .step-pill.active {
      background: var(--primary);
      color: white;
    }
    .step-pill.completed {
      background: var(--success-light);
      color: var(--success);
      border-color: rgba(22, 163, 123, 0.2);
    }
    .step-num {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
    }
    .step-pill.active .step-num {
      background: white;
      color: var(--primary);
    }

    /* Media/Learning Player */
    .video-mockup-frame {
      background: #0F172A;
      border-radius: var(--radius);
      aspect-ratio: 16/9;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 20px;
      color: white;
      position: relative;
      overflow: hidden;
      box-shadow: var(--shadow-lg);
    }
    .player-progress-bar {
      height: 6px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 3px;
      position: relative;
      overflow: hidden;
    }
    .player-progress-fill {
      height: 100%;
      background: var(--primary);
      width: 100%;
      transition: width 0.3s ease;
    }

    /* Proctored Exam Components */
    .proctored-header {
      background: #111827;
      color: white;
      padding: 14px 24px;
      border-radius: var(--radius) var(--radius) 0 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .proctored-timer {
      font-size: 18px;
      font-weight: 800;
      color: #FBBF24;
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: monospace;
    }
    .webcam-stream-mock {
      width: 140px;
      height: 105px;
      background: #1E293B;
      border: 2px solid #10B981;
      border-radius: 8px;
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }

    /* Toast / Notification Popover */
    .toast-pill {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #111827;
      color: white;
      padding: 12px 20px;
      border-radius: 30px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      gap: 12px;
      z-index: 1000;
      opacity: 0;
      pointer-events: none;
      transform: translateY(10px);
      transition: all 0.2s ease;
    }
    .toast-pill.show {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }

    /* Modals */
    .modal-backdrop {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      z-index: 500;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .modal-backdrop.active {
      display: flex;
    }
    .modal-dialog {
      background: white;
      border-radius: var(--radius-lg);
      max-width: 580px;
      width: 100%;
      box-shadow: var(--shadow-lg);
      overflow: hidden;
      animation: modalPop 0.2s ease;
    }
    @keyframes modalPop {
      from { transform: scale(0.96); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .modal-header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .modal-body {
      padding: 24px;
      max-height: 75vh;
      overflow-y: auto;
    }
    .modal-footer {
      padding: 16px 24px;
      background: #F8FAFC;
      border-top: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
    }

    /* Responsive */
    @media (max-width: 1024px) {
      .grid-4 { grid-template-columns: repeat(2, 1fr); }
      .grid-3 { grid-template-columns: repeat(1, 1fr); }
    }
    @media (max-width: 768px) {
      #sidebar {
        position: fixed;
        left: -260px;
      }
      #sidebar.open {
        left: 0;
      }
      .grid-4, .grid-2 { grid-template-columns: 1fr; }
      #content-area { padding: 16px; }
      #top-nav { padding: 0 16px; }
    }
  </style>
</head>
<body>

<div id="app-container">
  <!-- Dynamic Sidebar -->
  <aside id="sidebar">
    <div class="brand-header">
      <div class="brand-logo">E</div>
      <div class="brand-text">
        <h2>ExamLMS</h2>
        <span>Enterprise v2.4</span>
      </div>
    </div>

    <div class="role-badge-pill">
      <div class="role-badge-left">
        <span class="role-indicator-dot"></span>
        <span id="sidebar-role-display">Administrator</span>
      </div>
      <span class="badge badge-primary" style="font-size: 10px;">PRO</span>
    </div>

    <!-- Navigation container filled dynamically based on role -->
    <div id="sidebar-nav-container">
      <!-- Injected via JavaScript -->
    </div>
  </aside>

  <!-- Main Application Wrapper -->
  <main id="main-wrapper">
    <!-- Top Nav Header -->
    <header id="top-nav">
      <div class="top-nav-left">
        <button id="mobile-toggle-btn" class="icon-btn" style="display: none;" onclick="toggleSidebar()">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
        </button>
        <div class="search-box">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          <input type="text" id="global-search-input" placeholder="Search across 78 screens, courses, students..." oninput="handleGlobalSearch(this.value)">
          <div id="search-results-popover"></div>
        </div>
      </div>

      <div class="top-nav-right">
        <!-- Interactive Role Switcher Dropdown -->
        <div class="role-switcher-container">
          <span class="role-switcher-label">Role:</span>
          <select id="role-select" class="role-select" onchange="switchRole(this.value)">
            <option value="admin">🛡️ Administrator</option>
            <option value="head">🏛️ Institution Head</option>
            <option value="staff">👨‍🏫 Faculty / Staff</option>
            <option value="student">🎓 Student (Alex Johnson)</option>
          </select>
        </div>

        <button class="icon-btn" title="Notifications" onclick="navigate('shared-notifications')">
          <span class="badge-dot"></span>
          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
        </button>

        <button class="icon-btn" title="Settings" onclick="navigate('shared-account-settings')">
          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
        </button>

        <div class="user-profile-btn" onclick="navigate('shared-user-profile')">
          <div class="user-avatar" id="top-avatar-initials">AD</div>
          <div class="user-info-text">
            <div class="user-name" id="top-user-name">Super Admin</div>
            <div class="user-role-label" id="top-user-role">Administrator</div>
          </div>
        </div>
      </div>
    </header>

    <!-- Content Area: All 78 Screens -->
    <div id="content-area">
"""
    return html

print("Base builder written successfully.")
