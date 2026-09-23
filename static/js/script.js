// ============================================================================
// Campus Connect frontend <-> Flask API integration.
// Visual design, layout and CSS classes are unchanged. This file now talks
// to the real backend instead of faking auth/data with localStorage.
// ============================================================================

var CURRENT_USER = null; // populated by bootstrap() from /api/auth/me

// ---- Low-level API helper --------------------------------------------------
function api(path, options) {
  options = options || {};
  options.credentials = "include";
  var token = sessionStorage.getItem("campus_session_token");
  var headers = Object.assign({}, options.headers || {});
  if (token) {
    headers["X-Session-Token"] = token;
  }
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
    if (options.body && typeof options.body !== "string") options.body = JSON.stringify(options.body);
  }
  options.headers = headers;
  var targetUrl = path;
  return fetch(targetUrl, options).then(function (res) {
    return res.json().catch(function () { return {}; }).then(function (data) {
      if (!res.ok) {
        var err = new Error(data.error || ("Request failed (" + res.status + ")"));
        err.status = res.status;
        err.data = data;
        throw err;
      }
      return data;
    });
  });
}

function getActiveRole() {
  return CURRENT_USER ? CURRENT_USER.role : null;
}

function getUserProfile() {
  return CURRENT_USER;
}

function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

// ============================================================================
// Global Interactive ERP / SaaS UX Toolkit
// In-place reactive updates, loading spinners, credential modals, accessible
// confirm dialogs, and non-blocking toast notifications.
// ============================================================================

// 1. Modern Toast Notification Hub
function showToast(title, message, type, duration) {
  type = type || "info"; // "success", "error", "warning", "info"
  duration = duration || 4000;

  var container = document.getElementById("campusToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "campusToastContainer";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  var icons = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ"
  };

  var toast = document.createElement("div");
  toast.className = "toast-item toast-" + type;
  toast.innerHTML =
    '<div class="toast-icon">' + (icons[type] || "ℹ") + '</div>' +
    '<div class="toast-content">' +
      '<div class="toast-title">' + escapeHtml(title) + '</div>' +
      '<div class="toast-desc">' + escapeHtml(message) + '</div>' +
    '</div>' +
    '<span class="toast-close">&times;</span>' +
    '<div class="toast-progress"></div>';

  var closeBtn = toast.querySelector(".toast-close");
  var timer = null;

  function dismiss() {
    if (timer) clearTimeout(timer);
    toast.classList.add("toast-leave");
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 260);
  }

  closeBtn.addEventListener("click", dismiss);
  timer = setTimeout(dismiss, duration);
  container.appendChild(toast);
}

// 2. Button Loading State Helper
function setButtonLoading(btn, loadingText) {
  if (typeof btn === "string") btn = document.querySelector(btn);
  if (!btn) return;
  if (!btn.dataset.originalHtml) {
    btn.dataset.originalHtml = btn.innerHTML;
  }
  btn.disabled = true;
  btn.classList.add("btn-loading");
  btn.innerHTML = '<span class="btn-spinner"></span> ' + escapeHtml(loadingText || "Processing...");
}

function resetButton(btn, restoreHtml) {
  if (typeof btn === "string") btn = document.querySelector(btn);
  if (!btn) return;
  btn.disabled = false;
  btn.classList.remove("btn-loading");
  if (restoreHtml !== undefined) {
    btn.innerHTML = restoreHtml;
  } else if (btn.dataset.originalHtml) {
    btn.innerHTML = btn.dataset.originalHtml;
    delete btn.dataset.originalHtml;
  }
}

// 3. Accessible Confirmation Modal
function showConfirmModal(options) {
  options = options || {};
  var title = options.title || "Confirm Action";
  var message = options.message || "Are you sure you want to proceed?";
  var confirmText = options.confirmText || "Confirm";
  var cancelText = options.cancelText || "Cancel";
  var danger = options.danger !== false;
  var onConfirm = options.onConfirm || function (done) { done(); };
  var onCancel = options.onCancel || function () {};

  var existing = document.getElementById("globalConfirmModal");
  if (existing) existing.remove();

  var overlay = document.createElement("div");
  overlay.id = "globalConfirmModal";
  overlay.className = "modal-overlay active";
  overlay.innerHTML =
    '<div class="modal-box confirm-modal-box">' +
      '<div class="confirm-modal-icon">' + (danger ? '⚠️' : 'ℹ️') + '</div>' +
      '<div class="confirm-modal-title">' + escapeHtml(title) + '</div>' +
      '<div class="confirm-modal-desc">' + escapeHtml(message) + '</div>' +
      '<div class="confirm-modal-actions">' +
        '<button class="btn btn-secondary btn-sm confirm-cancel-btn">' + escapeHtml(cancelText) + '</button>' +
        '<button class="btn ' + (danger ? 'btn-danger' : 'btn-primary') + ' btn-sm confirm-ok-btn">' + escapeHtml(confirmText) + '</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(overlay);

  var cancelBtn = overlay.querySelector(".confirm-cancel-btn");
  var okBtn = overlay.querySelector(".confirm-ok-btn");

  function close() {
    overlay.classList.remove("active");
    setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 200);
  }

  cancelBtn.addEventListener("click", function () {
    close();
    onCancel();
  });

  okBtn.addEventListener("click", function () {
    setButtonLoading(okBtn, (confirmText.indexOf("Delete") !== -1 ? "Deleting..." : "Processing..."));
    cancelBtn.disabled = true;
    onConfirm(function done() {
      close();
    });
  });

  function handleKeydown(e) {
    if (e.key === "Escape") {
      document.removeEventListener("keydown", handleKeydown);
      close();
      onCancel();
    }
  }
  document.addEventListener("keydown", handleKeydown);
}

// 4. Success Credential / Action Modal
function showSuccessModal(options) {
  options = options || {};
  var title = options.title || "Operation Successful";
  var subtitle = options.subtitle || "";
  var items = options.items || []; // [{ label, value, copyable }]
  var actions = options.actions || []; // [{ text, className, onClick }]

  var existing = document.getElementById("globalSuccessModal");
  if (existing) existing.remove();

  var overlay = document.createElement("div");
  overlay.id = "globalSuccessModal";
  overlay.className = "modal-overlay active";

  var itemsHtml = items.map(function (item) {
    var copyBtnHtml = item.copyable ? (' <button class="copy-btn" title="Copy to clipboard" onclick="copyTextToClipboard(\'' + escapeHtml(item.value).replace(/'/g, "\\'") + '\', this)">📋 Copy</button>') : '';
    return '<div class="credential-row">' +
      '<span class="credential-label">' + escapeHtml(item.label) + '</span>' +
      '<span class="credential-value"><span>' + escapeHtml(item.value) + '</span>' + copyBtnHtml + '</span>' +
    '</div>';
  }).join("");

  var actionsHtml = actions.map(function (a, idx) {
    return '<button class="btn ' + (a.className || 'btn-primary') + ' btn-sm success-action-btn-' + idx + '">' + escapeHtml(a.text) + '</button>';
  }).join(" ");

  overlay.innerHTML =
    '<div class="modal-box credential-modal-box">' +
      '<div class="modal-header">' +
        '<div>' +
          '<h3 style="color: var(--success); display:flex; align-items:center; gap:8px;"><span>✓</span> ' + escapeHtml(title) + '</h3>' +
          (subtitle ? ('<p style="font-size:13px; color:var(--text-muted); margin-top:3px;">' + escapeHtml(subtitle) + '</p>') : '') +
        '</div>' +
        '<span class="modal-close success-close-btn">&times;</span>' +
      '</div>' +
      '<div class="modal-body">' +
        (items.length ? ('<div class="credential-card">' + itemsHtml + '</div>') : '') +
      '</div>' +
      '<div class="modal-footer">' +
        (actionsHtml || '<button class="btn btn-primary btn-sm success-close-btn">Done</button>') +
      '</div>' +
    '</div>';

  document.body.appendChild(overlay);

  function close() {
    overlay.classList.remove("active");
    setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 200);
  }

  overlay.querySelectorAll(".success-close-btn").forEach(function (btn) {
    btn.addEventListener("click", close);
  });

  actions.forEach(function (a, idx) {
    var btn = overlay.querySelector(".success-action-btn-" + idx);
    if (btn) {
      btn.addEventListener("click", function () {
        close();
        if (typeof a.onClick === "function") a.onClick();
      });
    }
  });
}

// 5. Clipboard Helper
window.copyTextToClipboard = function (text, btnElement) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(onSuccess).catch(fallback);
  } else {
    fallback();
  }

  function fallback() {
    var temp = document.createElement("textarea");
    temp.value = text;
    document.body.appendChild(temp);
    temp.select();
    try { document.execCommand("copy"); onSuccess(); } catch (e) {}
    document.body.removeChild(temp);
  }

  function onSuccess() {
    if (btnElement) {
      var old = btnElement.innerHTML;
      btnElement.innerHTML = "✓ Copied!";
      btnElement.style.color = "var(--success)";
      setTimeout(function () {
        btnElement.innerHTML = old;
        btnElement.style.color = "";
      }, 1600);
    }
    showToast("Copied to Clipboard", text, "info", 2000);
  }
};

// 6. Inline Error & Notification Banners
function showInlineError(container, message) {
  if (typeof container === "string") container = document.querySelector(container);
  if (!container) return;
  clearInlineErrors(container);
  var banner = document.createElement("div");
  banner.className = "inline-banner inline-banner-error";
  banner.innerHTML =
    '<span>⚠️ ' + escapeHtml(message) + '</span>' +
    '<span class="inline-banner-close" onclick="this.parentElement.remove()">&times;</span>';
  container.prepend(banner);
  banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function clearInlineErrors(container) {
  if (typeof container === "string") container = document.querySelector(container);
  if (!container) return;
  container.querySelectorAll(".inline-banner").forEach(function (b) { b.remove(); });
}

// 7. In-Place Row Animation Helpers
function highlightRow(rowElement, type) {
  if (!rowElement) return;
  var cls = type === "new" ? "row-highlight-new" : "row-highlight-update";
  rowElement.classList.remove("row-highlight-new", "row-highlight-update");
  void rowElement.offsetWidth; // trigger reflow
  rowElement.classList.add(cls);
}

function removeRowAnimated(rowElement, callback) {
  if (!rowElement) { if (callback) callback(); return; }
  rowElement.classList.add("row-fade-out");
  setTimeout(function () {
    if (rowElement.parentNode) rowElement.parentNode.removeChild(rowElement);
    if (callback) callback();
  }, 340);
}

// 8. Reusable ERP Empty State Renderer
function renderEmptyState(container, options) {
  if (typeof container === "string") container = document.querySelector(container);
  if (!container) return;
  options = options || {};
  var icon = options.icon || "📂";
  var title = options.title || "No Records Found";
  var message = options.message || "There is currently no data matching your request.";
  var actionText = options.actionText;
  var onAction = options.onAction;

  var btnHtml = actionText ? ('<button class="btn btn-primary btn-sm empty-state-action-btn">' + escapeHtml(actionText) + '</button>') : '';

  var isTbody = container.tagName.toLowerCase() === "tbody";
  if (isTbody) {
    var colSpan = options.colSpan || 7;
    container.innerHTML =
      '<tr class="empty-state-row"><td colspan="' + colSpan + '" style="padding: 0;">' +
        '<div class="empty-state-box">' +
          '<div class="empty-state-icon">' + icon + '</div>' +
          '<div class="empty-state-title">' + escapeHtml(title) + '</div>' +
          '<div class="empty-state-desc">' + escapeHtml(message) + '</div>' +
          btnHtml +
        '</div>' +
      '</td></tr>';
  } else {
    container.innerHTML =
      '<div class="empty-state-box">' +
        '<div class="empty-state-icon">' + icon + '</div>' +
        '<div class="empty-state-title">' + escapeHtml(title) + '</div>' +
        '<div class="empty-state-desc">' + escapeHtml(message) + '</div>' +
        btnHtml +
      '</div>';
  }

  if (actionText && typeof onAction === "function") {
    var actionBtn = container.querySelector(".empty-state-action-btn");
    if (actionBtn) actionBtn.addEventListener("click", onAction);
  }
}

// ---- Boot sequence ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
  var currentPath = window.location.pathname.split("/").pop() || "index.html";
  var publicPages = ["index.html", "login.html", "doc.html", ""];

  // Password toggle & role tabs work without auth (needed on login page)
  wirePasswordToggle();
  initLogin();

  if (publicPages.indexOf(currentPath) !== -1) {
    return;
  }

  // Enforce tab-isolated session: protected pages require this tab's own session token
  var token = sessionStorage.getItem("campus_session_token");
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  api("/api/auth/me")
    .then(function (res) {
      CURRENT_USER = res.data;
      boot(currentPath);
    })
    .catch(function () {
      sessionStorage.removeItem("campus_session_token");
      sessionStorage.removeItem("campus_user_role");
      window.location.href = "login.html";
    });
});

function boot(currentPath) {
  var user = CURRENT_USER;
  var role = user.role;

  // 1. Client-side RBAC gate (server also enforces this on every API call)
  if (currentPath === "users.html" && role !== "admin") {
    alert("Access Denied: The User Directory is restricted to Administrators only.");
    window.location.href = "dashboard.html";
    return;
  }
  if (currentPath === "attendance.html" && role === "admin") {
    alert("Access Denied: Attendance management is reserved for Faculty and Students.");
    window.location.href = "dashboard.html";
    return;
  }

  // 2. Topbar
  var topbarUser = document.getElementById("topbarUserName");
  if (topbarUser) topbarUser.textContent = user.name;
  var topbarAvatar = document.getElementById("topbarAvatar");
  if (topbarAvatar) topbarAvatar.textContent = user.name.charAt(0);

  // Role selector now just displays the authenticated role (role is decided
  // by which account you logged into, not a demo toggle anymore).
  var roleSelect = document.getElementById("globalRoleSelect");
  if (roleSelect) {
    roleSelect.value = role;
    roleSelect.disabled = true;
    roleSelect.title = "Your role is set by your login account.";
  }

  var topbarRoleBadge = document.getElementById("topbarRoleBadge");
  if (topbarRoleBadge) {
    topbarRoleBadge.textContent = user.roleLabel || role.toUpperCase();
    topbarRoleBadge.className =
      role === "student" ? "badge badge-primary" :
      role === "faculty" ? "badge badge-info" : "badge badge-warning";
  }

  // 3. Sidebar toggle for mobile
  var menuBtn = document.getElementById("menuBtn");
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("sidebarOverlay");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function () {
      sidebar.classList.toggle("open");
      if (overlay) overlay.classList.toggle("active");
    });
  }
  if (overlay) {
    overlay.addEventListener("click", function () {
      if (sidebar) sidebar.classList.remove("open");
      overlay.classList.remove("active");
    });
  }

  setupSidebar(role);

  // 4. Common & Page-specific initializers
  initSearchAndFilter();
  initPasswordChange();

  switch (currentPath) {
    case "dashboard.html":
      initDashboard(user, role);
      break;
    case "profile.html":
      initProfile(user, role);
      break;
    case "courses.html":
      initCourses(role);
      break;
    case "attendance.html":
      initAttendance(role);
      break;
    case "results.html":
      initResults(role);
      break;
    case "notices.html":
      initNotices(role);
      break;
    case "materials.html":
      initMaterials(role);
      break;
    case "users.html":
      initUsers(role);
      break;
    case "events.html":
      initEvents(role);
      break;
    case "settings.html":
      break;
    default:
      // Fallback detection using element IDs if page URL does not end in .html
      if (document.getElementById("welcomeMsg")) initDashboard(user, role);
      if (document.getElementById("profileName")) initProfile(user, role);
      if (document.getElementById("coursesContainer")) initCourses(role);
      if (document.getElementById("studentResultView") || document.getElementById("facultyResultView") || document.getElementById("adminResultView")) initResults(role);
      if (document.getElementById("materialsTableBody") || document.getElementById("uploadMaterialModal")) initMaterials(role);
      if (document.getElementById("usersTableBody") || document.getElementById("addUserModal")) initUsers(role);
      if (document.getElementById("postNoticeBtn") || document.getElementById("newNoticeModal")) initNotices(role);
      if (document.querySelector('[data-role="attendance-summary-body"]') || document.getElementById("facultyRollCallCard")) initAttendance(role);
      if (window.location.pathname.indexOf("events") !== -1) initEvents(role);
      break;
  }
}

function initPasswordChange() {
  var form = document.getElementById("changePassForm");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearInlineErrors(form);
    var currentPassword = document.getElementById("currentPass").value;
    var newPassword = document.getElementById("newPass").value;
    var confirmPassword = document.getElementById("confirmNewPass").value;
    var submitBtn = form.querySelector('button[type="submit"]') || form.querySelector('.btn-primary');

    if (!currentPassword || !newPassword || !confirmPassword) {
      showInlineError(form, "Please fill in all password fields.");
      return;
    }
    if (newPassword.length < 6) {
      showInlineError(form, "New password must be at least 6 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      showInlineError(form, "New password and confirmation do not match.");
      return;
    }

    setButtonLoading(submitBtn, "Updating Password...");

    api("/api/auth/change-password", {
      method: "POST",
      body: { currentPassword: currentPassword, newPassword: newPassword, confirmPassword: confirmPassword }
    }).then(function (res) {
      form.reset();
      var banner = document.createElement("div");
      banner.className = "inline-banner inline-banner-success";
      banner.innerHTML =
        '<span>✓ Password updated successfully! Your account credentials have been secured.</span>' +
        '<span class="inline-banner-close" onclick="this.parentElement.remove()">&times;</span>';
      form.prepend(banner);
      showToast("Security Update", "Password changed successfully.", "success");
    }).catch(function (e) {
      showInlineError(form, e.message || "Could not update password.");
      showToast("Update Failed", e.message || "Could not update password.", "error");
    }).finally(function () {
      resetButton(submitBtn);
    });
  });
}

function wirePasswordToggle() {
  document.querySelectorAll(".toggle-pass").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = this.getAttribute("data-target");
      var input = targetId ? document.getElementById(targetId) : this.previousElementSibling;
      if (input) {
        if (input.type === "password") {
          input.type = "text";
          this.textContent = "Hide";
        } else {
          input.type = "password";
          this.textContent = "Show";
        }
      }
    });
  });
}

// Dynamic sidebar links strictly matching role authorizations
function setupSidebar(role) {
  var nav = document.getElementById("sidebarNav");
  if (!nav) return;

  var current = window.location.pathname.split("/").pop() || "index.html";
  var items = [];

  if (role === "student") {
    items = [
      { name: "Dashboard", href: "dashboard.html", icon: "📊" },
      { name: "My Profile", href: "profile.html", icon: "👤" },
      { name: "Courses", href: "courses.html", icon: "📚" },
      { name: "My Results", href: "results.html", icon: "📝" },
      { name: "Notices", href: "notices.html", icon: "📢" },
      { name: "Events", href: "events.html", icon: "🎉" },
      { name: "Study Materials", href: "materials.html", icon: "📁" },
      { name: "Settings", href: "settings.html", icon: "⚙️" }
    ];
  } else if (role === "faculty") {
    items = [
      { name: "Dashboard", href: "dashboard.html", icon: "📊" },
      { name: "Faculty Profile", href: "profile.html", icon: "👤" },
      { name: "My Classes", href: "courses.html", icon: "📚" },
      { name: "Mark Attendance", href: "attendance.html", icon: "📅" },
      { name: "Enter Marks", href: "results.html", icon: "📝" },
      { name: "Notices", href: "notices.html", icon: "📢" },
      { name: "Events", href: "events.html", icon: "🎉" },
      { name: "Upload Materials", href: "materials.html", icon: "📁" },
      { name: "Settings", href: "settings.html", icon: "⚙️" }
    ];
  } else {
    items = [
      { name: "Dashboard", href: "dashboard.html", icon: "📊" },
      { name: "Admin Profile", href: "profile.html", icon: "👤" },
      { name: "User Directory", href: "users.html", icon: "👥" },
      { name: "Courses", href: "courses.html", icon: "📚" },
      { name: "Result Control", href: "results.html", icon: "📝" },
      { name: "Manage Notices", href: "notices.html", icon: "📢" },
      { name: "Manage Events", href: "events.html", icon: "🎉" },
      { name: "Study Repository", href: "materials.html", icon: "📁" },
      { name: "Settings", href: "settings.html", icon: "⚙️" }
    ];
  }

  var html = items.map(function (item) {
    return '<a href="' + item.href + '" class="' + (current === item.href ? 'active' : '') + '">' +
      '<span class="sidebar-icon">' + item.icon + '</span>' +
      '<span>' + item.name + '</span></a>';
  }).join("");

  html += '<a href="login.html" onclick="logoutUser(event)" style="margin-top: 15px; color: var(--danger);">' +
    '<span class="sidebar-icon">🚪</span><span>Logout</span></a>';

  nav.innerHTML = html;
}

// User logout handler
window.logoutUser = function (e) {
  if (e) e.preventDefault();
  api("/api/auth/logout", { method: "POST" }).finally(function () {
    sessionStorage.removeItem("campus_session_token");
    sessionStorage.removeItem("campus_user_role");
    sessionStorage.removeItem("campus_role");
    CURRENT_USER = null;
    window.location.href = "login.html";
  });
};

// ---- Login page --------------------------------------------------------------
function initLogin() {
  var form = document.getElementById("loginForm");
  if (!form) return;

  // Clean stale session tokens whenever reaching the login screen
  sessionStorage.removeItem("campus_session_token");
  sessionStorage.removeItem("campus_user_role");
  CURRENT_USER = null;

  var tabs = document.querySelectorAll(".role-tab");
  var selectedRole = "student";

  // Pre-select role tab if selected on home page in this tab
  var savedRole = sessionStorage.getItem("campus_role");
  if (savedRole) {
    selectedRole = savedRole;
    tabs.forEach(function (tab) {
      if (tab.getAttribute("data-role") === savedRole) {
        tabs.forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
      }
    });
  }

  tabs.forEach(function (tab) {
    if (tab.classList.contains("active")) selectedRole = tab.getAttribute("data-role");
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("active"); });
      this.classList.add("active");
      selectedRole = this.getAttribute("data-role");
      sessionStorage.setItem("campus_role", selectedRole);
    });
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var id = document.getElementById("loginId").value.trim();
    var pass = document.getElementById("loginPassword").value.trim();
    var err = document.getElementById("loginError");
    var submitBtn = form.querySelector('button[type="submit"]');

    if (!id || !pass) {
      err.textContent = "Please enter both ID/Email and password.";
      return;
    }
    err.textContent = "";
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Signing in..."; }

    api("/api/auth/login", {
      method: "POST",
      body: { email: id, password: pass, role: selectedRole }
    }).then(function (res) {
      if (res.sessionToken) {
        sessionStorage.setItem("campus_session_token", res.sessionToken);
      }
      if (res.data && res.data.role) {
        sessionStorage.setItem("campus_user_role", res.data.role);
      }
      window.location.href = "dashboard.html";
    }).catch(function (e) {
      err.textContent = e.message || "Login failed.";
    }).finally(function () {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Sign In to Workspace"; }
    });
  });
}

// ---- Dashboard ----------------------------------------------------------------
function initDashboard(user, role) {
  var welcomeMsg = document.getElementById("welcomeMsg");
  if (!welcomeMsg) return;

  welcomeMsg.textContent = "Welcome, " + user.name + "!";
  var roleTag = document.getElementById("welcomeRole");
  if (roleTag) roleTag.textContent = user.roleLabel || role.toUpperCase();

  var container = document.getElementById("dashboardWidgets");

  api("/api/dashboard/summary").then(function (res) {
    var d = res.data;
    var welcomeSub = document.getElementById("welcomeSub");
    if (welcomeSub && d.cohort && d.cohort.badge) {
      welcomeSub.textContent = d.cohort.badge + " • Campus Connect Portal";
    }
    if (!container) return;

    if (role === "student") {
      container.innerHTML =
        '<div class="stat-card stat-green"><div class="stat-card-header">Attendance</div><div class="stat-card-value">' + d.attendancePct + '%</div><div class="stat-card-desc">Min 75% required</div><div class="progress-bar-bg"><div class="progress-bar-fill progress-green" style="width: ' + d.attendancePct + '%;"></div></div></div>' +
        '<div class="stat-card"><div class="stat-card-header">Current CGPA</div><div class="stat-card-value">' + d.cgpa + '</div><div class="stat-card-desc">Based on published results</div><div class="progress-bar-bg"><div class="progress-bar-fill" style="width: ' + Math.min(d.cgpa * 10, 100) + '%;"></div></div></div>' +
        '<div class="stat-card stat-amber"><div class="stat-card-header">Enrolled Courses</div><div class="stat-card-value">' + d.enrolledCourses + ' Courses</div><div class="stat-card-desc">This semester</div></div>' +
        '<div class="stat-card stat-purple"><div class="stat-card-header">Pending Tasks</div><div class="stat-card-value">' + d.pendingTasks + ' Notices</div><div class="stat-card-desc">Posted this week</div></div>';
    } else if (role === "faculty") {
      container.innerHTML =
        '<div class="stat-card stat-green"><div class="stat-card-header">Assigned Classes</div><div class="stat-card-value">' + d.todayClasses + ' Classes</div><div class="stat-card-desc">This semester</div></div>' +
        '<div class="stat-card"><div class="stat-card-header">Total Students</div><div class="stat-card-value">' + d.totalStudents + '</div><div class="stat-card-desc">Across your courses</div></div>' +
        '<div class="stat-card stat-amber"><div class="stat-card-header">Attendance Pending</div><div class="stat-card-value">' + d.attendancePending + ' Class(es)</div><div class="stat-card-desc">Not yet marked today</div></div>' +
        '<div class="stat-card stat-purple"><div class="stat-card-header">Uploaded Notes</div><div class="stat-card-value">' + d.uploadedNotes + ' Files</div><div class="stat-card-desc">By you</div></div>';
    } else {
      container.innerHTML =
        '<div class="stat-card stat-green"><div class="stat-card-header">Total Students</div><div class="stat-card-value">' + d.totalStudents + '</div><div class="stat-card-desc">Active Enrolled</div></div>' +
        '<div class="stat-card"><div class="stat-card-header">Faculty Members</div><div class="stat-card-value">' + d.facultyMembers + '</div><div class="stat-card-desc">Across departments</div></div>' +
        '<div class="stat-card stat-amber"><div class="stat-card-header">Course Offerings</div><div class="stat-card-value">' + (d.activeCourses || 0) + ' Active</div><div class="stat-card-desc">' + (d.totalCourses || 0) + ' Total • ' + (d.inactiveCourses || 0) + ' Inactive • ' + (d.departmentsWithCourses || 0) + ' Depts</div></div>' +
        '<div class="stat-card stat-purple"><div class="stat-card-header">System Health</div><div class="stat-card-value">' + d.systemHealth + '%</div><div class="stat-card-desc">Portal Running Smoothly</div></div>';
    }
  }).catch(function () {
    if (container) container.innerHTML = '<div class="stat-card"><div class="stat-card-desc">Could not load dashboard data.</div></div>';
  });

  var quickLinks = document.getElementById("dashboardQuickLinks");
  if (quickLinks) {
    if (role === "student") {
      quickLinks.innerHTML =
        '<a href="courses.html" class="btn btn-secondary btn-sm">📚 My Courses</a>' +
        '<a href="results.html" class="btn btn-secondary btn-sm">📝 My Results</a>' +
        '<a href="materials.html" class="btn btn-secondary btn-sm">📁 Study Notes</a>' +
        '<a href="notices.html" class="btn btn-secondary btn-sm">📢 Notice Board</a>' +
        '<a href="events.html" class="btn btn-secondary btn-sm">🎉 Events</a>' +
        '<a href="settings.html" class="btn btn-secondary btn-sm">⚙️ Settings</a>';
    } else if (role === "faculty") {
      quickLinks.innerHTML =
        '<a href="courses.html" class="btn btn-secondary btn-sm">📚 My Classes</a>' +
        '<a href="attendance.html" class="btn btn-secondary btn-sm">📅 Mark Attendance</a>' +
        '<a href="results.html" class="btn btn-secondary btn-sm">📝 Enter Marks</a>' +
        '<a href="materials.html" class="btn btn-secondary btn-sm">📁 Upload Materials</a>' +
        '<a href="notices.html" class="btn btn-secondary btn-sm">📢 Notice Board</a>' +
        '<a href="settings.html" class="btn btn-secondary btn-sm">⚙️ Settings</a>';
    } else {
      quickLinks.innerHTML =
        '<a href="users.html" class="btn btn-secondary btn-sm">👥 User Directory</a>' +
        '<a href="courses.html" class="btn btn-secondary btn-sm">📚 Manage Courses</a>' +
        '<a href="results.html" class="btn btn-secondary btn-sm">📝 Result Control</a>' +
        '<a href="notices.html" class="btn btn-secondary btn-sm">📢 Manage Notices</a>' +
        '<a href="materials.html" class="btn btn-secondary btn-sm">📁 Study Repository</a>' +
        '<a href="settings.html" class="btn btn-secondary btn-sm">⚙️ Settings</a>';
    }
  }
}

// ---- Courses module ----------------------------------------------------------------
var _allCoursesCache = [];
var _allDepartmentsCache = [];
var _currentCourseViewMode = "auto";

function initCourses(role) {
  var container = document.getElementById("coursesContainer");
  var tableContainer = document.getElementById("adminCoursesTableContainer");
  var addBtn = document.getElementById("openAddCourseBtn");
  var statsBar = document.getElementById("adminCourseStatsBar");
  var statusFilter = document.getElementById("courseStatusFilter");
  var pageTitle = document.getElementById("coursesPageTitle");
  var pageSub = document.getElementById("coursesPageSub");

  if (!container && !tableContainer) return;

  var isAdmin = (role === "admin");

  if (addBtn) addBtn.style.display = isAdmin ? "inline-flex" : "none";
  if (statsBar) statsBar.style.display = isAdmin ? "grid" : "none";
  if (statusFilter) statusFilter.style.display = isAdmin ? "inline-block" : "none";

  if (pageTitle) {
    pageTitle.textContent = isAdmin ? "Course Administration & Curriculum" : "Courses & Academic Curriculum";
  }
  if (pageSub) {
    pageSub.textContent = isAdmin
      ? "Manage institutional course offerings, assign departments & instructors, and track syllabus coverage"
      : "Explore enrolled subjects, syllabus schedules and course progress";
  }

  // Load Departments for filters and modals
  api("/api/departments").then(function (res) {
    _allDepartmentsCache = res.data || [];
    populateDeptDropdowns(_allDepartmentsCache);
  }).catch(function () {});

  // Bind Search and Filter events
  var searchInput = document.getElementById("courseSearchInput");
  var deptFilter = document.getElementById("courseDeptFilter");
  var semFilter = document.getElementById("courseSemFilter");
  var catFilter = document.getElementById("courseCategoryFilter");

  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener("input", function () { filterAndRenderCourses(); });
  }
  if (deptFilter && !deptFilter._bound) {
    deptFilter._bound = true;
    deptFilter.addEventListener("change", filterAndRenderCourses);
  }
  if (semFilter && !semFilter._bound) {
    semFilter._bound = true;
    semFilter.addEventListener("change", filterAndRenderCourses);
  }
  if (catFilter && !catFilter._bound) {
    catFilter._bound = true;
    catFilter.addEventListener("change", filterAndRenderCourses);
  }
  if (statusFilter && !statusFilter._bound) {
    statusFilter._bound = true;
    statusFilter.addEventListener("change", filterAndRenderCourses);
  }

  loadCoursesList();
}

function loadCoursesList() {
  api("/api/courses").then(function (res) {
    _allCoursesCache = res.data || [];
    updateAdminCourseStats(_allCoursesCache);
    filterAndRenderCourses();
  }).catch(function (err) {
    var container = document.getElementById("coursesContainer");
    if (container) {
      container.innerHTML = '<div class="card" style="grid-column: 1 / -1; text-align:center; color: var(--text-muted); padding: 32px;">Could not load courses: ' + escapeHtml(err.message || "Network error") + '</div>';
    }
  });
}

function updateAdminCourseStats(courses) {
  var statTotal = document.getElementById("statTotalCourses");
  var statActive = document.getElementById("statActiveCourses");
  var statInactive = document.getElementById("statInactiveCourses");
  var statDepts = document.getElementById("statDeptCourses");

  if (!statTotal) return;

  var total = courses.length;
  var active = courses.filter(function (c) { return (c.status || "active").toLowerCase() === "active"; }).length;
  var inactive = total - active;
  var depts = {};
  courses.forEach(function (c) {
    if (c.departmentId) depts[c.departmentId] = true;
    else if (c.department) depts[c.department] = true;
  });
  var deptCount = Object.keys(depts).length;

  statTotal.textContent = total;
  statActive.textContent = active;
  statInactive.textContent = inactive;
  statDepts.textContent = deptCount;
}

function populateDeptDropdowns(depts) {
  var filterSelect = document.getElementById("courseDeptFilter");
  var addSelect = document.getElementById("addCourseDept");
  var editSelect = document.getElementById("editCourseDept");

  var optionsHtml = '<option value="">Select Department...</option>' +
    depts.map(function (d) {
      return '<option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.name) + ' (' + escapeHtml(d.code) + ')</option>';
    }).join("");

  if (addSelect) {
    var addVal = addSelect.value;
    addSelect.innerHTML = optionsHtml;
    if (addVal) addSelect.value = addVal;
  }
  if (editSelect) {
    var editVal = editSelect.value;
    editSelect.innerHTML = optionsHtml;
    if (editVal) editSelect.value = editVal;
  }

  if (filterSelect) {
    var curVal = filterSelect.value || "all";
    filterSelect.innerHTML = '<option value="all">All Departments</option>' +
      depts.map(function (d) {
        return '<option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.name) + '</option>';
      }).join("");
    filterSelect.value = curVal;
  }
}

function onDepartmentChanged(deptSelectId, instSelectId, selectedInstId) {
  var deptSelect = document.getElementById(deptSelectId);
  var instSelect = document.getElementById(instSelectId);
  if (!deptSelect || !instSelect) return;

  var deptId = deptSelect.value;
  if (!deptId) {
    instSelect.innerHTML = '<option value="">Select Department first...</option>';
    return;
  }

  instSelect.innerHTML = '<option value="">Loading faculty...</option>';

  api("/api/faculty?department_id=" + encodeURIComponent(deptId)).then(function (res) {
    var faculty = res.data || [];
    if (!faculty.length) {
      instSelect.innerHTML = '<option value="">-- No Faculty Assigned in Dept --</option>';
      return;
    }
    var html = '<option value="">-- Unassigned --</option>' +
      faculty.map(function (f) {
        var isSel = (selectedInstId && (String(selectedInstId) === String(f.facultyId) || String(selectedInstId) === String(f.id) || String(selectedInstId) === String(f.facultyCode)));
        return '<option value="' + escapeHtml(f.facultyId || f.facultyCode) + '" ' + (isSel ? 'selected' : '') + '>' +
          escapeHtml(f.name) + ' (' + escapeHtml(f.facultyCode) + ')' +
          '</option>';
      }).join("");
    instSelect.innerHTML = html;
  }).catch(function () {
    instSelect.innerHTML = '<option value="">-- Unassigned --</option>';
  });
}

function onSemesterChanged(semSelectId, yearSelectId) {
  var semSelect = document.getElementById(semSelectId);
  var yearSelect = document.getElementById(yearSelectId);
  if (!semSelect || !yearSelect) return;

  var sem = parseInt(semSelect.value, 10) || 1;
  var yr = Math.ceil(sem / 2);
  var yrLabel = yr === 1 ? "1st Year" : yr === 2 ? "2nd Year" : yr === 3 ? "3rd Year" : "4th Year";
  yearSelect.value = yrLabel;
}

function setCourseViewMode(mode) {
  _currentCourseViewMode = mode;
  filterAndRenderCourses();
}

function filterAndRenderCourses() {
  var role = getActiveRole();
  var isAdmin = (role === "admin");

  var searchVal = (document.getElementById("courseSearchInput") ? document.getElementById("courseSearchInput").value : "").toLowerCase().trim();
  var deptVal = (document.getElementById("courseDeptFilter") ? document.getElementById("courseDeptFilter").value : "all");
  var semVal = (document.getElementById("courseSemFilter") ? document.getElementById("courseSemFilter").value : "all");
  var catVal = (document.getElementById("courseCategoryFilter") ? document.getElementById("courseCategoryFilter").value : "all");
  var statusVal = (document.getElementById("courseStatusFilter") ? document.getElementById("courseStatusFilter").value : "all");

  var filtered = _allCoursesCache.filter(function (c) {
    if (searchVal) {
      var match = (c.code && c.code.toLowerCase().indexOf(searchVal) !== -1) ||
                  (c.title && c.title.toLowerCase().indexOf(searchVal) !== -1) ||
                  (c.department && c.department.toLowerCase().indexOf(searchVal) !== -1) ||
                  (c.instructor && c.instructor.toLowerCase().indexOf(searchVal) !== -1);
      if (!match) return false;
    }
    if (deptVal && deptVal !== "all") {
      if (String(c.departmentId) !== String(deptVal) && String(c.department) !== String(deptVal)) return false;
    }
    if (semVal && semVal !== "all") {
      if (String(c.semester) !== String(semVal)) return false;
    }
    if (catVal && catVal !== "all") {
      var cleanCat = (c.category || "").toLowerCase();
      if (catVal === "lab" && cleanCat !== "lab" && cleanCat !== "laboratory" && cleanCat !== "practical") return false;
      if (catVal !== "lab" && cleanCat !== catVal.toLowerCase()) return false;
    }
    if (statusVal && statusVal !== "all") {
      if ((c.status || "active").toLowerCase() !== statusVal.toLowerCase()) return false;
    }
    return true;
  });

  var tableContainer = document.getElementById("adminCoursesTableContainer");
  var tableBody = document.getElementById("adminCoursesTableBody");
  var gridContainer = document.getElementById("coursesContainer");

  var showTable = (_currentCourseViewMode === "table") || (_currentCourseViewMode === "auto" && isAdmin);

  if (showTable) {
    if (tableContainer) tableContainer.style.display = "block";
    if (gridContainer) gridContainer.style.display = "none";

    if (tableBody) {
      if (!filtered.length) {
        tableBody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 28px; color: var(--text-muted);">No courses match the current filters.</td></tr>';
      } else {
        tableBody.innerHTML = filtered.map(function (c) {
          var statusBadge = (c.status || "active").toLowerCase() === "active"
            ? '<span class="badge badge-success">Active</span>'
            : '<span class="badge badge-secondary" style="opacity: 0.8;">Inactive</span>';
          var coverage = c.syllabusCoverage !== undefined ? c.syllabusCoverage : 0;
          var toggleAction = (c.status || "active").toLowerCase() === "active" ? "Deactivate" : "Activate";

          return '<tr id="course-row-' + escapeHtml(c.id) + '">' +
            '<td><strong class="badge badge-primary" style="font-size: 12px;">' + escapeHtml(c.code) + '</strong></td>' +
            '<td><strong>' + escapeHtml(c.title) + '</strong><br><small style="color: var(--text-muted);">' + escapeHtml(c.category || "Core") + '</small></td>' +
            '<td>' + escapeHtml(c.department || "-") + '</td>' +
            '<td>Sem ' + (c.semester || "-") + '</td>' +
            '<td>' + (c.credits || 3) + '</td>' +
            '<td>' + escapeHtml(c.instructor || "Unassigned") + '</td>' +
            '<td>' + escapeHtml(c.room || "-") + '</td>' +
            '<td>' +
              '<div style="font-size: 11px; margin-bottom: 2px;">' + coverage + '%</div>' +
              '<div class="progress-bar-bg" style="height: 6px; width: 70px;"><div class="progress-bar-fill progress-green" style="width: ' + coverage + '%;"></div></div>' +
            '</td>' +
            '<td>' + statusBadge + '</td>' +
            '<td style="text-align: right; white-space: nowrap;">' +
              '<button class="btn btn-secondary btn-sm" style="padding: 4px 8px; margin-right: 4px;" onclick="openCourseDetailsModal(\'' + escapeHtml(c.id) + '\')">View</button>' +
              (isAdmin ? '<button class="btn btn-secondary btn-sm" style="padding: 4px 8px; margin-right: 4px;" onclick="openEditCourseModal(\'' + escapeHtml(c.id) + '\')">Edit</button>' : '') +
              (isAdmin ? '<button class="btn btn-secondary btn-sm" style="padding: 4px 8px; margin-right: 4px;" onclick="toggleCourseStatus(\'' + escapeHtml(c.id) + '\', \'' + escapeHtml(c.status || "active") + '\')">' + toggleAction + '</button>' : '') +
              (isAdmin ? '<button class="btn btn-danger btn-sm" style="padding: 4px 8px;" onclick="deleteCourse(\'' + escapeHtml(c.id) + '\')">Delete</button>' : '') +
            '</td>' +
          '</tr>';
        }).join("");
      }
    }
  } else {
    if (tableContainer) tableContainer.style.display = "none";
    if (gridContainer) gridContainer.style.display = "grid";

    if (gridContainer) {
      if (!filtered.length) {
        gridContainer.innerHTML = '<div class="card" style="grid-column: 1 / -1; text-align:center; color: var(--text-muted); padding: 32px;">No courses found matching your criteria.</div>';
      } else {
        gridContainer.innerHTML = filtered.map(function (c) {
          var cat = (c.category || "core").toLowerCase();
          var coverage = c.syllabusCoverage !== undefined ? c.syllabusCoverage : 80;
          var divText = c.assignedDivisions && c.assignedDivisions.length ? (' • Div: ' + c.assignedDivisions.join(', ')) : (c.division ? (' • Div: ' + c.division) : '');
          var statusBadge = (c.status || "active").toLowerCase() === "active"
            ? '<span class="badge badge-success">Active</span>'
            : '<span class="badge badge-secondary">Inactive</span>';

          return '<div class="card filterable-item" data-category="' + escapeHtml(cat) + '">' +
            '<div class="card-header-row">' +
              '<div>' +
                '<span class="badge badge-primary">' + escapeHtml(c.code) + '</span>' +
                '<span class="badge badge-secondary" style="margin-left: 4px;">' + (c.credits || 3) + ' Credits</span>' +
              '</div>' +
              statusBadge +
            '</div>' +
            '<h3 style="font-size: 17px; margin-bottom: 6px;">' + escapeHtml(c.title) + '</h3>' +
            '<p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">' +
              'Instructor: ' + escapeHtml(c.instructor || 'Faculty Assigned') + ' • Sem ' + (c.semester || '-') + divText +
            '</p>' +
            '<div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px; display: flex; justify-content: space-between;">' +
              '<span>Syllabus Coverage</span>' +
              '<strong>' + coverage + '%</strong>' +
            '</div>' +
            '<div class="progress-bar-bg" style="margin-bottom: 16px;">' +
              '<div class="progress-bar-fill progress-green" style="width: ' + coverage + '%;"></div>' +
            '</div>' +
            '<div style="display: flex; gap: 8px;">' +
              '<button class="btn btn-secondary btn-sm full-width" onclick="openCourseDetailsModal(\'' + escapeHtml(c.id) + '\')">View Details</button>' +
              (isAdmin ? '<button class="btn btn-secondary btn-sm full-width" onclick="openEditCourseModal(\'' + escapeHtml(c.id) + '\')">Edit</button>' : '<a href="materials.html" class="btn btn-secondary btn-sm full-width">Notes</a>') +
            '</div>' +
          '</div>';
        }).join("");
      }
    }
  }
}

// Add Course Modal handlers
function openAddCourseModal() {
  if (getActiveRole() !== "admin") {
    showToast("Access Denied", "Only administrators can create courses.", "warning");
    return;
  }
  var errEl = document.getElementById("addCourseErrorMsg");
  if (errEl) errEl.style.display = "none";

  var codeEl = document.getElementById("addCourseCode");
  var titleEl = document.getElementById("addCourseTitle");
  var creditsEl = document.getElementById("addCourseCredits");
  var roomEl = document.getElementById("addCourseRoom");
  var covEl = document.getElementById("addCourseCoverage");
  var semEl = document.getElementById("addCourseSemester");
  var yrEl = document.getElementById("addCourseYear");
  var divEl = document.getElementById("addCourseDivision");
  var statusEl = document.getElementById("addCourseStatus");
  var catEl = document.getElementById("addCourseCategory");

  if (codeEl) codeEl.value = "";
  if (titleEl) titleEl.value = "";
  if (creditsEl) creditsEl.value = "4";
  if (roomEl) roomEl.value = "";
  if (covEl) covEl.value = "0";
  if (semEl) semEl.value = "6";
  if (yrEl) yrEl.value = "3rd Year";
  if (divEl) divEl.value = "All";
  if (statusEl) statusEl.value = "active";
  if (catEl) catEl.value = "core";

  populateDeptDropdowns(_allDepartmentsCache);
  var instEl = document.getElementById("addCourseInstructor");
  if (instEl) instEl.innerHTML = '<option value="">Select Department first...</option>';

  openModal("addCourseModal");
}

function submitCreateCourse() {
  var errEl = document.getElementById("addCourseErrorMsg");
  var btn = document.getElementById("btnSubmitAddCourse");

  var code = (document.getElementById("addCourseCode") ? document.getElementById("addCourseCode").value : "").trim().toUpperCase();
  var title = (document.getElementById("addCourseTitle") ? document.getElementById("addCourseTitle").value : "").trim();
  var dept = (document.getElementById("addCourseDept") ? document.getElementById("addCourseDept").value : "");
  var credits = parseInt(document.getElementById("addCourseCredits") ? document.getElementById("addCourseCredits").value : "3", 10);
  var category = (document.getElementById("addCourseCategory") ? document.getElementById("addCourseCategory").value : "core");
  var semester = parseInt(document.getElementById("addCourseSemester") ? document.getElementById("addCourseSemester").value : "1", 10);
  var year = (document.getElementById("addCourseYear") ? document.getElementById("addCourseYear").value : "1st Year");
  var division = (document.getElementById("addCourseDivision") ? document.getElementById("addCourseDivision").value : "All");
  var room = (document.getElementById("addCourseRoom") ? document.getElementById("addCourseRoom").value : "").trim();
  var coverage = parseInt(document.getElementById("addCourseCoverage") ? document.getElementById("addCourseCoverage").value : "0", 10);
  var instructor = (document.getElementById("addCourseInstructor") ? document.getElementById("addCourseInstructor").value : "");
  var status = (document.getElementById("addCourseStatus") ? document.getElementById("addCourseStatus").value : "active");

  function showError(msg) {
    if (errEl) {
      errEl.textContent = msg;
      errEl.style.display = "block";
    } else {
      showToast("Validation Error", msg, "danger");
    }
  }

  if (!code) return showError("Course code is required.");
  if (!title) return showError("Course title is required.");
  if (!dept) return showError("Please select a department.");
  if (isNaN(credits) || credits <= 0 || credits > 12) return showError("Credits must be a positive integer between 1 and 12.");
  if (isNaN(semester) || semester < 1 || semester > 8) return showError("Semester must be between 1 and 8.");
  if (isNaN(coverage) || coverage < 0 || coverage > 100) return showError("Syllabus coverage must be between 0 and 100%.");

  if (errEl) errEl.style.display = "none";
  if (btn) { btn.disabled = true; btn.textContent = "Creating..."; }

  var payload = {
    code: code,
    title: title,
    department: dept,
    credits: credits,
    category: category,
    semester: semester,
    year: year,
    division: division,
    room: room,
    syllabusCoverage: coverage,
    instructorId: instructor || null,
    status: status
  };

  api("/api/courses", { method: "POST", body: payload })
    .then(function (res) {
      if (btn) { btn.disabled = false; btn.textContent = "Create Course"; }
      closeModal("addCourseModal");
      showToast("Course Created", "Course " + code + " has been added successfully.", "success");
      loadCoursesList();
    })
    .catch(function (err) {
      if (btn) { btn.disabled = false; btn.textContent = "Create Course"; }
      showError(err.message || "Failed to create course.");
    });
}

function openEditCourseModal(courseId) {
  if (getActiveRole() !== "admin") {
    showToast("Access Denied", "Only administrators can edit courses.", "warning");
    return;
  }
  var errEl = document.getElementById("editCourseErrorMsg");
  if (errEl) errEl.style.display = "none";

  api("/api/courses/" + encodeURIComponent(courseId)).then(function (res) {
    var c = res.data;
    if (!c) return;

    document.getElementById("editCourseId").value = c.id;
    document.getElementById("editCourseCode").value = c.code || "";
    document.getElementById("editCourseTitle").value = c.title || "";
    document.getElementById("editCourseCredits").value = c.credits || 3;
    document.getElementById("editCourseCategory").value = (c.category || "core").toLowerCase();
    document.getElementById("editCourseSemester").value = c.semester || 1;
    document.getElementById("editCourseYear").value = c.year || "1st Year";
    document.getElementById("editCourseDivision").value = c.division || "All";
    document.getElementById("editCourseRoom").value = c.room || "";
    document.getElementById("editCourseCoverage").value = c.syllabusCoverage !== undefined ? c.syllabusCoverage : 0;
    document.getElementById("editCourseStatus").value = (c.status || "active").toLowerCase();

    populateDeptDropdowns(_allDepartmentsCache);
    if (document.getElementById("editCourseDept")) {
      document.getElementById("editCourseDept").value = c.departmentId || "";
    }

    onDepartmentChanged("editCourseDept", "editCourseInstructor", c.instructorId || c.instructorCode);
    openModal("editCourseModal");
  }).catch(function (err) {
    showToast("Error", "Could not load course details: " + (err.message || ""), "danger");
  });
}

function submitUpdateCourse() {
  var courseId = document.getElementById("editCourseId").value;
  var errEl = document.getElementById("editCourseErrorMsg");
  var btn = document.getElementById("btnSubmitEditCourse");

  var code = (document.getElementById("editCourseCode").value || "").trim().toUpperCase();
  var title = (document.getElementById("editCourseTitle").value || "").trim();
  var dept = document.getElementById("editCourseDept").value;
  var credits = parseInt(document.getElementById("editCourseCredits").value || "3", 10);
  var category = document.getElementById("editCourseCategory").value;
  var semester = parseInt(document.getElementById("editCourseSemester").value || "1", 10);
  var year = document.getElementById("editCourseYear").value;
  var division = document.getElementById("editCourseDivision").value;
  var room = (document.getElementById("editCourseRoom").value || "").trim();
  var coverage = parseInt(document.getElementById("editCourseCoverage").value || "0", 10);
  var instructor = document.getElementById("editCourseInstructor").value;
  var status = document.getElementById("editCourseStatus").value;

  function showError(msg) {
    if (errEl) {
      errEl.textContent = msg;
      errEl.style.display = "block";
    } else {
      showToast("Validation Error", msg, "danger");
    }
  }

  if (!code) return showError("Course code is required.");
  if (!title) return showError("Course title is required.");
  if (!dept) return showError("Please select a department.");
  if (isNaN(credits) || credits <= 0 || credits > 12) return showError("Credits must be a positive integer between 1 and 12.");
  if (isNaN(semester) || semester < 1 || semester > 8) return showError("Semester must be between 1 and 8.");
  if (isNaN(coverage) || coverage < 0 || coverage > 100) return showError("Syllabus coverage must be between 0 and 100%.");

  if (errEl) errEl.style.display = "none";
  if (btn) { btn.disabled = true; btn.textContent = "Saving..."; }

  var payload = {
    code: code,
    title: title,
    departmentId: dept,
    credits: credits,
    category: category,
    semester: semester,
    year: year,
    division: division,
    room: room,
    syllabusCoverage: coverage,
    instructorId: instructor || null,
    status: status
  };

  api("/api/courses/" + encodeURIComponent(courseId), { method: "PUT", body: payload })
    .then(function (res) {
      if (btn) { btn.disabled = false; btn.textContent = "Save Changes"; }
      closeModal("editCourseModal");
      showToast("Course Updated", "Course " + code + " has been updated successfully.", "success");
      loadCoursesList();
    })
    .catch(function (err) {
      if (btn) { btn.disabled = false; btn.textContent = "Save Changes"; }
      showError(err.message || "Failed to update course.");
    });
}

function openCourseDetailsModal(courseId) {
  api("/api/courses/" + encodeURIComponent(courseId)).then(function (res) {
    var c = res.data;
    if (!c) return;

    var codeEl = document.getElementById("detailCourseCode");
    var titleEl = document.getElementById("detailCourseTitle");
    var deptEl = document.getElementById("detailDept");
    var credEl = document.getElementById("detailCredits");
    var catEl = document.getElementById("detailCategory");
    var semEl = document.getElementById("detailSemester");
    var yrEl = document.getElementById("detailYear");
    var divEl = document.getElementById("detailDivision");
    var roomEl = document.getElementById("detailRoom");
    var instEl = document.getElementById("detailInstructor");
    var statusEl = document.getElementById("detailStatus");
    var covText = document.getElementById("detailCoverageText");
    var covBar = document.getElementById("detailCoverageBar");

    if (codeEl) codeEl.textContent = c.code || "-";
    if (titleEl) titleEl.textContent = c.title || "-";
    if (deptEl) deptEl.textContent = (c.department || "-") + (c.departmentCode ? " (" + c.departmentCode + ")" : "");
    if (credEl) credEl.textContent = (c.credits || 3) + " Credits";
    if (catEl) catEl.textContent = (c.category || "Core").toUpperCase();
    if (semEl) semEl.textContent = "Semester " + (c.semester || "-");
    if (yrEl) yrEl.textContent = c.year || "-";
    if (divEl) divEl.textContent = c.division || "All";
    if (roomEl) roomEl.textContent = c.room || "TBA";
    if (instEl) instEl.textContent = c.instructor || "Unassigned";

    if (statusEl) {
      var isAct = (c.status || "active").toLowerCase() === "active";
      statusEl.textContent = isAct ? "Active" : "Inactive";
      statusEl.className = isAct ? "badge badge-success" : "badge badge-secondary";
    }

    var cov = c.syllabusCoverage !== undefined ? c.syllabusCoverage : 0;
    if (covText) covText.textContent = cov + "%";
    if (covBar) covBar.style.width = cov + "%";

    // Related Academic Records counts
    var countEnr = document.getElementById("countEnrolledStudents");
    var countAtt = document.getElementById("countAttendanceSessions");
    var countAsg = document.getElementById("countAssignments");
    var countRes = document.getElementById("countResults");
    var countMat = document.getElementById("countStudyMaterials");
    var countFa = document.getElementById("countFacultyAssignments");

    if (countEnr) countEnr.textContent = c.enrolledStudentsCount !== undefined ? c.enrolledStudentsCount : 0;
    if (countAtt) countAtt.textContent = c.attendanceSessionsCount !== undefined ? c.attendanceSessionsCount : 0;
    if (countAsg) countAsg.textContent = c.assignmentsCount !== undefined ? c.assignmentsCount : 0;
    if (countRes) countRes.textContent = c.resultsCount !== undefined ? c.resultsCount : 0;
    if (countMat) countMat.textContent = c.studyMaterialsCount !== undefined ? c.studyMaterialsCount : 0;
    if (countFa) countFa.textContent = c.facultyAssignmentsCount !== undefined ? c.facultyAssignmentsCount : 0;

    openModal("courseDetailsModal");
  }).catch(function (err) {
    showToast("Error", "Could not load course details: " + (err.message || ""), "danger");
  });
}

function toggleCourseStatus(courseId, currentStatus) {
  var newStatus = (currentStatus || "active").toLowerCase() === "active" ? "inactive" : "active";
  api("/api/courses/" + encodeURIComponent(courseId) + "/status", {
    method: "PATCH",
    body: { status: newStatus }
  }).then(function (res) {
    showToast("Status Updated", res.message || ("Course marked as " + newStatus), "success");
    loadCoursesList();
  }).catch(function (err) {
    showToast("Error", err.message || "Failed to update status", "danger");
  });
}

function deleteCourse(courseId) {
  if (!confirm("Are you sure you want to delete this course? If academic records exist, it will need to be deactivated instead.")) {
    return;
  }
  api("/api/courses/" + encodeURIComponent(courseId), { method: "DELETE" })
    .then(function (res) {
      showToast("Course Deleted", res.message || "Course deleted successfully.", "success");
      loadCoursesList();
    })
    .catch(function (err) {
      if (err.canDeactivate || (err.message && err.message.indexOf("associated academic records") !== -1)) {
        if (confirm(err.message + "\n\nWould you like to deactivate this course instead?")) {
          toggleCourseStatus(courseId, "active");
        }
      } else {
        showToast("Cannot Delete Course", err.message || "Failed to delete course.", "danger");
      }
    });
}

// ---- Profile page ---------------------------------------------------------------
function initProfile(user, role) {
  var nameEl = document.getElementById("profileName");
  if (!nameEl) return;

  function render(u) {
    nameEl.textContent = u.name;
    var roleTag = document.getElementById("profileRoleTag");
    if (roleTag) roleTag.textContent = u.roleLabel || role.toUpperCase();
    var pId = document.getElementById("pId");
    var pEmail = document.getElementById("pEmail");
    var pDept = document.getElementById("pDept");
    var pPhone = document.getElementById("pPhone");
    var pExtra = document.getElementById("pExtra");
    if (pId) pId.textContent = u.publicId;
    if (pEmail) pEmail.textContent = u.email;
    if (pDept) pDept.textContent = u.dept;
    if (pPhone) pPhone.textContent = u.phone || "-";
    if (pExtra) pExtra.textContent = u.year || u.designation || "-";
  }
  render(user);

  var editBtn = document.getElementById("editProfileBtn");
  var detailsBox = document.getElementById("profileDetails");
  var editBox = document.getElementById("profileEditForm");
  var editing = false;

  if (editBtn && detailsBox && editBox) {
    editBtn.addEventListener("click", function () {
      if (!editing) {
        document.getElementById("editName").value = user.name;
        document.getElementById("editEmail").value = user.email;
        document.getElementById("editDept").value = user.dept || "";
        document.getElementById("editPhone").value = user.phone || "";
        detailsBox.style.display = "none";
        editBox.style.display = "block";
        editBtn.textContent = "Save Changes";
        editBtn.className = "btn btn-success btn-sm";
        editing = true;
      } else {
        var payload = {
          name: document.getElementById("editName").value.trim(),
          email: document.getElementById("editEmail").value.trim(),
          phone: document.getElementById("editPhone").value.trim(),
          dept: document.getElementById("editDept").value.trim()
        };
        setButtonLoading(editBtn, "Saving Profile...");
        api("/api/profile", { method: "PUT", body: payload }).then(function (res) {
          user = res.data;
          CURRENT_USER = res.data;
          render(user);
          var topUser = document.getElementById("topbarUserName");
          if (topUser) topUser.textContent = user.name;
          detailsBox.style.display = "block";
          editBox.style.display = "none";
          resetButton(editBtn, "Edit Profile");
          editBtn.className = "btn btn-secondary btn-sm";
          editing = false;
          highlightRow(detailsBox, "update");
          showToast("Profile Updated", "Your profile details have been saved.", "success");
        }).catch(function (e) {
          resetButton(editBtn, "Save Changes");
          showToast("Update Failed", e.message || "Could not update profile.", "error");
        });
      }
    });
  }
}

// ---- Search and category filters (unchanged, purely client-side) --------------
function initSearchAndFilter() {
  var searchInput = document.getElementById("globalSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      var query = this.value.toLowerCase();
      var items = document.querySelectorAll(".filterable-item, .data-table tbody tr");
      items.forEach(function (item) {
        item.style.display = item.textContent.toLowerCase().includes(query) ? "" : "none";
      });
    });
  }

  var filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      filterBtns.forEach(function (b) { b.classList.replace("btn-primary", "btn-secondary"); });
      this.classList.replace("btn-secondary", "btn-primary");

      var filter = this.getAttribute("data-filter");
      document.querySelectorAll(".filterable-item").forEach(function (item) {
        var cat = item.getAttribute("data-category");
        item.style.display = (filter === "all" || cat === filter) ? "" : "none";
      });
    });
  });
}

// ---- Attendance module ------------------------------------------------------------
function initAttendance(role) {
  var summaryBody = document.querySelector('[data-role="attendance-summary-body"]');
  if (summaryBody) {
    api("/api/attendance/summary").then(function (res) {
      var rows = res.data.rows;
      summaryBody.innerHTML = rows.length ? rows.map(function (r) {
        return '<tr><td><strong>' + r.courseCode + '</strong></td><td>' + r.courseTitle + '</td>' +
          '<td>' + (r.instructor || '-') + '</td><td>' + r.held + '</td><td>' + r.attended + '</td>' +
          '<td><strong>' + r.percentage + '%</strong></td>' +
          '<td><span class="badge ' + (r.percentage >= 75 ? 'badge-success' : 'badge-warning') + '">' + r.status + '</span></td></tr>';
      }).join("") : '<tr><td colspan="7" style="text-align:center; padding:24px; color: var(--text-muted);">No attendance data yet.</td></tr>';

      var overall = res.data.overall;
      var countEl = document.getElementById("presentCountDisplay");
      if (countEl && role === "student") {
        countEl.textContent = "Overall: " + overall.percentage + "% Attendance";
      }
    }).catch(function () {});
  }

  var facultyCard = document.getElementById("facultyRollCallCard");
  if (role === "student") {
    if (facultyCard) facultyCard.remove();
  } else if (role === "faculty") {
    if (facultyCard) {
      facultyCard.style.display = "block";
      initFacultyAttendanceControls();
    }
  }

  function initFacultyAttendanceControls() {
    var courseSelect = document.getElementById("facultyRollCourseSelect");
    var divSelect = document.getElementById("facultyRollDivisionSelect");
    var tbody = document.getElementById("rollCallTableBody") || (facultyCard ? facultyCard.querySelector(".data-table tbody") : null);

    api("/api/courses").then(function (res) {
      var courses = res.data || [];
      if (courseSelect && courses.length) {
        courseSelect.innerHTML = courses.map(function (c) {
          return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
        }).join("");
      }
      loadRollCall();
    }).catch(function () {
      loadRollCall();
    });

    if (courseSelect) courseSelect.addEventListener("change", loadRollCall);
    if (divSelect) divSelect.addEventListener("change", loadRollCall);

    function loadRollCall() {
      var rollCourse = courseSelect ? courseSelect.value : (facultyCard ? facultyCard.getAttribute("data-course") || "CS601" : "CS601");
      var rollDiv = divSelect ? divSelect.value : "A";
      api("/api/attendance/roll-call?courseCode=" + encodeURIComponent(rollCourse) + "&division=" + encodeURIComponent(rollDiv)).then(function (res) {
        if (!tbody) return;
        var roster = res.data.roster || [];
        if (!roster.length) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">No students enrolled in Division ' + escapeHtml(rollDiv) + ' for ' + escapeHtml(rollCourse) + '.</td></tr>';
          return;
        }
        tbody.innerHTML = roster.map(function (s) {
          var cls = s.status === "present" ? "btn-success" : s.status === "late" ? "btn-warning" : "btn-danger";
          var label = s.status === "present" ? "Present" : s.status === "late" ? "Late" : "Absent";
          return '<tr data-student-id="' + s.studentId + '">' +
            '<td><strong>' + escapeHtml(s.prn || s.studentId) + '</strong></td>' +
            '<td>' + escapeHtml(s.name) + '</td>' +
            '<td>' + escapeHtml(s.department || '-') + '</td>' +
            '<td><span class="badge badge-info">Div ' + escapeHtml(s.division || rollDiv) + '</span></td>' +
            '<td><button type="button" class="btn btn-sm ' + cls + ' attend-toggle">' + label + '</button></td></tr>';
        }).join("");
        wireAttendanceToggles();
      }).catch(function () {});
    }

    function wireAttendanceToggles() {
      if (!tbody) return;
      tbody.querySelectorAll(".attend-toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
          if (getActiveRole() !== "faculty") {
            alert("Permission Denied: Only faculty members can mark attendance.");
            return;
          }
          if (this.classList.contains("btn-success")) {
            this.className = "btn btn-sm btn-danger attend-toggle";
            this.textContent = "Absent";
          } else if (this.classList.contains("btn-danger")) {
            this.className = "btn btn-sm btn-warning attend-toggle";
            this.textContent = "Late";
          } else {
            this.className = "btn btn-sm btn-success attend-toggle";
            this.textContent = "Present";
          }
        });
      });
    }

    window.saveFacultyAttendance = function () {
      if (getActiveRole() !== "faculty") {
        showToast("Access Restricted", "Only faculty members can save attendance.", "warning");
        return;
      }
      var saveBtn = document.getElementById("saveAttendanceBtn") || (facultyCard ? facultyCard.querySelector("#saveAttendanceBtn") : null);
      var rollCourse = courseSelect ? courseSelect.value : "CS601";
      var rollDiv = divSelect ? divSelect.value : "A";
      var records = [];
      var presentCount = 0;
      var lateCount = 0;
      var absentCount = 0;

      if (tbody) {
        tbody.querySelectorAll("tr[data-student-id]").forEach(function (row) {
          var btn = row.querySelector(".attend-toggle");
          if (btn) {
            var status = btn.classList.contains("btn-success") ? "present" :
                         btn.classList.contains("btn-warning") ? "late" : "absent";
            if (status === "present") presentCount++;
            else if (status === "late") lateCount++;
            else absentCount++;
            records.push({ studentId: row.getAttribute("data-student-id"), status: status });
          }
        });
      }

      setButtonLoading(saveBtn, "Saving Attendance...");

      api("/api/attendance/roll-call", {
        method: "POST",
        body: { courseCode: rollCourse, division: rollDiv, records: records }
      }).then(function (res) {
        resetButton(saveBtn, '<span class="badge-saved">✓ Attendance Saved</span>');
        setTimeout(function () {
          resetButton(saveBtn, "Save Attendance");
        }, 2500);

        var bannerContainer = document.getElementById("rollCallStatusBanner");
        if (!bannerContainer && facultyCard) {
          bannerContainer = document.createElement("div");
          bannerContainer.id = "rollCallStatusBanner";
          var header = facultyCard.querySelector(".card-header-row");
          if (header) header.insertAdjacentElement("afterend", bannerContainer);
        }
        if (bannerContainer) {
          bannerContainer.innerHTML =
            '<div class="inline-banner inline-banner-success">' +
              '<span>✓ Attendance recorded for <strong>' + escapeHtml(rollCourse) + ' (Div ' + escapeHtml(rollDiv) + ')</strong>: ' +
              '<strong>' + presentCount + ' Present</strong>, <strong>' + absentCount + ' Absent</strong>, <strong>' + lateCount + ' Late</strong>. Records committed to academic ledger.</span>' +
              '<span class="inline-banner-close" onclick="this.parentElement.remove()">&times;</span>' +
            '</div>';
        }
        if (tbody) {
          tbody.querySelectorAll("tr[data-student-id]").forEach(function (r) {
            highlightRow(r, "update");
          });
        }
        showToast("Attendance Recorded", presentCount + " Present, " + absentCount + " Absent (" + rollCourse + " Div " + rollDiv + ")", "success");
      }).catch(function (e) {
        resetButton(saveBtn, "Save Attendance");
        var bannerContainer = document.getElementById("rollCallStatusBanner");
        if (bannerContainer) {
          bannerContainer.innerHTML =
            '<div class="inline-banner inline-banner-error">' +
              '<span>⚠️ Could not save attendance: ' + escapeHtml(e.message || "Unknown error occurred.") + '</span>' +
              '<span class="inline-banner-close" onclick="this.parentElement.remove()">&times;</span>' +
            '</div>';
        }
        showToast("Save Failed", e.message || "Could not save attendance.", "error");
      });
    };
  }
}

// ---- Results module ----------------------------------------------------------------
// Note: the three views (student grade-card / faculty marks-entry / admin
// department publish-control) use genuinely different table shapes in the
// original design, so each is wired to match its own real columns rather
// than one generic renderer.
function initResults(role) {
  var studentView = document.getElementById("studentResultView");
  var facultyView = document.getElementById("facultyResultView");
  var adminView = document.getElementById("adminResultView");
  if (!studentView && !facultyView && !adminView) return;

  if (role === "student") {
    if (studentView) { studentView.style.display = "block"; loadStudentResults(studentView); }
    if (facultyView) facultyView.remove();
    if (adminView) adminView.remove();
  } else if (role === "faculty") {
    if (facultyView) { facultyView.style.display = "block"; loadFacultyMarksSheet(facultyView); }
    if (studentView) studentView.remove();
    if (adminView) adminView.remove();
  } else if (role === "admin") {
    if (adminView) {
      adminView.style.display = "block";
      loadAdminResults(adminView);
    }
    if (studentView) studentView.remove();
    if (facultyView) facultyView.remove();
  }

  function loadStudentResults(container) {
    var tbody = document.getElementById("studentResultsTableBody") || container.querySelector(".data-table tbody");
    if (!tbody) return;
    api("/api/results").then(function (res) {
      var rows = res.data || [];
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color: var(--text-muted);">Results have not been published yet.</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        var pass = r.total >= 40;
        return '<tr><td><strong>' + escapeHtml(r.courseCode) + '</strong></td><td>' + escapeHtml(r.courseTitle) + '</td>' +
          '<td>' + r.internal + '</td><td>' + r.endSem + '</td><td><strong>' + r.total + '</strong></td>' +
          '<td><span class="badge badge-' + (pass ? 'success' : 'danger') + '">' + escapeHtml(r.grade) + '</span></td>' +
          '<td>-</td><td><span class="badge badge-' + (pass ? 'success' : 'danger') + '">' + (pass ? 'Pass' : 'Fail') + '</span></td></tr>';
      }).join("");
    }).catch(function () {});
  }

  function loadAdminResults(container) {
    var tbody = document.getElementById("adminResultsTableBody") || container.querySelector("#adminStudentResultsTable tbody");
    var countBadge = document.getElementById("adminResultCountBadge");
    if (!tbody) return;

    api("/api/results").then(function (res) {
      var rows = res.data || [];
      if (countBadge) {
        countBadge.textContent = rows.length + (rows.length === 1 ? " Student Record" : " Student Records");
      }
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);">No student scorecards recorded yet.</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function (r) {
        var pass = r.total >= 40;
        var pubBadge = r.isPublished
          ? '<span class="badge badge-success result-status-badge">Published</span>'
          : '<span class="badge badge-warning result-status-badge">Unpublished</span>';
        var btnClass = r.isPublished ? 'btn-warning' : 'btn-success';
        var btnText = r.isPublished ? 'Unpublish' : 'Publish';

        return '<tr class="filterable-item">' +
          '<td><strong>' + escapeHtml(r.studentId) + '</strong></td>' +
          '<td>' + escapeHtml(r.studentName || '-') + '</td>' +
          '<td>' + escapeHtml(r.courseCode) + ' <span style="font-size:12px; color:var(--text-muted);">(' + escapeHtml(r.courseTitle || '') + ')</span></td>' +
          '<td>' + r.internal + '</td>' +
          '<td>' + r.endSem + '</td>' +
          '<td><strong>' + r.total + '</strong></td>' +
          '<td><span class="badge badge-' + (pass ? 'success' : 'danger') + '">' + escapeHtml(r.grade) + '</span></td>' +
          '<td>' + pubBadge + '</td>' +
          '<td><button class="btn ' + btnClass + ' btn-sm pub-toggle-btn" data-result-id="' + r.id + '" onclick="togglePublish(this)">' + btnText + '</button></td>' +
          '</tr>';
      }).join("");
    }).catch(function (err) {
      console.log("Could not load admin results:", err.message);
    });
  }

  function loadFacultyMarksSheet(container) {
    var courseSelect = document.getElementById("facultyResultCourseSelect") || container.querySelector(".form-select");
    var divSelect = document.getElementById("facultyResultDivisionSelect");
    var tbody = container.querySelector(".data-table tbody");
    var heading = container.querySelector(".card:last-child h3");
    if (!tbody) return;

    api("/api/courses").then(function (res) {
      var courses = res.data || [];
      if (courseSelect && courses.length) {
        courseSelect.innerHTML = courses.map(function (c) {
          return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
        }).join("");
      }
      render();
    }).catch(function () {
      render();
    });

    if (courseSelect) courseSelect.addEventListener("change", render);
    if (divSelect) divSelect.addEventListener("change", render);

    function courseCodeFromSelect() {
      if (!courseSelect) return "CS601";
      return (courseSelect.value || courseSelect.options[courseSelect.selectedIndex].text).split(" ")[0].trim();
    }

    function render() {
      var courseCode = courseCodeFromSelect();
      var division = divSelect ? divSelect.value : "A";
      if (heading) heading.textContent = "Student Marks Entry Sheet (" + courseCode + " - Div " + division + ")";
      api("/api/attendance/roll-call?courseCode=" + encodeURIComponent(courseCode) + "&division=" + encodeURIComponent(division)).then(function (res) {
        var roster = res.data.roster || [];
        if (!roster.length) {
          tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">No students found in ' + escapeHtml(courseCode) + ' (Div ' + escapeHtml(division) + ').</td></tr>';
          return;
        }
        tbody.innerHTML = roster.map(function (s) {
          return '<tr data-student-id="' + s.studentId + '" data-course="' + courseCode + '">' +
            '<td><strong>' + escapeHtml(s.prn || s.studentId) + '</strong></td>' +
            '<td>' + escapeHtml(s.name) + '</td>' +
            '<td><input type="number" class="form-input marks-input" value="0" style="width: 90px; padding: 6px;" min="0" max="100"></td>' +
            '<td><span class="grade-preview">-</span></td>' +
            '<td><button class="btn btn-secondary btn-sm save-marks-btn" type="button">Save</button></td></tr>';
        }).join("");
        wireSaveButtons();
      }).catch(function () {});
    }

    function wireSaveButtons() {
      tbody.querySelectorAll(".save-marks-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var row = this.closest("tr");
          var studentId = row.getAttribute("data-student-id");
          var courseCode = row.getAttribute("data-course");
          var marksInput = row.querySelector(".marks-input");
          var marks = marksInput.value;

          setButtonLoading(btn, "Saving...");
          marksInput.disabled = true;

          api("/api/results", { method: "POST", body: { studentId: studentId, courseCode: courseCode, marks: marks } })
            .then(function (res) {
              var pass = res.data.total >= 40;
              row.querySelector(".grade-preview").innerHTML =
                '<span class="badge badge-' + (pass ? 'success' : 'danger') + '">' + escapeHtml(res.data.grade) + ' (' + res.data.total + '/100)</span>';
              highlightRow(row, "update");
              resetButton(btn, '<span class="badge-saved">✓ Saved</span>');
              setTimeout(function () {
                resetButton(btn, "Save");
              }, 2500);
              showToast("Marks Recorded", studentId + ": " + res.data.total + "/100 • Grade " + res.data.grade, "success");
            }).catch(function (e) {
              resetButton(btn, "Save");
              showToast("Save Failed", e.message || "Could not save marks.", "error");
            }).finally(function () {
              marksInput.disabled = false;
            });
        });
      });
    }
  }

  window.togglePublish = function (btn) {
    if (getActiveRole() !== "admin") {
      showToast("Access Restricted", "Only Administrators can publish or unpublish examination results.", "warning");
      return;
    }
    var resultId = btn.getAttribute("data-result-id");
    var row = btn.closest("tr");
    var badge = row ? row.querySelector(".result-status-badge") : null;
    var willPublish = btn.classList.contains("btn-success");

    function applyVisual(isPublished) {
      if (isPublished) {
        btn.className = "btn btn-warning btn-sm pub-toggle-btn";
        resetButton(btn, "Unpublish");
        if (badge) { badge.className = "badge badge-success result-status-badge"; badge.textContent = "Published"; }
      } else {
        btn.className = "btn btn-success btn-sm pub-toggle-btn";
        resetButton(btn, "Publish");
        if (badge) { badge.className = "badge badge-warning result-status-badge"; badge.textContent = "Unpublished"; }
      }
      if (row) highlightRow(row, "update");
    }

    if (!resultId) {
      // Department-level demo row with no backing Result id: visual-only toggle.
      applyVisual(willPublish);
      return;
    }

    setButtonLoading(btn, willPublish ? "Publishing..." : "Unpublishing...");

    api("/api/results/" + resultId + "/publish", { method: "PUT", body: { isPublished: willPublish } })
      .then(function (res) {
        applyVisual(res.data.isPublished);
        showToast("Publication Status Updated", "Scorecard is now " + (res.data.isPublished ? "Published" : "Unpublished") + ".", "info");
      })
      .catch(function (e) {
        resetButton(btn, willPublish ? "Publish" : "Unpublish");
        showToast("Update Failed", e.message || "Could not update publish status.", "error");
      });
  };
}

// ---- Notices module ------------------------------------------------------------------
function initNotices(role) {
  var postBtn = document.getElementById("postNoticeBtn");
  var modal = document.getElementById("newNoticeModal");
  var list = document.querySelector(".item-list");

  if (role === "student") {
    if (postBtn) postBtn.remove();
    if (modal) modal.remove();
  } else if (modal) {
    var publishBtn = document.getElementById("submitPublishNoticeBtn") || modal.querySelector(".modal-footer .btn-primary");
    if (publishBtn) {
      publishBtn.setAttribute("onclick", "");
      publishBtn.addEventListener("click", function () {
        var titleInp = document.getElementById("modalNoticeTitle");
        var catSelect = document.getElementById("modalNoticeCat");
        var bodyInp = document.getElementById("modalNoticeBody");
        var title = titleInp ? titleInp.value.trim() : "";
        var category = catSelect ? catSelect.value : "General";
        var body = bodyInp ? bodyInp.value.trim() : "";

        var modalBody = modal.querySelector(".modal-body");
        clearInlineErrors(modalBody);

        if (!title || !body) {
          showInlineError(modalBody, "Please provide both notice title and announcement details.");
          return;
        }

        setButtonLoading(publishBtn, "Broadcasting...");

        api("/api/notices", { method: "POST", body: { title: title, category: category, body: body } })
          .then(function (res) {
            closeModal("newNoticeModal");
            if (titleInp) titleInp.value = "";
            if (bodyInp) bodyInp.value = "";

            var newNotice = res.data || { title: title, category: category, body: body, createdAt: new Date().toISOString() };
            var cat = (newNotice.category || "General").toLowerCase();
            var posted = "Just now";

            var deleteBtn = (role === "admin" || role === "faculty")
              ? ' <button class="btn btn-danger btn-sm" style="padding: 2px 8px; font-size: 11.5px;" onclick="deleteNotice(' + (newNotice.id || '') + ', \'' + escapeHtml(newNotice.title).replace(/'/g, "\\'") + '\', this)">🗑️ Delete</button>'
              : '';

            var card = document.createElement("div");
            card.className = "card filterable-item row-highlight-new";
            card.setAttribute("data-category", cat);
            card.innerHTML =
              '<div class="card-header-row">' +
                '<div><span class="badge badge-primary">' + escapeHtml(newNotice.category || "General") + '</span></div>' +
                '<div style="display:flex; align-items:center; gap:8px;">' +
                  '<span class="list-item-date">' + posted + '</span>' +
                  deleteBtn +
                '</div>' +
              '</div>' +
              '<h3 style="font-size: 18px; margin-bottom: 8px;">' + escapeHtml(newNotice.title) + '</h3>' +
              '<p style="font-size: 14px; color: var(--text-muted); line-height: 1.6; margin-bottom: 12px;">' + escapeHtml(newNotice.body) + '</p>' +
              '<div style="font-size: 12.5px; color: var(--text-light);">Issued by: ' + escapeHtml(newNotice.postedBy || (CURRENT_USER ? CURRENT_USER.name : "Campus Admin")) + '</div>';

            if (list) {
              var empty = list.querySelector(".empty-state-box, .card:not(.filterable-item)");
              if (empty) empty.remove();
              list.prepend(card);
            }
            showToast("Notice Published", "Announcement broadcasted successfully to campus.", "success");
          })
          .catch(function (e) {
            showInlineError(modalBody, e.message || "Could not post notice.");
            showToast("Publish Failed", e.message || "Could not post notice.", "error");
          })
          .finally(function () {
            resetButton(publishBtn, "Publish Notice");
          });
      });
    }
  }

  if (list) loadNotices();

  function loadNotices() {
    api("/api/notices").then(function (res) {
      var notices = res.data || [];
      if (!notices.length) {
        renderEmptyState(list, {
          icon: "📢",
          title: "No Notices Posted",
          message: "There are currently no announcements on the campus notice board.",
          actionText: (role === "admin" || role === "faculty") ? "Post Notice" : null,
          onAction: function () { openModal("newNoticeModal"); }
        });
        return;
      }
      list.innerHTML = notices.map(function (n) {
        var cat = (n.category || "General").toLowerCase();
        var posted = n.createdAt ? new Date(n.createdAt).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" }) : "";
        var deleteBtn = (role === "admin" || role === "faculty")
          ? ' <button class="btn btn-danger btn-sm" style="padding: 2px 8px; font-size: 11.5px;" onclick="deleteNotice(' + n.id + ', \'' + escapeHtml(n.title).replace(/'/g, "\\'") + '\', this)">🗑️ Delete</button>'
          : '';

        return '<div class="card filterable-item" data-category="' + cat + '">' +
          '<div class="card-header-row">' +
            '<div><span class="badge badge-primary">' + escapeHtml(n.category || "General") + '</span></div>' +
            '<div style="display:flex; align-items:center; gap:8px;">' +
              '<span class="list-item-date">' + posted + '</span>' +
              deleteBtn +
            '</div>' +
          '</div>' +
          '<h3 style="font-size: 18px; margin-bottom: 8px;">' + escapeHtml(n.title) + '</h3>' +
          '<p style="font-size: 14px; color: var(--text-muted); line-height: 1.6; margin-bottom: 12px;">' + escapeHtml(n.body) + '</p>' +
          '<div style="font-size: 12.5px; color: var(--text-light);">Issued by: ' + escapeHtml(n.postedBy || "Campus Admin") + '</div>' +
        '</div>';
      }).join("");
    }).catch(function () {});
  }
}

window.deleteNotice = function (id, title, btn) {
  showConfirmModal({
    title: "Delete Notice?",
    message: "Are you sure you want to delete '" + title + "'? This announcement will be removed immediately from all student and faculty notice boards.",
    confirmText: "Delete Notice",
    danger: true,
    onConfirm: function (done) {
      api("/api/notices/" + encodeURIComponent(id), { method: "DELETE" })
        .then(function () {
          done();
          var card = btn ? btn.closest(".card") : null;
          if (card) {
            removeRowAnimated(card, function () {
              var list = document.querySelector(".item-list");
              if (list && !list.querySelectorAll(".filterable-item").length) {
                var role = getActiveRole();
                initNotices(role);
              }
            });
          }
          showToast("Notice Deleted", "'" + title + "' has been removed.", "info");
        })
        .catch(function (err) {
          done();
          showToast("Delete Failed", err.message || "Could not delete notice.", "error");
        });
    }
  });
};

// ---- Study Materials module -------------------------------------------------------
function initMaterials(role) {
  var tbody = document.getElementById("materialsTableBody");
  var uploadBtn = document.getElementById("uploadMaterialBtn");
  var modal = document.getElementById("uploadMaterialModal");
  if (!tbody && !uploadBtn && !modal) return;

  if (role === "student") {
    if (uploadBtn) uploadBtn.remove();
    if (modal) modal.remove();
  } else if (modal) {
    var courseSelect = document.getElementById("materialCourse");
    if (courseSelect) {
      api("/api/courses").then(function (res) {
        var courses = res.data || [];
        if (courses.length) {
          courseSelect.innerHTML = courses.map(function (c) {
            return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
          }).join("");
        }
      }).catch(function () {});
    }

    var fileInput = document.getElementById("materialFile");
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        var metaBox = document.getElementById("materialFileMeta");
        var file = fileInput.files && fileInput.files[0];
        if (!metaBox) return;
        if (!file) {
          metaBox.style.display = "none";
          metaBox.innerHTML = "";
          return;
        }
        var sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        var ext = file.name.split(".").pop().toUpperCase();
        metaBox.innerHTML =
          '<div style="display:flex; justify-content:space-between; align-items:center;">' +
            '<div>' +
              '<strong>📎 Selected File:</strong> ' + escapeHtml(file.name) +
              '<div style="font-size:11.5px; color:var(--text-muted); margin-top:2px;">Size: ' + sizeMb + ' MB • Format: ' + ext + '</div>' +
            '</div>' +
            '<span class="badge badge-primary">' + ext + '</span>' +
          '</div>';
        metaBox.style.display = "block";
      });
    }

    var uploadConfirmBtn = document.getElementById("confirmUploadMaterialBtn") || modal.querySelector(".modal-footer .btn-primary");
    if (uploadConfirmBtn) {
      uploadConfirmBtn.setAttribute("onclick", "");
      uploadConfirmBtn.addEventListener("click", function () {
        var titleInp = document.getElementById("materialTitle");
        var title = (titleInp ? titleInp.value : "").trim();
        var category = document.getElementById("materialType") ? document.getElementById("materialType").value : "Lecture Notes";
        var division = document.getElementById("materialDivision") ? document.getElementById("materialDivision").value : "All";
        var file = fileInput && fileInput.files && fileInput.files[0];

        var modalBody = modal.querySelector(".modal-body");
        clearInlineErrors(modalBody);

        if (!title || !file) {
          showInlineError(modalBody, "Please provide a document title and select a valid file (PDF, PPT, or PPTX).");
          return;
        }

        var courseVal = courseSelect ? courseSelect.value : "";
        var courseCode = courseVal.split(" - ")[0].trim();

        var form = new FormData();
        form.append("title", title);
        form.append("category", category);
        form.append("courseCode", courseCode);
        form.append("division", division);
        form.append("file", file);

        setButtonLoading(uploadConfirmBtn, "Uploading Material...");

        api("/api/materials", { method: "POST", body: form }).then(function (res) {
          closeModal("uploadMaterialModal");
          if (titleInp) titleInp.value = "";
          if (fileInput) fileInput.value = "";
          var metaBox = document.getElementById("materialFileMeta");
          if (metaBox) { metaBox.style.display = "none"; metaBox.innerHTML = ""; }

          var m = res.data || {
            title: title,
            category: category,
            courseCode: courseCode,
            division: division,
            sizeKb: file ? Math.round(file.size / 1024) : 0,
            uploadedBy: CURRENT_USER ? CURRENT_USER.name : "Faculty",
            filename: file ? file.name : ""
          };

          var divBadge = m.division === "All"
            ? '<span class="badge badge-secondary">All Divisions</span>'
            : '<span class="badge badge-info">Div ' + escapeHtml(m.division) + '</span>';

          var downloadBtn = m.downloadUrl
            ? '<a class="btn btn-secondary btn-sm" href="' + escapeHtml(m.downloadUrl) + '" target="_blank" download>📥 Download</a>'
            : '<span style="color:var(--text-muted)">Uploaded</span>';

          var deleteBtn = ' <button class="btn btn-danger btn-sm" onclick="deleteStudyMaterial(' + (m.id || '') + ', \'' + escapeHtml(m.title).replace(/'/g, "\\'") + '\', this)">🗑️ Delete</button>';

          var row = document.createElement("tr");
          row.className = "filterable-item row-highlight-new";
          row.setAttribute("data-category", (m.category || "notes").toLowerCase());
          var docName = m.fileName || m.filename || "";
          row.innerHTML =
            '<td><strong>📄 ' + escapeHtml(m.title) + '</strong>' + (docName ? ('<div style="font-size:11.5px;color:var(--text-muted);">' + escapeHtml(docName) + '</div>') : '') + '</td>' +
            '<td>' + escapeHtml(m.subject || m.courseCode || '-') + '</td>' +
            '<td>' + divBadge + '</td>' +
            '<td><span class="badge badge-primary">' + escapeHtml(m.category) + '</span></td>' +
            '<td>' + escapeHtml(m.uploadedBy || '-') + '</td>' +
            '<td>' + (m.sizeKb ? m.sizeKb + ' KB' : '-') + '</td>' +
            '<td style="white-space:nowrap;">' + downloadBtn + deleteBtn + '</td>';

          var targetBody = document.getElementById("materialsTableBody");
          if (targetBody) {
            var emptyRow = targetBody.querySelector(".empty-state-row");
            if (emptyRow) emptyRow.remove();
            targetBody.prepend(row);
          }

          showToast("Study Material Uploaded", "Successfully added '" + title + "' to the repository.", "success");
        }).catch(function (e) {
          showInlineError(modalBody, e.message || "Could not upload study material.");
          showToast("Upload Failed", e.message || "Could not upload material.", "error");
        }).finally(function () {
          resetButton(uploadConfirmBtn, "Upload File");
        });
      });
    }
  }

  if (tbody) loadMaterials();

  function loadMaterials() {
    var targetBody = document.getElementById("materialsTableBody");
    if (!targetBody) return;

    api("/api/materials").then(function (res) {
      var items = res.data || [];
      if (!items.length) {
        renderEmptyState(targetBody, {
          icon: "📁",
          title: "No Study Materials Found",
          message: "There are currently no notes, lab manuals or papers in the repository.",
          actionText: (role === "admin" || role === "faculty") ? "Upload Material" : null,
          onAction: function () { openModal("uploadMaterialModal"); },
          colSpan: 7
        });
        return;
      }
      targetBody.innerHTML = items.map(function (m) {
        var divBadge = m.division === "All"
          ? '<span class="badge badge-secondary">All Divisions</span>'
          : '<span class="badge badge-info">Div ' + escapeHtml(m.division) + '</span>';

        var downloadUrl = m.downloadUrl;
        var downloadBtn = downloadUrl
          ? '<a class="btn btn-secondary btn-sm" href="' + escapeHtml(downloadUrl) + '" target="_blank" download>📥 Download</a>'
          : '<span style="color:var(--text-muted)">Unavailable</span>';

        var deleteBtn = (role === "admin" || role === "faculty")
          ? ' <button class="btn btn-danger btn-sm" onclick="deleteStudyMaterial(' + m.id + ', \'' + escapeHtml(m.title).replace(/'/g, "\\'") + '\', this)">🗑️ Delete</button>'
          : '';

        var docName = m.fileName || m.filename || "";
        return '<tr class="filterable-item" data-category="' + (m.category || "notes").toLowerCase() + '">' +
          '<td><strong>📄 ' + escapeHtml(m.title) + '</strong>' + (docName ? ('<div style="font-size:11.5px;color:var(--text-muted);">' + escapeHtml(docName) + '</div>') : '') + '</td>' +
          '<td>' + escapeHtml(m.subject || m.courseCode || '-') + '</td>' +
          '<td>' + divBadge + '</td>' +
          '<td><span class="badge badge-primary">' + escapeHtml(m.category) + '</span></td>' +
          '<td>' + escapeHtml(m.uploadedBy || '-') + '</td>' +
          '<td>' + (m.sizeKb ? m.sizeKb + ' KB' : '-') + '</td>' +
          '<td style="white-space:nowrap;">' + downloadBtn + deleteBtn + '</td></tr>';
      }).join("");
    }).catch(function (err) {
      console.log("Could not load study materials:", err.message);
    });
  }
}

window.deleteStudyMaterial = function (id, title, btn) {
  showConfirmModal({
    title: "Delete Study Material?",
    message: "Are you sure you want to delete '" + title + "' from the campus repository? This document will no longer be accessible for download by students.",
    confirmText: "Delete Material",
    danger: true,
    onConfirm: function (done) {
      api("/api/materials/" + encodeURIComponent(id), { method: "DELETE" })
        .then(function () {
          done();
          var row = btn ? btn.closest("tr") : null;
          if (row) {
            removeRowAnimated(row, function () {
              var targetBody = document.getElementById("materialsTableBody");
              if (targetBody && !targetBody.querySelectorAll(".filterable-item").length) {
                var role = getActiveRole();
                initMaterials(role);
              }
            });
          }
          showToast("Material Removed", "'" + title + "' was removed from repository.", "info");
        })
        .catch(function (err) {
          done();
          showToast("Delete Failed", err.message || "Could not delete study material.", "error");
        });
    }
  });
};

// ---- User Directory (Admin) --------------------------------------------------------
var _assignmentRowCounter = 0;

window.toggleMemberTypeFields = function () {
  var type = document.getElementById("newMemberType") ? document.getElementById("newMemberType").value : "Student";
  var studentFields = document.getElementById("studentSpecificFields");
  var facultyFields = document.getElementById("facultySpecificFields");
  if (type === "Faculty Member") {
    if (studentFields) studentFields.style.display = "none";
    if (facultyFields) facultyFields.style.display = "block";
    var cont = document.getElementById("facultyAssignmentsContainer");
    if (cont && cont.children.length === 0) {
      window.addFacultyAssignmentRow({ subject: "DBMS", year: "3rd Year", semester: 5, divisions: ["A", "B"] });
    }
  } else {
    if (studentFields) studentFields.style.display = "block";
    if (facultyFields) facultyFields.style.display = "none";
  }
};

window.syncStudentYearSem = function () {
  var yearEl = document.getElementById("newStudentYear");
  var semEl = document.getElementById("newStudentSem");
  if (!yearEl || !semEl) return;
  var year = yearEl.value;
  var map = { "1st Year": 1, "2nd Year": 3, "3rd Year": 5, "4th Year": 7 };
  if (map[year] !== undefined) {
    semEl.value = String(map[year]);
  }
};

window.updateDepartmentCourses = function () {};

window.addFacultyAssignmentRow = function (initial) {
  var cont = document.getElementById("facultyAssignmentsContainer");
  if (!cont) return;
  _assignmentRowCounter++;
  var rowId = "fac_assign_row_" + _assignmentRowCounter;
  var data = initial || { subject: "", year: "3rd Year", semester: 5, divisions: ["A"] };

  var div = document.createElement("div");
  div.id = rowId;
  div.className = "faculty-assignment-row";
  div.style.cssText = "background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px;margin-bottom:8px;";

  div.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
      '<strong style="font-size:12px;color:var(--text-main);">Teaching Assignment #' + _assignmentRowCounter + '</strong>' +
      '<button type="button" class="btn btn-danger btn-sm" onclick="window.removeFacultyAssignmentRow(\'' + rowId + '\')" style="padding:2px 6px;font-size:11px;">✕ Remove</button>' +
    '</div>' +
    '<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:8px;margin-bottom:6px;">' +
      '<div>' +
        '<label style="font-size:11px;display:block;margin-bottom:2px;">Subject / Course Title *</label>' +
        '<input type="text" class="form-input assign-subject" value="' + escapeHtml(data.subject || '') + '" placeholder="e.g. DBMS, Computer Networks" style="font-size:12px;padding:6px;" required>' +
      '</div>' +
      '<div>' +
        '<label style="font-size:11px;display:block;margin-bottom:2px;">Teaching Year *</label>' +
        '<select class="form-select assign-year" style="font-size:12px;padding:6px;">' +
          '<option value="1st Year"' + (data.year === "1st Year" ? " selected" : "") + '>1st Year</option>' +
          '<option value="2nd Year"' + (data.year === "2nd Year" ? " selected" : "") + '>2nd Year</option>' +
          '<option value="3rd Year"' + (data.year === "3rd Year" ? " selected" : "") + '>3rd Year</option>' +
          '<option value="4th Year"' + (data.year === "4th Year" ? " selected" : "") + '>4th Year</option>' +
        '</select>' +
      '</div>' +
      '<div>' +
        '<label style="font-size:11px;display:block;margin-bottom:2px;">Semester *</label>' +
        '<select class="form-select assign-sem" style="font-size:12px;padding:6px;">' +
          [1,2,3,4,5,6,7,8].map(function (s) {
            return '<option value="' + s + '"' + (Number(data.semester) === s ? ' selected' : '') + '>Sem ' + s + '</option>';
          }).join('') +
        '</select>' +
      '</div>' +
    '</div>' +
    '<div>' +
      '<label style="font-size:11px;display:block;margin-bottom:2px;">Divisions / Sections Taught (e.g. A, B)</label>' +
      '<div style="display:flex;gap:12px;align-items:center;font-size:12px;padding:4px 0;">' +
        ['A', 'B', 'C', 'D'].map(function (d) {
          var checked = (data.divisions && data.divisions.indexOf(d) !== -1) ? " checked" : "";
          return '<label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-weight:normal;">' +
            '<input type="checkbox" class="assign-div-cb" value="' + d + '"' + checked + '> Div ' + d +
          '</label>';
        }).join('') +
      '</div>' +
    '</div>';

  cont.appendChild(div);
};

window.removeFacultyAssignmentRow = function (rowId) {
  var el = document.getElementById(rowId);
  if (el) el.remove();
};

function resetUserForm() {
  var nameInp = document.getElementById("newMemberName");
  var emailInp = document.getElementById("newMemberEmail");
  var phoneInp = document.getElementById("newMemberPhone");
  var prnInp = document.getElementById("newStudentID");
  var facIdInp = document.getElementById("newFacultyID");
  if (nameInp) nameInp.value = "";
  if (emailInp) emailInp.value = "";
  if (phoneInp) phoneInp.value = "";
  if (prnInp) prnInp.value = "";
  if (facIdInp) facIdInp.value = "";
  var cont = document.getElementById("facultyAssignmentsContainer");
  if (cont) cont.innerHTML = "";
}

function initUsers(role) {
  var usersTable = document.getElementById("usersDirectoryTable");
  var usersBody = document.getElementById("usersTableBody");
  var addBtn = document.getElementById("addUserBtn");
  var modal = document.getElementById("addUserModal");

  // Page guard: only run on User Directory page
  if (!usersTable && !usersBody && !addBtn && !modal) return;

  if (role !== "admin") {
    if (addBtn) addBtn.remove();
    if (modal) modal.remove();
    return;
  }

  // Setup initial toggle state
  window.toggleMemberTypeFields();

  // Dynamically load departments from backend database
  api("/api/departments").then(function (res) {
    var depts = res.data || [];
    var deptSelect = document.getElementById("newMemberDept");
    if (deptSelect && depts.length) {
      var currentVal = deptSelect.value;
      deptSelect.innerHTML = depts.map(function (d) {
        return '<option value="' + escapeHtml(d.name) + '">' + escapeHtml(d.name) + '</option>';
      }).join('');
      if (currentVal && Array.from(deptSelect.options).some(function (opt) { return opt.value === currentVal; })) {
        deptSelect.value = currentVal;
      }
    }
  }).catch(function () {});

  var typeSelect = document.getElementById("newMemberType");
  if (typeSelect) {
    typeSelect.addEventListener("change", window.toggleMemberTypeFields);
  }

  var enrollBtn = document.getElementById("submitEnrollMemberBtn") || (modal ? modal.querySelector(".modal-footer .btn-primary") : null);
  if (enrollBtn) {
    enrollBtn.setAttribute("onclick", "");
    enrollBtn.addEventListener("click", function () {
      var modalBody = modal.querySelector(".modal-body");
      clearInlineErrors(modalBody);

      var type = document.getElementById("newMemberType") ? document.getElementById("newMemberType").value : "Student";
      var name = document.getElementById("newMemberName") ? document.getElementById("newMemberName").value.trim() : "";
      var dept = document.getElementById("newMemberDept") ? document.getElementById("newMemberDept").value : "";
      var email = document.getElementById("newMemberEmail") ? document.getElementById("newMemberEmail").value.trim() : "";
      var phone = document.getElementById("newMemberPhone") ? document.getElementById("newMemberPhone").value.trim() : "";

      if (!name || !email || !phone) {
        showInlineError(modalBody, "Please provide full name, college email and phone number.");
        return;
      }

      var isStudent = type === "Student";
      setButtonLoading(enrollBtn, isStudent ? "Creating Student..." : "Enrolling Faculty...");

      if (isStudent) {
        var year = document.getElementById("newStudentYear") ? document.getElementById("newStudentYear").value : "3rd Year";
        var sem = document.getElementById("newStudentSem") ? document.getElementById("newStudentSem").value : "5";
        var div = document.getElementById("newStudentDivision") ? document.getElementById("newStudentDivision").value : "A";
        var prn = document.getElementById("newStudentID") ? document.getElementById("newStudentID").value.trim() : "";

        api("/api/students", {
          method: "POST",
          body: {
            name: name,
            email: email,
            phone: phone,
            department: dept,
            year: year,
            semester: sem,
            division: div,
            prn: prn
          }
        }).then(function (res) {
          closeModal("addUserModal");
          resetUserForm();

          var s = res.data || { id: prn || email, prn: prn || "STU-NEW", name: name, email: email, dept: dept, year: year, semester: sem, division: div, status: "Active" };
          var classBadge = '<span class="badge badge-secondary">' + escapeHtml(s.year || year) + ' • Sem ' + (s.semester || sem) + ' • Div ' + escapeHtml(s.division || div) + '</span>';

          var tr = document.createElement("tr");
          tr.className = "filterable-item row-highlight-new";
          tr.setAttribute("data-category", "student");
          tr.id = "member-row-" + (s.id || s.prn);
          tr.innerHTML =
            '<td><strong class="col-member-id">' + escapeHtml(s.prn || s.id) + '</strong></td>' +
            '<td><span class="col-member-name">' + escapeHtml(s.name) + '</span><div class="col-member-email" style="font-size:12px;color:var(--text-muted);">' + escapeHtml(s.email) + '</div></td>' +
            '<td><span class="badge badge-primary">Student</span></td>' +
            '<td class="col-member-dept">' + escapeHtml(s.dept || dept) + '</td>' +
            '<td class="col-member-class">' + classBadge + '</td>' +
            '<td><span class="badge badge-success">' + escapeHtml(s.status || 'Active') + '</span></td>' +
            '<td style="white-space:nowrap;">' +
              '<button class="btn btn-secondary btn-sm" onclick="viewDirectoryMember(\'student\', \'' + encodeURIComponent(s.id || s.prn) + '\')">View</button> ' +
              '<button class="btn btn-secondary btn-sm" onclick="editDirectoryMember(\'student\', \'' + encodeURIComponent(s.id || s.prn) + '\')">Edit</button> ' +
              '<button class="btn btn-danger btn-sm" onclick="deleteDirectoryMember(\'student\', \'' + encodeURIComponent(s.id || s.prn) + '\', \'' + escapeHtml(s.name).replace(/'/g, "\\'") + '\', this)">Delete</button>' +
            '</td>';

          var tbody = document.getElementById("usersTableBody");
          if (tbody) {
            var emptyRow = tbody.querySelector(".empty-state-row");
            if (emptyRow) emptyRow.remove();
            tbody.prepend(tr);
          }

          var counter = document.getElementById("statTotalStudents");
          if (counter) {
            var curr = parseInt(counter.textContent.replace(/,/g, ""), 10) || 0;
            counter.textContent = (curr + 1).toLocaleString();
          }

          showSuccessModal({
            title: "Student Created Successfully",
            subtitle: "Student account is active with automatic academic cohort mapping.",
            items: [
              { label: "Student Name", value: s.name },
              { label: "Academic Cohort", value: (s.dept || dept) + " • " + (s.year || year) + " • Sem " + (s.semester || sem) + " • Div " + (s.division || div) },
              { label: "Login ID", value: s.email, copyable: true },
              { label: "Initial Password", value: phone, copyable: true }
            ],
            actions: [
              {
                text: "View Student",
                className: "btn-primary",
                onClick: function () {
                  tr.scrollIntoView({ behavior: "smooth", block: "center" });
                  highlightRow(tr, "new");
                }
              },
              { text: "Close", className: "btn-secondary" }
            ]
          });

          showToast("Student Enrolled", s.name + " has been added to directory.", "success");
        }).catch(function (e) {
          showInlineError(modalBody, e.message || "Could not enroll student.");
          showToast("Creation Failed", e.message || "Could not enroll student.", "error");
        }).finally(function () {
          resetButton(enrollBtn, "Enroll Member");
        });

      } else {
        var designation = document.getElementById("newFacultyDesignation") ? document.getElementById("newFacultyDesignation").value : "Assistant Professor";
        var facultyId = document.getElementById("newFacultyID") ? document.getElementById("newFacultyID").value.trim() : "";

        var rows = document.querySelectorAll("#facultyAssignmentsContainer .faculty-assignment-row");
        var assignments = [];
        rows.forEach(function (r) {
          var subject = r.querySelector(".assign-subject").value.trim();
          var y = r.querySelector(".assign-year").value;
          var s = r.querySelector(".assign-sem").value;
          var divs = [];
          r.querySelectorAll(".assign-div-cb:checked").forEach(function (cb) {
            divs.push(cb.value);
          });
          if (subject) {
            assignments.push({
              subject: subject,
              year: y,
              semester: s,
              divisions: divs.length ? divs : ["A"]
            });
          }
        });

        api("/api/faculty", {
          method: "POST",
          body: {
            name: name,
            email: email,
            phone: phone,
            department: dept,
            designation: designation,
            facultyId: facultyId,
            assignments: assignments
          }
        }).then(function (res) {
          closeModal("addUserModal");
          resetUserForm();

          var f = res.data || { id: facultyId || email, name: name, email: email, dept: dept, designation: designation, status: "Active" };
          var assignSummary = f.assignedSubjects && f.assignedSubjects.length ? ('<small style="display:block;color:var(--text-muted);margin-top:2px;">' + escapeHtml(f.assignedSubjects.join(', ')) + ' (Div: ' + escapeHtml((f.assignedDivisions || []).join(', ') || 'All') + ')</small>') : '';
          var classBadge = '<span class="badge badge-secondary">' + escapeHtml(f.designation || designation) + '</span>' + assignSummary;

          var tr = document.createElement("tr");
          tr.className = "filterable-item row-highlight-new";
          tr.setAttribute("data-category", "faculty");
          tr.id = "member-row-" + f.id;
          tr.innerHTML =
            '<td><strong class="col-member-id">' + escapeHtml(f.id) + '</strong></td>' +
            '<td><span class="col-member-name">' + escapeHtml(f.name) + '</span><div class="col-member-email" style="font-size:12px;color:var(--text-muted);">' + escapeHtml(f.email) + '</div></td>' +
            '<td><span class="badge badge-success">Faculty</span></td>' +
            '<td class="col-member-dept">' + escapeHtml(f.dept || dept) + '</td>' +
            '<td class="col-member-class">' + classBadge + '</td>' +
            '<td><span class="badge badge-success">' + escapeHtml(f.status || 'Active') + '</span></td>' +
            '<td style="white-space:nowrap;">' +
              '<button class="btn btn-secondary btn-sm" onclick="viewDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\')">View</button> ' +
              '<button class="btn btn-secondary btn-sm" onclick="editDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\')">Edit</button> ' +
              '<button class="btn btn-danger btn-sm" onclick="deleteDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\', \'' + escapeHtml(f.name).replace(/'/g, "\\'") + '\', this)">Delete</button>' +
            '</td>';

          var tbody = document.getElementById("usersTableBody");
          if (tbody) {
            var emptyRow = tbody.querySelector(".empty-state-row");
            if (emptyRow) emptyRow.remove();
            tbody.prepend(tr);
          }

          var counter = document.getElementById("statTotalFaculty");
          if (counter) {
            var curr = parseInt(counter.textContent.replace(/,/g, ""), 10) || 0;
            counter.textContent = (curr + 1).toLocaleString();
          }

          showSuccessModal({
            title: "Faculty Member Enrolled Successfully",
            subtitle: "Faculty profile generated with assigned teaching portfolio.",
            items: [
              { label: "Faculty Name", value: f.name },
              { label: "Department & Role", value: (f.dept || dept) + " • " + (f.designation || designation) },
              { label: "Login ID", value: f.email, copyable: true },
              { label: "Initial Password", value: phone, copyable: true },
              { label: "Assigned Subjects", value: (res.data && res.data.assignedSubjects) ? res.data.assignedSubjects.join(", ") : "-" }
            ],
            actions: [
              {
                text: "View Faculty",
                className: "btn-primary",
                onClick: function () {
                  tr.scrollIntoView({ behavior: "smooth", block: "center" });
                  highlightRow(tr, "new");
                }
              },
              { text: "Close", className: "btn-secondary" }
            ]
          });

          showToast("Faculty Enrolled", f.name + " has been added to directory.", "success");
        }).catch(function (e) {
          showInlineError(modalBody, e.message || "Could not enroll faculty member.");
          showToast("Enrollment Failed", e.message || "Could not enroll faculty member.", "error");
        }).finally(function () {
          resetButton(enrollBtn, "Enroll Member");
        });
      }
    });
  }

  fetchUsersFromAPI(role);
}

function fetchUsersFromAPI(role) {
  var tbody = document.getElementById("usersTableBody");
  if (!tbody) return;

  Promise.all([
    api("/api/students"),
    api("/api/faculty")
  ]).then(function (results) {
    var students = results[0].data || [];
    var faculty = results[1].data || [];

    var statStudents = document.getElementById("statTotalStudents");
    var statFaculty = document.getElementById("statTotalFaculty");
    if (statStudents) statStudents.textContent = students.length.toLocaleString();
    if (statFaculty) statFaculty.textContent = faculty.length.toLocaleString();

    var html = "";

    students.forEach(function (s) {
      var classBadge = '<span class="badge badge-secondary">' + escapeHtml(s.year || '-') + ' • Sem ' + (s.semester || '-') + ' • Div ' + escapeHtml(s.division || 'A') + '</span>';
      html += '<tr class="filterable-item" data-category="student" id="member-row-' + escapeHtml(s.id) + '">' +
        '<td><strong class="col-member-id">' + escapeHtml(s.prn || s.id) + '</strong></td>' +
        '<td><span class="col-member-name">' + escapeHtml(s.name) + '</span><div class="col-member-email" style="font-size:12px;color:var(--text-muted);">' + escapeHtml(s.email) + '</div></td>' +
        '<td><span class="badge badge-primary">Student</span></td>' +
        '<td class="col-member-dept">' + escapeHtml(s.dept || s.deptCode || '-') + '</td>' +
        '<td class="col-member-class">' + classBadge + '</td>' +
        '<td><span class="badge badge-success">' + escapeHtml(s.status || 'Active') + '</span></td>' +
        '<td style="white-space:nowrap;">' +
          '<button class="btn btn-secondary btn-sm" onclick="viewDirectoryMember(\'student\', \'' + encodeURIComponent(s.id) + '\')">View</button> ' +
          '<button class="btn btn-secondary btn-sm" onclick="editDirectoryMember(\'student\', \'' + encodeURIComponent(s.id) + '\')">Edit</button> ' +
          '<button class="btn btn-danger btn-sm" onclick="deleteDirectoryMember(\'student\', \'' + encodeURIComponent(s.id) + '\', \'' + escapeHtml(s.name).replace(/'/g, "\\'") + '\', this)">Delete</button>' +
        '</td>' +
        '</tr>';
    });

    faculty.forEach(function (f) {
      var assignSummary = f.assignedSubjects && f.assignedSubjects.length ? ('<small style="display:block;color:var(--text-muted);margin-top:2px;">' + escapeHtml(f.assignedSubjects.join(', ')) + ' (Div: ' + escapeHtml((f.assignedDivisions || []).join(', ') || 'All') + ')</small>') : '';
      var classBadge = '<span class="badge badge-secondary">' + escapeHtml(f.designation || 'Faculty') + '</span>' + assignSummary;
      html += '<tr class="filterable-item" data-category="faculty" id="member-row-' + escapeHtml(f.id) + '">' +
        '<td><strong class="col-member-id">' + escapeHtml(f.id) + '</strong></td>' +
        '<td><span class="col-member-name">' + escapeHtml(f.name) + '</span><div class="col-member-email" style="font-size:12px;color:var(--text-muted);">' + escapeHtml(f.email) + '</div></td>' +
        '<td><span class="badge badge-success">Faculty</span></td>' +
        '<td class="col-member-dept">' + escapeHtml(f.dept || '-') + '</td>' +
        '<td class="col-member-class">' + classBadge + '</td>' +
        '<td><span class="badge badge-success">' + escapeHtml(f.status || 'Active') + '</span></td>' +
        '<td style="white-space:nowrap;">' +
          '<button class="btn btn-secondary btn-sm" onclick="viewDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\')">View</button> ' +
          '<button class="btn btn-secondary btn-sm" onclick="editDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\')">Edit</button> ' +
          '<button class="btn btn-danger btn-sm" onclick="deleteDirectoryMember(\'faculty\', \'' + encodeURIComponent(f.id) + '\', \'' + escapeHtml(f.name).replace(/'/g, "\\'") + '\', this)">Delete</button>' +
        '</td>' +
        '</tr>';
    });

    if (students.length === 0 && faculty.length === 0) {
      renderEmptyState(tbody, {
        icon: "👥",
        title: "No Directory Records Found",
        message: "There are currently no students or faculty matching your filter criteria.",
        actionText: role === "admin" ? "Add New Member" : null,
        onAction: function () { openModal("addUserModal"); },
        colSpan: 7
      });
    } else {
      tbody.innerHTML = html;
    }
  }).catch(function (err) {
    console.log("Could not load directory records:", err.message);
  });
}

// ---- Directory Member Deletion ----------------------------------------------------
window.deleteDirectoryMember = function (type, code, name, btn) {
  var isStudent = type === "student";
  var memberTitle = isStudent ? "Student" : "Faculty Member";

  showConfirmModal({
    title: "Delete " + memberTitle + "?",
    message: "Are you sure you want to delete " + name + "? This action will permanently remove their account, credentials, and associated academic access.",
    confirmText: "Delete " + (isStudent ? "Student" : "Faculty"),
    danger: true,
    onConfirm: function (done) {
      var endpoint = isStudent ? "/api/students/" : "/api/faculty/";
      api(endpoint + encodeURIComponent(code), { method: "DELETE" })
        .then(function () {
          done();
          var row = btn ? btn.closest("tr") : document.getElementById("member-row-" + code);
          if (row) {
            removeRowAnimated(row, function () {
              var tbody = document.getElementById("usersTableBody");
              if (tbody && !tbody.querySelectorAll(".filterable-item").length) {
                var role = getActiveRole();
                fetchUsersFromAPI(role);
              }
            });
          }
          var counter = document.getElementById(isStudent ? "statTotalStudents" : "statTotalFaculty");
          if (counter) {
            var curr = parseInt(counter.textContent.replace(/,/g, ""), 10) || 0;
            if (curr > 0) counter.textContent = (curr - 1).toLocaleString();
          }
          showToast("Member Deleted", name + " has been removed from the directory.", "success");
        })
        .catch(function (err) {
          done();
          showToast("Delete Failed", err.message || ("Could not delete " + memberTitle.toLowerCase() + "."), "error");
        });
    }
  });
};

// ---- Directory detail viewer -------------------------------------------------------
window.viewDirectoryMember = function (type, code) {
  var endpoint = type === "faculty" ? "/api/faculty/" : "/api/students/";
  api(endpoint + encodeURIComponent(code)).then(function (res) {
    var d = res.data || {};
    var html = "";

    if (type === "student") {
      var details = [
        ["Full Name", d.name],
        ["Email / Login ID", d.email],
        ["Phone Number", d.phone || "Not provided"],
        ["Department", d.dept || "-"],
        ["Academic Year", d.year || "-"],
        ["Semester", "Semester " + (d.semester || "-")],
        ["Division / Section", "Division " + (d.division || "A")],
        ["Student ID / PRN", d.prn || d.id || "-"],
        ["Status", d.status || "Active"]
      ];
      html = '<div style="margin-bottom:12px;padding:10px;background:var(--bg-subtle);border-radius:var(--radius-sm);border:1px solid var(--border);">' +
        '<div style="font-size:12px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:4px;">🎓 Student Academic Profile</div>' +
        '<div style="font-size:13px;color:var(--text-muted);">' + escapeHtml(d.name) + ' (' + escapeHtml(d.prn || d.id) + ')</div>' +
      '</div>';
      html += details.map(function (x) {
        return '<div style="display:flex;justify-content:space-between;gap:20px;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;">' +
          '<strong style="color:var(--text-main);">' + escapeHtml(x[0]) + '</strong>' +
          '<span style="color:var(--text-muted);">' + escapeHtml(x[1]) + '</span>' +
        '</div>';
      }).join("");

    } else {
      var facDetails = [
        ["Full Name", d.name],
        ["Email / Login ID", d.email],
        ["Phone Number", d.phone || "Not provided"],
        ["Department", d.dept || "-"],
        ["Designation", d.designation || "Faculty"],
        ["Faculty ID", d.id || d.facultyCode || "-"],
        ["Assigned Subjects", (d.assignedSubjects && d.assignedSubjects.length) ? d.assignedSubjects.join(", ") : "None"],
        ["Assigned Years", (d.assignedYears && d.assignedYears.length) ? d.assignedYears.join(", ") : "None"],
        ["Assigned Semesters", (d.assignedSemesters && d.assignedSemesters.length) ? d.assignedSemesters.map(function(s){return 'Sem ' + s;}).join(", ") : "None"],
        ["Assigned Divisions", (d.assignedDivisions && d.assignedDivisions.length) ? d.assignedDivisions.map(function(dv){return 'Div ' + dv;}).join(", ") : "None"],
        ["Status", d.status || "Active"]
      ];

      html = '<div style="margin-bottom:12px;padding:10px;background:var(--bg-subtle);border-radius:var(--radius-sm);border:1px solid var(--border);">' +
        '<div style="font-size:12px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:4px;">👨‍🏫 Faculty Member Profile</div>' +
        '<div style="font-size:13px;color:var(--text-muted);">' + escapeHtml(d.name) + ' (' + escapeHtml(d.designation || 'Faculty') + ')</div>' +
      '</div>';

      html += facDetails.map(function (x) {
        return '<div style="display:flex;justify-content:space-between;gap:20px;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;">' +
          '<strong style="color:var(--text-main);">' + escapeHtml(x[0]) + '</strong>' +
          '<span style="color:var(--text-muted);text-align:right;">' + escapeHtml(x[1]) + '</span>' +
        '</div>';
      }).join("");

      if (d.assignments && d.assignments.length) {
        html += '<div style="margin-top:16px;">' +
          '<div style="font-size:12px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:8px;">📚 Detailed Teaching Assignments</div>' +
          '<table style="width:100%;font-size:12px;border-collapse:collapse;">' +
            '<thead><tr style="border-bottom:1px solid var(--border);text-align:left;color:var(--text-muted);"><th style="padding:4px 6px;">Subject</th><th style="padding:4px 6px;">Year</th><th style="padding:4px 6px;">Sem</th><th style="padding:4px 6px;">Div</th></tr></thead>' +
            '<tbody>' +
            d.assignments.map(function (a) {
              return '<tr style="border-bottom:1px solid var(--border);"><td style="padding:6px;"><strong>' + escapeHtml(a.courseTitle || a.courseCode || '-') + '</strong></td><td style="padding:6px;">' + escapeHtml(a.year || '-') + '</td><td style="padding:6px;">Sem ' + a.semester + '</td><td style="padding:6px;"><span class="badge badge-info">Div ' + escapeHtml(a.division || '-') + '</span></td></tr>';
            }).join("") +
            '</tbody>' +
          '</table>' +
        '</div>';
      }
    }

    var existing = document.getElementById("directoryDetailModal");
    if (!existing) {
      existing = document.createElement("div");
      existing.id = "directoryDetailModal";
      existing.className = "modal-overlay";
      existing.innerHTML =
        '<div class="modal-box" style="max-width:540px;max-height:90vh;overflow-y:auto;">' +
          '<div class="modal-header">' +
            '<h3>Member Complete Profile</h3>' +
            '<span class="modal-close" id="directoryDetailClose">&times;</span>' +
          '</div>' +
          '<div class="modal-body" id="directoryDetailBody"></div>' +
          '<div class="modal-footer">' +
            '<button class="btn btn-secondary btn-sm" id="directoryDetailCloseBtn">Close</button>' +
          '</div>' +
        '</div>';
      document.body.appendChild(existing);
      document.getElementById("directoryDetailClose").onclick = function () { existing.classList.remove("active"); };
      document.getElementById("directoryDetailCloseBtn").onclick = function () { existing.classList.remove("active"); };
    }
    document.getElementById("directoryDetailBody").innerHTML = html;
    existing.classList.add("active");
  }).catch(function (e) {
    showToast("Load Failed", e.message || "Could not load member details.", "error");
  });
};

// ---- Directory Member Editing ------------------------------------------------------
window.editDirectoryMember = function (type, code) {
  var endpoint = type === "faculty" ? "/api/faculty/" : "/api/students/";
  Promise.all([
    api(endpoint + encodeURIComponent(code)),
    api("/api/departments").catch(function() { return { data: [] }; })
  ]).then(function (results) {
    var d = (results[0] && results[0].data) || {};
    var depts = (results[1] && results[1].data) || [];
    var modal = document.getElementById("editUserModal");
    var body = document.getElementById("editModalBody");
    var heading = document.getElementById("editModalHeading");
    var saveBtn = document.getElementById("saveEditMemberBtn");
    if (!modal || !body) return;

    clearInlineErrors(body);

    if (heading) heading.textContent = "Edit " + (type === "faculty" ? "Faculty" : "Student") + " Details";

    var currentDeptName = d.dept || d.department || "";
    var deptOptions = depts.map(function(dept) {
      var sel = (dept.name === currentDeptName || dept.code === currentDeptName) ? " selected" : "";
      return '<option value="' + escapeHtml(dept.name) + '"' + sel + '>' + escapeHtml(dept.name) + '</option>';
    }).join("");

    if (type === "student") {
      body.innerHTML =
        '<div class="form-group"><label>Full Name *</label><input type="text" class="form-input" id="editMemberName" value="' + escapeHtml(d.name) + '" required></div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">' +
          '<div class="form-group"><label>Phone Number *</label><input type="tel" class="form-input" id="editMemberPhone" value="' + escapeHtml(d.phone || '') + '" required></div>' +
          '<div class="form-group"><label>Department</label><select class="form-select" id="editMemberDept">' + deptOptions + '</select></div>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">' +
          '<div class="form-group"><label>Academic Year</label><select class="form-select" id="editMemberYear">' +
            ['1st Year', '2nd Year', '3rd Year', '4th Year'].map(function(y){return '<option value="' + y + '"' + (d.year === y ? ' selected' : '') + '>' + y + '</option>';}).join('') +
          '</select></div>' +
          '<div class="form-group"><label>Semester</label><select class="form-select" id="editMemberSem">' +
            [1,2,3,4,5,6,7,8].map(function(s){return '<option value="' + s + '"' + (Number(d.semester) === s ? ' selected' : '') + '>Sem ' + s + '</option>';}).join('') +
          '</select></div>' +
          '<div class="form-group"><label>Division</label><select class="form-select" id="editMemberDiv">' +
            ['A', 'B', 'C', 'D'].map(function(dv){return '<option value="' + dv + '"' + (d.division === dv ? ' selected' : '') + '>Div ' + dv + '</option>';}).join('') +
          '</select></div>' +
        '</div>';

      saveBtn.onclick = function () {
        var payload = {
          name: document.getElementById("editMemberName").value.trim(),
          phone: document.getElementById("editMemberPhone").value.trim(),
          year: document.getElementById("editMemberYear").value,
          semester: document.getElementById("editMemberSem").value,
          division: document.getElementById("editMemberDiv").value
        };
        var deptEl = document.getElementById("editMemberDept");
        if (deptEl && deptEl.value) {
          payload.department = deptEl.value;
        }

        if (!payload.name || !payload.phone) {
          showInlineError(body, "Please fill in all required fields.");
          return;
        }

        setButtonLoading(saveBtn, "Saving Changes...");

        api(endpoint + encodeURIComponent(code), { method: "PUT", body: payload }).then(function (updateRes) {
          closeModal("editUserModal");

          var row = document.getElementById("member-row-" + code);
          if (row) {
            var nameEl = row.querySelector(".col-member-name");
            if (nameEl) nameEl.textContent = payload.name;
            if (payload.department) {
              var deptCol = row.querySelector(".col-member-dept");
              if (deptCol) deptCol.textContent = payload.department;
            }
            var classEl = row.querySelector(".col-member-class");
            if (classEl) {
              classEl.innerHTML = '<span class="badge badge-secondary">' + escapeHtml(payload.year) + ' • Sem ' + payload.semester + ' • Div ' + escapeHtml(payload.division) + '</span>';
            }
            highlightRow(row, "update");
          }

          showToast("Profile Updated", "Student details for " + payload.name + " updated successfully.", "success");
        }).catch(function (e) {
          showInlineError(body, e.message || "Could not update student.");
          showToast("Update Failed", e.message || "Could not update student.", "error");
        }).finally(function () {
          resetButton(saveBtn, "Save Changes");
        });
      };

    } else {
      body.innerHTML =
        '<div class="form-group"><label>Full Name *</label><input type="text" class="form-input" id="editMemberName" value="' + escapeHtml(d.name) + '" required></div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">' +
          '<div class="form-group"><label>Phone Number *</label><input type="tel" class="form-input" id="editMemberPhone" value="' + escapeHtml(d.phone || '') + '" required></div>' +
          '<div class="form-group"><label>Designation *</label><select class="form-select" id="editMemberDesignation">' +
            ['Assistant Professor', 'Associate Professor', 'Professor', 'Head of Department'].map(function(des){return '<option value="' + des + '"' + (d.designation === des ? ' selected' : '') + '>' + des + '</option>';}).join('') +
          '</select></div>' +
        '</div>' +
        '<div class="form-group"><label>Department</label><select class="form-select" id="editMemberDept">' + deptOptions + '</select></div>';

      saveBtn.onclick = function () {
        var payload = {
          name: document.getElementById("editMemberName").value.trim(),
          phone: document.getElementById("editMemberPhone").value.trim(),
          designation: document.getElementById("editMemberDesignation").value
        };
        var deptEl = document.getElementById("editMemberDept");
        if (deptEl && deptEl.value) {
          payload.department = deptEl.value;
        }

        if (!payload.name || !payload.phone) {
          showInlineError(body, "Please fill in all required fields.");
          return;
        }

        setButtonLoading(saveBtn, "Saving Changes...");

        api(endpoint + encodeURIComponent(code), { method: "PUT", body: payload }).then(function (updateRes) {
          closeModal("editUserModal");

          var row = document.getElementById("member-row-" + code);
          if (row) {
            var nameEl = row.querySelector(".col-member-name");
            if (nameEl) nameEl.textContent = payload.name;
            if (payload.department) {
              var deptCol = row.querySelector(".col-member-dept");
              if (deptCol) deptCol.textContent = payload.department;
            }
            var classEl = row.querySelector(".col-member-class");
            if (classEl) {
              classEl.innerHTML = '<span class="badge badge-secondary">' + escapeHtml(payload.designation) + '</span>';
            }
            highlightRow(row, "update");
          }

          showToast("Profile Updated", "Faculty details for " + payload.name + " updated successfully.", "success");
        }).catch(function (e) {
          showInlineError(body, e.message || "Could not update faculty member.");
          showToast("Update Failed", e.message || "Could not update faculty member.", "error");
        }).finally(function () {
          resetButton(saveBtn, "Save Changes");
        });
      };
    }

    modal.classList.add("active");
  }).catch(function (e) {
    showToast("Open Failed", e.message || "Could not open member editor.", "error");
  });
};

// ---- Campus Events Module ---------------------------------------------------------
function initEvents(role) {
  var grid = document.querySelector(".grid-3");
  var pageActions = document.querySelector(".page-actions");

  if (pageActions && (role === "admin" || role === "faculty")) {
    if (!document.getElementById("openNewEventBtn")) {
      var postEventBtn = document.createElement("button");
      postEventBtn.id = "openNewEventBtn";
      postEventBtn.className = "btn btn-primary btn-sm";
      postEventBtn.textContent = "+ Post New Event";
      postEventBtn.addEventListener("click", function () {
        openModal("newEventModal");
      });
      pageActions.appendChild(postEventBtn);
    }
  }

  // Create #newEventModal if missing
  var modal = document.getElementById("newEventModal");
  if (!modal && (role === "admin" || role === "faculty")) {
    modal = document.createElement("div");
    modal.id = "newEventModal";
    modal.className = "modal-overlay";
    modal.innerHTML =
      '<div class="modal-box">' +
        '<div class="modal-header">' +
          '<h3>Post Campus Event</h3>' +
          '<span class="modal-close" onclick="closeModal(\'newEventModal\')">&times;</span>' +
        '</div>' +
        '<div class="modal-body">' +
          '<div class="form-group"><label>Event Title *</label><input type="text" class="form-input" id="eventTitle" placeholder="e.g. AI & Robotics Symposium" required></div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">' +
            '<div class="form-group"><label>Category *</label><select class="form-select" id="eventCategory">' +
              '<option value="Workshop">Workshop</option>' +
              '<option value="Sports">Sports</option>' +
              '<option value="Cultural">Cultural</option>' +
              '<option value="Seminar">Seminar</option>' +
            '</select></div>' +
            '<div class="form-group"><label>Event Date *</label><input type="date" class="form-input" id="eventDate" required></div>' +
          '</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">' +
            '<div class="form-group"><label>Venue</label><input type="text" class="form-input" id="eventVenue" placeholder="e.g. Auditorium Hall B"></div>' +
            '<div class="form-group"><label>Time Schedule</label><input type="text" class="form-input" id="eventTime" placeholder="e.g. 10:00 AM - 02:00 PM"></div>' +
          '</div>' +
          '<div class="form-group"><label>Description</label><textarea class="form-input" id="eventDesc" rows="3" placeholder="Describe the event objectives, speaker details, and requirements..."></textarea></div>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button class="btn btn-secondary btn-sm" onclick="closeModal(\'newEventModal\')">Cancel</button>' +
          '<button class="btn btn-primary btn-sm" id="submitCreateEventBtn">Publish Event</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modal);

    var createBtn = document.getElementById("submitCreateEventBtn");
    createBtn.addEventListener("click", function () {
      var modalBody = modal.querySelector(".modal-body");
      clearInlineErrors(modalBody);

      var title = document.getElementById("eventTitle").value.trim();
      var category = document.getElementById("eventCategory").value;
      var dateVal = document.getElementById("eventDate").value;
      var venue = document.getElementById("eventVenue").value.trim();
      var timeStr = document.getElementById("eventTime").value.trim();
      var desc = document.getElementById("eventDesc").value.trim();

      if (!title || !dateVal) {
        showInlineError(modalBody, "Please provide an event title and scheduled date.");
        return;
      }

      setButtonLoading(createBtn, "Publishing Event...");

      api("/api/events", {
        method: "POST",
        body: {
          title: title,
          category: category,
          date: dateVal,
          location: venue ? (venue + (timeStr ? " • " + timeStr : "")) : (timeStr || "Campus Grounds"),
          description: desc
        }
      }).then(function (res) {
        closeModal("newEventModal");
        document.getElementById("eventTitle").value = "";
        document.getElementById("eventDate").value = "";
        document.getElementById("eventVenue").value = "";
        document.getElementById("eventTime").value = "";
        document.getElementById("eventDesc").value = "";

        loadEvents();
        showToast("Event Created", title + " added to campus calendar.", "success");
      }).catch(function (err) {
        showInlineError(modalBody, err.message || "Could not publish event.");
        showToast("Publish Failed", err.message || "Could not publish event.", "error");
      }).finally(function () {
        resetButton(createBtn, "Publish Event");
      });
    });
  }

  loadEvents();

  function loadEvents() {
    if (!grid) return;
    api("/api/events").then(function (res) {
      var events = res.data || [];
      if (!events.length) {
        renderEmptyState(grid, {
          icon: "🎉",
          title: "No Events Scheduled",
          message: "There are currently no upcoming events or workshops on the campus calendar.",
          actionText: (role === "admin" || role === "faculty") ? "Post Event" : null,
          onAction: function () { openModal("newEventModal"); }
        });
        return;
      }

      grid.innerHTML = events.map(function (ev) {
        var cat = (ev.category || "General").toLowerCase();
        var dateFormatted = ev.date || "Upcoming";
        var deleteBtn = (role === "admin" || role === "faculty")
          ? ' <button class="btn btn-danger btn-sm" style="padding: 2px 8px; font-size: 11.5px;" onclick="deleteCampusEvent(' + ev.id + ', \'' + escapeHtml(ev.title).replace(/'/g, "\\'") + '\', this)">🗑️ Cancel</button>'
          : '';

        var actionBtn = (role === "student")
          ? '<button class="btn btn-primary btn-sm full-width event-reg-btn" onclick="registerForEvent(this, \'' + escapeHtml(ev.title).replace(/'/g, "\\'") + '\')">Register Now</button>'
          : '<div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 4px 0;">Organized by Campus Activities</div>';

        return '<div class="card filterable-item" data-category="' + cat + '">' +
          '<div class="card-header-row">' +
            '<span class="badge badge-primary">' + escapeHtml(ev.category || "General") + '</span>' +
            '<div style="display:flex; align-items:center; gap:8px;">' +
              '<span class="badge badge-info">' + escapeHtml(dateFormatted) + '</span>' +
              deleteBtn +
            '</div>' +
          '</div>' +
          '<h3 style="font-size: 17px; margin-bottom: 6px;">' + escapeHtml(ev.title) + '</h3>' +
          '<p style="font-size: 13.5px; color: var(--text-muted); margin-bottom: 12px; line-height: 1.5;">' +
            escapeHtml(ev.description || "Campus interactive session.") +
          '</p>' +
          '<div style="font-size: 12.5px; color: var(--text-light); margin-bottom: 16px;">' +
            '<div>📍 <strong>Venue:</strong> ' + escapeHtml(ev.location || "Campus Center") + '</div>' +
          '</div>' +
          actionBtn +
        '</div>';
      }).join("");
    }).catch(function () {});
  }
}

window.registerForEvent = function (btn, eventTitle) {
  setButtonLoading(btn, "Registering...");
  setTimeout(function () {
    resetButton(btn, '<span class="badge-saved">✓ Registered</span>');
    showToast("Registration Confirmed", "Your seat for '" + eventTitle + "' has been reserved.", "success");
  }, 450);
};

window.deleteCampusEvent = function (id, title, btn) {
  showConfirmModal({
    title: "Cancel Event?",
    message: "Are you sure you want to cancel '" + title + "'? This will remove the event from the public calendar.",
    confirmText: "Cancel Event",
    danger: true,
    onConfirm: function (done) {
      api("/api/events/" + encodeURIComponent(id), { method: "DELETE" })
        .then(function () {
          done();
          var card = btn ? btn.closest(".card") : null;
          if (card) {
            removeRowAnimated(card, function () {
              var grid = document.querySelector(".grid-3");
              if (grid && !grid.querySelectorAll(".filterable-item").length) {
                var role = getActiveRole();
                initEvents(role);
              }
            });
          }
          showToast("Event Cancelled", "'" + title + "' has been removed.", "info");
        })
        .catch(function (err) {
          done();
          showToast("Cancel Failed", err.message || "Could not delete event.", "error");
        });
    }
  });
};

// ---- Modal helpers with RBAC checks -------------------------------------------------
function openModal(id) {
  var role = getActiveRole();
  if (id === "newNoticeModal" && role === "student") {
    showToast("Access Restricted", "Only Faculty and Administrators can publish notices.", "warning");
    return;
  }
  if (id === "uploadMaterialModal" && role === "student") {
    showToast("Access Restricted", "Only Faculty and Administrators can upload study materials.", "warning");
    return;
  }
  if (id === "addUserModal" && role !== "admin") {
    showToast("Access Restricted", "Only Administrators can add members to the user directory.", "warning");
    return;
  }
  if ((id === "addCourseModal" || id === "editCourseModal") && role !== "admin") {
    showToast("Access Restricted", "Only Administrators can manage course offerings.", "warning");
    return;
  }
  var el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function closeModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.remove("active");
}
