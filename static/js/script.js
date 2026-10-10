// ============================================================================
// Campus Connect frontend <-> Flask API integration.
// Visual design, layout and CSS classes are unchanged. This file now talks
// to the real backend instead of faking auth/data with localStorage.
// ============================================================================

var CURRENT_USER = null; // populated by bootstrap() from /api/auth/me

// ---- Low-level API helper with request deduplication ------------------------
var _inflightGetRequests = {};

function api(path, options) {
  options = options || {};
  var method = (options.method || "GET").toUpperCase();
  var isGet = method === "GET";

  if (isGet && _inflightGetRequests[path]) {
    return _inflightGetRequests[path];
  }

  options.credentials = "include";
  var token = sessionStorage.getItem("campus_session_token") || localStorage.getItem("campus_session_token");
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

  var reqPromise = fetch(targetUrl, options).then(function (res) {
    return res.json().catch(function () { return {}; }).then(function (data) {
      if (!res.ok) {
        var err = new Error(data.error || ("Request failed (" + res.status + ")"));
        err.status = res.status;
        err.data = data;
        throw err;
      }
      return data;
    });
  }).finally(function () {
    if (isGet) {
      delete _inflightGetRequests[path];
    }
  });

  if (isGet) {
    _inflightGetRequests[path] = reqPromise;
  }

  return reqPromise;
}

function debounce(fn, delay) {
  var timer = null;
  return function () {
    var context = this, args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () {
      fn.apply(context, args);
    }, delay || 300);
  };
}

function getActiveRole() {
  if (CURRENT_USER && CURRENT_USER.role) return CURRENT_USER.role.toLowerCase();
  var stored = sessionStorage.getItem("campus_user_role") || localStorage.getItem("campus_user_role");
  return stored ? stored.toLowerCase() : null;
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

  // Synchronize token between sessionStorage and localStorage for seamless multi-tab navigation
  var token = sessionStorage.getItem("campus_session_token") || localStorage.getItem("campus_session_token");
  if (token && !sessionStorage.getItem("campus_session_token")) {
    sessionStorage.setItem("campus_session_token", token);
  }

  api("/api/auth/me")
    .then(function (res) {
      CURRENT_USER = res.data;
      if (res.data && res.data.role) {
        sessionStorage.setItem("campus_user_role", res.data.role);
        localStorage.setItem("campus_user_role", res.data.role);
      }
      boot(currentPath);
    })
    .catch(function (err) {
      // Only redirect to login if authentication was explicitly rejected with HTTP 401
      if (err && err.status === 401) {
        sessionStorage.removeItem("campus_session_token");
        sessionStorage.removeItem("campus_user_role");
        localStorage.removeItem("campus_session_token");
        localStorage.removeItem("campus_user_role");
        window.location.href = "login.html";
        return;
      }
      // On network timeout or server glitch, do NOT logout the user
      console.warn("Auth verification check deferred:", err);
      var banner = document.createElement("div");
      banner.id = "connectionRetryBanner";
      banner.style.cssText = "position:fixed;top:12px;left:50%;transform:translateX(-50%);background:#e11d48;color:#fff;padding:8px 18px;border-radius:6px;z-index:99999;font-size:13px;font-weight:600;box-shadow:0 4px 12px rgba(0,0,0,0.2);display:flex;align-items:center;gap:10px;";
      banner.innerHTML = "<span>⚠️ Server connection delayed. Retrying...</span><button style='background:#fff;color:#111;border:none;padding:3px 10px;border-radius:4px;cursor:pointer;font-weight:700;' onclick='window.location.reload()'>🔄 Retry</button>";
      document.body.appendChild(banner);
    });
});

function boot(currentPath) {
  var user = CURRENT_USER;
  var role = (user && user.role) ? user.role.toLowerCase() : (getActiveRole() || "");

  // 1. Client-side RBAC gate (server also enforces this on every API call)
  if ((currentPath === "users.html" || currentPath === "users") && role !== "admin") {
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
    case "assignments.html":
      initAssignments(role);
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
    case "users":
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
      if (document.getElementById("studentAssignmentsCard") || document.getElementById("facultyAssignmentsCard")) initAssignments(role);
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
      { name: "My Attendance", href: "attendance.html", icon: "📅" },
      { name: "My Assignments & Submissions", href: "assignments.html", icon: "📋" },
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
      { name: "Attendance", href: "attendance.html", icon: "📅" },
      { name: "Assignment Management", href: "assignments.html", icon: "📋" },
      { name: "Assignment Evaluation", href: "assignments.html#evaluations", icon: "📝" },
      { name: "Enter Marks", href: "results.html", icon: "📊" },
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
    localStorage.removeItem("campus_session_token");
    localStorage.removeItem("campus_user_role");
    localStorage.removeItem("campus_role");
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
        localStorage.setItem("campus_session_token", res.sessionToken);
      }
      if (res.data && res.data.role) {
        sessionStorage.setItem("campus_user_role", res.data.role);
        localStorage.setItem("campus_user_role", res.data.role);
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
        '<a href="attendance.html" class="btn btn-secondary btn-sm">📅 My Attendance</a>' +
        '<a href="assignments.html" class="btn btn-secondary btn-sm">📋 My Assignments & Submissions</a>' +
        '<a href="results.html" class="btn btn-secondary btn-sm">📝 My Results</a>' +
        '<a href="materials.html" class="btn btn-secondary btn-sm">📁 Study Notes</a>' +
        '<a href="notices.html" class="btn btn-secondary btn-sm">📢 Notice Board</a>' +
        '<a href="events.html" class="btn btn-secondary btn-sm">🎉 Events</a>' +
        '<a href="settings.html" class="btn btn-secondary btn-sm">⚙️ Settings</a>';
    } else if (role === "faculty") {
      quickLinks.innerHTML =
        '<a href="courses.html" class="btn btn-secondary btn-sm">📚 My Classes</a>' +
        '<a href="attendance.html" class="btn btn-secondary btn-sm">📅 Attendance</a>' +
        '<a href="assignments.html" class="btn btn-secondary btn-sm">📋 Assignment Management</a>' +
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

  // Dynamically load top 3 recent notices from database for dashboard
  var noticesList = document.getElementById("dashboardRecentNotices");
  function loadDashboardNotices() {
    if (!noticesList) return;
    noticesList.innerHTML = '<div style="text-align:center; padding: 24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading recent notices...</div>';
    api("/api/notices").then(function (res) {
      var notices = (res && res.data ? res.data : []).slice(0, 3);
      if (!notices.length) {
        noticesList.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--text-muted);">No notices available.</div>';
        return;
      }
      noticesList.innerHTML = notices.map(function (n) {
        var dateStr = n.createdAt ? new Date(n.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
        var cat = escapeHtml(n.category || "General");
        var badgeClass = cat.toLowerCase() === "exam" ? "badge-danger" : cat.toLowerCase() === "academic" ? "badge-primary" : "badge-info";
        return '<div class="list-item">' +
          '<div class="list-item-main">' +
            '<span class="badge ' + badgeClass + '" style="margin-bottom: 3px;">' + cat + '</span>' +
            '<h4>' + escapeHtml(n.title) + '</h4>' +
            '<p>' + escapeHtml(n.body ? (n.body.length > 90 ? n.body.substring(0, 90) + '...' : n.body) : '') + '</p>' +
          '</div>' +
          '<div class="list-item-date">' + dateStr + '</div>' +
        '</div>';
      }).join("");
    }).catch(function (err) {
      if (noticesList) {
        noticesList.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--danger);">' +
          '<p style="font-size:13px; margin-bottom:8px;">Failed to load notices.</p>' +
          '<button class="btn btn-secondary btn-sm" onclick="loadDashboardNotices()">🔄 Retry</button>' +
        '</div>';
      }
    });
  }
  window.loadDashboardNotices = loadDashboardNotices;
  if (noticesList) loadDashboardNotices();

  // Dynamically load top 3 upcoming events from database for dashboard
  var eventsList = document.getElementById("dashboardRecentEvents");
  function loadDashboardEvents() {
    if (!eventsList) return;
    eventsList.innerHTML = '<div style="text-align:center; padding: 24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading upcoming events...</div>';
    api("/api/events").then(function (res) {
      var events = (res && res.data ? res.data : []).slice(0, 3);
      if (!events.length) {
        eventsList.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--text-muted);">No events available.</div>';
        return;
      }
      eventsList.innerHTML = events.map(function (ev) {
        var cat = escapeHtml(ev.category || "General");
        var badgeClass = cat.toLowerCase() === "workshop" ? "badge-success" : cat.toLowerCase() === "sports" ? "badge-warning" : "badge-info";
        return '<div class="list-item">' +
          '<div class="list-item-main">' +
            '<span class="badge ' + badgeClass + '" style="margin-bottom: 3px;">' + cat + '</span>' +
            '<h4>' + escapeHtml(ev.title) + '</h4>' +
            '<p>' + escapeHtml(ev.location || "Campus Center") + '</p>' +
          '</div>' +
          '<div class="list-item-date">' + escapeHtml(ev.date || 'Upcoming') + '</div>' +
        '</div>';
      }).join("");
    }).catch(function (err) {
      if (eventsList) {
        eventsList.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--danger);">' +
          '<p style="font-size:13px; margin-bottom:8px;">Failed to load events.</p>' +
          '<button class="btn btn-secondary btn-sm" onclick="loadDashboardEvents()">🔄 Retry</button>' +
        '</div>';
      }
    });
  }
  window.loadDashboardEvents = loadDashboardEvents;
  if (eventsList) loadDashboardEvents();
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
  var tableBody = document.getElementById("adminCoursesTableBody");
  var container = document.getElementById("coursesContainer");
  if (tableBody && !_allCoursesCache.length) {
    tableBody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 28px; color: var(--text-muted);"><span class="page-spinner"></span> Loading curriculum catalog...</td></tr>';
  }
  if (container && !_allCoursesCache.length) {
    container.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding: 36px; color: var(--text-muted);"><span class="page-spinner"></span> Loading curriculum courses...</div>';
  }

  api("/api/courses").then(function (res) {
    _allCoursesCache = res.data || [];
    updateAdminCourseStats(_allCoursesCache);
    filterAndRenderCourses();
  }).catch(function (err) {
    if (container) {
      container.innerHTML = '<div class="card" style="grid-column: 1 / -1; text-align:center; color: var(--danger); padding: 32px;">Could not load courses: ' + escapeHtml(err.message || "Network error") + '</div>';
    }
    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 28px; color: var(--danger);">Could not load courses: ' + escapeHtml(err.message || "Network error") + '</td></tr>';
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
var attendancePollTimer = null;

function initAttendance(role) {
  if (attendancePollTimer) {
    clearInterval(attendancePollTimer);
    attendancePollTimer = null;
  }

  function renderStudentAttendance() {
    if (document.hidden) return; // Tab in background, skip polling
    var summaryBody = document.querySelector('[data-role="attendance-summary-body"]');
    var historyBody = document.getElementById("attendanceHistoryBody");
    if (!summaryBody && !historyBody) {
      if (attendancePollTimer) {
        clearInterval(attendancePollTimer);
        attendancePollTimer = null;
      }
      return;
    }
    var syncBadge = document.getElementById("attendanceLastUpdated");

    api("/api/attendance/summary").then(function (res) {
      var rows = (res.data && res.data.rows) || [];
      var overall = (res.data && res.data.overall) || {};
      var history = (res.data && res.data.history) || [];

      if (summaryBody) {
        summaryBody.innerHTML = rows.length ? rows.map(function (r) {
          var pct = r.percentage !== undefined ? r.percentage : 0;
          var present = r.presentCount !== undefined ? r.presentCount : r.attended;
          var late = r.lateCount || 0;
          var held = r.held || r.totalConducted || 0;
          var absent = r.absentCount !== undefined ? r.absentCount : Math.max(0, held - (present + late));
          var isEligible = pct >= 75;
          return '<tr>' +
            '<td><strong>' + escapeHtml(r.courseCode) + '</strong></td>' +
            '<td>' + escapeHtml(r.courseTitle) + '</td>' +
            '<td>' + escapeHtml(r.instructor || '-') + '</td>' +
            '<td>' + held + '</td>' +
            '<td><span style="color:var(--success); font-weight:600;">' + present + '</span></td>' +
            '<td><span style="color:var(--warning); font-weight:600;">' + late + '</span></td>' +
            '<td><span style="color:var(--danger); font-weight:600;">' + absent + '</span></td>' +
            '<td><strong>' + pct + '%</strong></td>' +
            '<td><span class="badge ' + (isEligible ? 'badge-success' : 'badge-danger') + '">' + (isEligible ? 'Eligible' : 'Shortage') + '</span></td>' +
            '</tr>';
        }).join("") : '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);">No attendance records available.</td></tr>';
      }

      if (historyBody) {
        historyBody.innerHTML = history.length ? history.map(function (h) {
          var st = (h.status || "").toLowerCase();
          var cls = st === "present" ? "badge-success" : st === "late" ? "badge-warning" : "badge-danger";
          var label = st.charAt(0).toUpperCase() + st.slice(1);
          return '<tr>' +
            '<td><strong>' + escapeHtml(h.date || '-') + '</strong></td>' +
            '<td>' + escapeHtml(h.courseCode || '-') + '</td>' +
            '<td>' + escapeHtml(h.courseName || h.courseTitle || '-') + '</td>' +
            '<td><span class="badge badge-info">Div ' + escapeHtml(h.division || 'A') + '</span></td>' +
            '<td><span class="badge ' + cls + '">' + label + '</span></td>' +
            '<td>' + escapeHtml(h.markedBy || 'Faculty Instructor') + '</td>' +
            '</tr>';
        }).join("") : '<tr><td colspan="6" style="text-align:center; padding:24px; color: var(--text-muted);">No attendance records available.</td></tr>';
      }

      var histCountBadge = document.getElementById("historyCountBadge");
      if (histCountBadge) {
        histCountBadge.textContent = history.length + " Sessions Logged";
      }

      // Update stat cards
      var pctEl = document.getElementById("overallAttendancePct");
      var progBar = document.getElementById("overallProgressBar");
      var presEl = document.getElementById("classesAttendedCount");
      var lateEl = document.getElementById("classesLateCount");
      var absEl = document.getElementById("classesMissedCount");
      var totalEl = document.getElementById("classesTotalCount");
      var eligEl = document.getElementById("eligibilityStatus");
      var countEl = document.getElementById("presentCountDisplay");

      var overallPct = overall.percentage !== undefined ? overall.percentage : 0;
      var totalHeld = overall.totalConducted !== undefined ? overall.totalConducted : (overall.held || 0);
      var totalPres = overall.presentCount !== undefined ? overall.presentCount : (overall.attended || 0);
      var totalLate = overall.lateCount !== undefined ? overall.lateCount : 0;

      if (pctEl) pctEl.textContent = overallPct + "%";
      if (progBar) progBar.style.width = Math.min(100, overallPct) + "%";
      if (presEl) presEl.textContent = totalPres;
      if (lateEl) lateEl.textContent = totalLate;
      if (absEl) absEl.textContent = overall.absentCount !== undefined ? overall.absentCount : Math.max(0, totalHeld - (totalPres + totalLate));
      if (totalEl) totalEl.textContent = totalHeld;
      if (eligEl) {
        eligEl.innerHTML = totalHeld === 0
          ? '<span style="color:var(--text-muted);">No Classes Conducted</span>'
          : (overallPct >= 75
              ? '<span style="color:var(--success);">Eligible</span>'
              : '<span style="color:var(--danger);">Defaulter (<75%)</span>');
      }
      if (countEl) countEl.textContent = "Overall: " + overallPct + "% Attendance";

      if (syncBadge) {
        syncBadge.textContent = "Live Synced (" + new Date().toLocaleTimeString() + ")";
      }
    }).catch(function (err) {
      if (summaryBody) {
        summaryBody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--danger);">' +
          'Failed to load attendance records. <button class="btn btn-sm btn-outline-primary" onclick="renderStudentAttendance()" style="margin-left:8px;">🔄 Retry</button></td></tr>';
      }
      if (historyBody) {
        historyBody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color: var(--danger);">' +
          'Failed to load attendance logs. <button class="btn btn-sm btn-outline-primary" onclick="renderStudentAttendance()" style="margin-left:8px;">🔄 Retry</button></td></tr>';
      }
    });
  }

  window.renderStudentAttendance = renderStudentAttendance;

  var studentSec = document.getElementById("studentAttendanceSection");
  var facultyCard = document.getElementById("facultyRollCallCard");
  if (role === "student") {
    if (studentSec) studentSec.style.display = "block";
    if (facultyCard) facultyCard.style.display = "none";
    renderStudentAttendance();
    // Lightweight polling every 7 seconds for real-time attendance ledger updates
    attendancePollTimer = setInterval(renderStudentAttendance, 7000);
  } else if (role === "faculty" || role === "admin") {
    if (studentSec) studentSec.style.display = "none";
    if (facultyCard) {
      facultyCard.style.display = "block";
      initFacultyAttendanceControls();
    }
  }

  function initFacultyAttendanceControls() {
    var courseSelect = document.getElementById("facultyRollCourseSelect");
    var divSelect = document.getElementById("facultyRollDivisionSelect");
    var dateInput = document.getElementById("facultyRollDateInput");
    var tbody = document.getElementById("rollCallTableBody");
    var coursesList = [];

    if (dateInput && !dateInput.value) {
      dateInput.value = new Date().toISOString().split("T")[0];
    }

    function updateDivisions() {
      if (!divSelect || !courseSelect) return;
      var selectedCode = courseSelect.value;
      var matchedCourse = coursesList.find(function (c) { return c.code === selectedCode; });
      var divs = (matchedCourse && matchedCourse.assignedDivisions && matchedCourse.assignedDivisions.length)
        ? matchedCourse.assignedDivisions
        : ["A"];
      divSelect.innerHTML = divs.map(function (d) {
        return '<option value="' + escapeHtml(d) + '">Division ' + escapeHtml(d) + '</option>';
      }).join("");
    }

    api("/api/courses").then(function (res) {
      coursesList = res.data || [];
      if (courseSelect && coursesList.length) {
        courseSelect.innerHTML = coursesList.map(function (c) {
          return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
        }).join("");
      }
      updateDivisions();
      loadRollCall();
    }).catch(function () {
      loadRollCall();
    });

    if (courseSelect) courseSelect.addEventListener("change", function () {
      updateDivisions();
      loadRollCall();
    });
    if (divSelect) divSelect.addEventListener("change", loadRollCall);
    if (dateInput) dateInput.addEventListener("change", loadRollCall);

    function loadRollCall() {
      var rollCourse = courseSelect ? courseSelect.value : "";
      var rollDiv = divSelect ? divSelect.value : "A";
      var rollDate = dateInput ? dateInput.value : new Date().toISOString().split("T")[0];

      if (!rollCourse) {
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">Please select a course to view attendance roster.</td></tr>';
        }
        return;
      }

      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-muted);"><span class="page-spinner"></span> Loading roll-call roster...</td></tr>';
      }

      api("/api/attendance/roll-call?courseCode=" + encodeURIComponent(rollCourse) + "&division=" + encodeURIComponent(rollDiv) + "&date=" + encodeURIComponent(rollDate)).then(function (res) {
        if (!tbody) return;
        var roster = (res.data && res.data.roster) || [];
        if (!roster.length) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">No students enrolled in Division ' + escapeHtml(rollDiv) + ' for ' + escapeHtml(rollCourse) + '.</td></tr>';
          return;
        }
        tbody.innerHTML = roster.map(function (s) {
          var status = (s.status || "present").toLowerCase();
          var rollNum = s.rollNumber || s.roll_number || "-";
          var prn = s.prn || s.studentId || "-";
          return '<tr data-student-id="' + s.studentId + '">' +
            '<td><strong>' + escapeHtml(prn) + '</strong></td>' +
            '<td><span class="badge badge-secondary">' + escapeHtml(rollNum) + '</span></td>' +
            '<td><strong>' + escapeHtml(s.name) + '</strong></td>' +
            '<td>' + escapeHtml(s.department || '-') + '</td>' +
            '<td><span class="badge badge-info">Div ' + escapeHtml(s.division || rollDiv) + '</span></td>' +
            '<td>' +
              '<div class="status-toggle-group" style="display:inline-flex; gap:6px;">' +
                '<button type="button" class="btn btn-sm attend-btn ' + (status === 'present' ? 'btn-success active' : 'btn-secondary') + '" data-status="present">Present</button>' +
                '<button type="button" class="btn btn-sm attend-btn ' + (status === 'late' ? 'btn-warning active' : 'btn-secondary') + '" data-status="late">Late</button>' +
                '<button type="button" class="btn btn-sm attend-btn ' + (status === 'absent' ? 'btn-danger active' : 'btn-secondary') + '" data-status="absent">Absent</button>' +
              '</div>' +
            '</td></tr>';
        }).join("");
        wireAttendanceButtons();
      }).catch(function (err) {
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--danger);">' + escapeHtml(err.message || 'Error loading roster.') + '</td></tr>';
        }
      });
    }

    function wireAttendanceButtons() {
      if (!tbody) return;
      tbody.querySelectorAll("tr[data-student-id]").forEach(function (row) {
        var buttons = row.querySelectorAll(".attend-btn");
        buttons.forEach(function (btn) {
          btn.addEventListener("click", function () {
            if (getActiveRole() !== "faculty" && getActiveRole() !== "admin") {
              alert("Permission Denied: Only authorized faculty members can mark attendance.");
              return;
            }
            buttons.forEach(function (b) {
              b.classList.remove("active", "btn-success", "btn-warning", "btn-danger");
              b.classList.add("btn-secondary");
            });
            var st = this.getAttribute("data-status");
            this.classList.remove("btn-secondary");
            this.classList.add("active");
            if (st === "present") this.classList.add("btn-success");
            else if (st === "late") this.classList.add("btn-warning");
            else this.classList.add("btn-danger");
          });
        });
      });
    }

    window.saveFacultyAttendance = function () {
      var currentRole = getActiveRole();
      if (currentRole !== "faculty" && currentRole !== "admin") {
        showToast("Access Restricted", "Only authorized faculty members can save attendance.", "warning");
        return;
      }
      var saveBtn = document.getElementById("saveAttendanceBtn");
      var rollCourse = courseSelect ? courseSelect.value : "CS601";
      var rollDiv = divSelect ? divSelect.value : "A";
      var rollDate = dateInput ? dateInput.value : new Date().toISOString().split("T")[0];
      var records = [];
      var presentCount = 0;
      var lateCount = 0;
      var absentCount = 0;

      if (tbody) {
        tbody.querySelectorAll("tr[data-student-id]").forEach(function (row) {
          var activeBtn = row.querySelector(".attend-btn.active");
          var status = activeBtn ? activeBtn.getAttribute("data-status") : "present";
          if (status === "present") presentCount++;
          else if (status === "late") lateCount++;
          else absentCount++;
          records.push({ studentId: row.getAttribute("data-student-id"), status: status });
        });
      }

      setButtonLoading(saveBtn, "Saving Ledger...");

      api("/api/attendance/roll-call", {
        method: "POST",
        body: { courseCode: rollCourse, division: rollDiv, date: rollDate, records: records }
      }).then(function (res) {
        resetButton(saveBtn, '<span class="badge-saved">✓ Attendance Saved</span>');
        setTimeout(function () {
          resetButton(saveBtn, "Save Attendance");
        }, 2500);

        var bannerContainer = document.getElementById("rollCallStatusBanner");
        if (bannerContainer) {
          bannerContainer.innerHTML =
            '<div class="inline-banner inline-banner-success">' +
              '<span>✓ Attendance recorded for <strong>' + escapeHtml(rollCourse) + ' (Div ' + escapeHtml(rollDiv) + ', ' + escapeHtml(rollDate) + ')</strong>: ' +
              '<strong>' + presentCount + ' Present</strong>, <strong>' + lateCount + ' Late</strong>, <strong>' + absentCount + ' Absent</strong>. Records committed to academic ledger.</span>' +
              '<span class="inline-banner-close" onclick="this.parentElement.remove()">&times;</span>' +
            '</div>';
        }
        if (tbody) {
          tbody.querySelectorAll("tr[data-student-id]").forEach(function (r) {
            highlightRow(r, "update");
          });
        }
        showToast("Attendance Recorded", presentCount + " Present, " + lateCount + " Late, " + absentCount + " Absent (" + rollCourse + ")", "success");
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

// ---- Assignments module ------------------------------------------------------------
var assignmentsPollTimer = null;

function initAssignments(role) {
  if (assignmentsPollTimer) {
    clearInterval(assignmentsPollTimer);
    assignmentsPollTimer = null;
  }

  var studentCard = document.getElementById("studentAssignmentsCard");
  var facultyCard = document.getElementById("facultyAssignmentsCard");
  var submissionsCard = document.getElementById("assignmentSubmissionsCard");
  var syncBadge = document.getElementById("assignmentLastUpdated");

  var currentAssignmentsList = [];

  if (role === "student") {
    if (studentCard) studentCard.style.display = "block";
    if (facultyCard) facultyCard.style.display = "none";
    if (submissionsCard) submissionsCard.style.display = "none";
    loadStudentAssignments();
    // Real-time polling every 8 seconds for gradebook updates
    assignmentsPollTimer = setInterval(loadStudentAssignments, 8000);
  } else {
    if (studentCard) studentCard.style.display = "none";
    if (facultyCard) facultyCard.style.display = "block";
    initFacultyAssignments();
  }

  function loadStudentAssignments() {
    if (document.hidden) return; // Tab in background, skip polling
    var tbody = document.getElementById("studentAssignmentsTableBody");
    if (!tbody) {
      if (assignmentsPollTimer) {
        clearInterval(assignmentsPollTimer);
        assignmentsPollTimer = null;
      }
      return;
    }
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading assignments...</td></tr>';
    api("/api/assignments").then(function (res) {
      currentAssignmentsList = res.data || [];
      var assignments = currentAssignmentsList;
      var total = assignments.length;
      var submitted = 0;
      var pending = 0;
      var evaluated = 0;

      assignments.forEach(function (a) {
        var st = (a.submissionStatus || "not_submitted").toLowerCase();
        if (st === "evaluated" || a.isEvaluated) evaluated++;
        else if (st === "submitted" || st === "late" || st === "under_review") pending++;
      });
      submitted = pending + evaluated;

      var totEl = document.getElementById("totalAssignmentsCount");
      var subEl = document.getElementById("submittedAssignmentsCount");
      var penEl = document.getElementById("pendingEvaluationCount");
      var evaEl = document.getElementById("evaluatedAssignmentsCount");

      if (totEl) totEl.textContent = total;
      if (subEl) subEl.textContent = submitted;
      if (penEl) penEl.textContent = pending;
      if (evaEl) evaEl.textContent = evaluated;

      if (syncBadge) syncBadge.textContent = "Live Synced (" + new Date().toLocaleTimeString() + ")";

      if (!tbody) return;
      if (!assignments.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);">No assignments published for your courses.</td></tr>';
        return;
      }

      tbody.innerHTML = assignments.map(function (a) {
        var statusBadge = '';
        var st = (a.submissionStatus || "not_submitted").toLowerCase();
        var sub = a.submission || a.mySubmission || {};
        var isLocked = a.isLocked || sub.isLocked || (a.isSubmitted && sub.isLocked !== false);

        if (a.isEvaluated || st === "evaluated" || st === "graded") {
          statusBadge = '<span class="badge badge-success">Evaluated (' + (a.marksObtained !== null ? a.marksObtained + '/10' : '') + ')</span>';
        } else if (a.isSubmitted) {
          if (isLocked) {
            statusBadge = '<span class="badge badge-success">✓ Submitted (Locked)</span>';
          } else {
            statusBadge = '<span class="badge badge-warning">Correction Unlocked</span>';
          }
        } else if (st === "late") {
          statusBadge = '<span class="badge badge-warning">Late Submission</span>';
        } else {
          statusBadge = '<span class="badge badge-secondary">Not Submitted</span>';
        }

        var marksDisplay = '-';
        if (a.isEvaluated || (a.marksObtained !== null && a.marksObtained !== undefined)) {
          marksDisplay = '<strong style="color:var(--success); font-size:14px;">' + a.marksObtained + ' / ' + (a.totalPoints || 10) + '</strong>';
        }

        var feedbackDisplay = a.feedback ? escapeHtml(a.feedback) : '<span style="color:var(--text-muted);">-</span>';
        var deadlineStr = a.dueDate ? new Date(a.dueDate).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';

        var actionBtn = '';
        if (a.isEvaluated) {
          actionBtn = '<button class="btn btn-secondary btn-sm" onclick="openStudentSubmitModal(' + a.id + ')">View Evaluation</button>';
        } else if (a.isSubmitted) {
          if (isLocked) {
            actionBtn = '<button class="btn btn-secondary btn-sm" onclick="openStudentSubmitModal(' + a.id + ')">View Submission (Locked)</button>';
          } else {
            actionBtn = '<button class="btn btn-warning btn-sm" onclick="openStudentSubmitModal(' + a.id + ')">Submit Correction</button>';
          }
        } else {
          actionBtn = '<button class="btn btn-primary btn-sm" onclick="openStudentSubmitModal(' + a.id + ')">Submit Work</button>';
        }

        return '<tr data-assignment-id="' + a.id + '">' +
          '<td><strong>' + escapeHtml(a.courseCode || '-') + '</strong></td>' +
          '<td><strong>' + escapeHtml(a.title) + '</strong><br><small style="color:var(--text-muted);">' + escapeHtml((a.description || '').substring(0, 50)) + '...</small></td>' +
          '<td>' + escapeHtml(a.facultyName || 'Course Faculty') + '</td>' +
          '<td>' + escapeHtml(deadlineStr) + '</td>' +
          '<td><span class="badge badge-info">' + (a.totalPoints || 10) + ' Marks</span></td>' +
          '<td>' + statusBadge + '</td>' +
          '<td>' + marksDisplay + '</td>' +
          '<td style="max-width:200px;">' + feedbackDisplay + '</td>' +
          '<td>' + actionBtn + '</td>' +
          '</tr>';
      }).join("");
    }).catch(function (err) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--danger);">Failed to load assignments.</td></tr>';
    });
  }

  window.openStudentSubmitModal = function (assignmentId) {
    var a = currentAssignmentsList.find(function (item) { return item.id === assignmentId; });
    if (!a) return;

    var modalId = document.getElementById("submitModalAssignmentId");
    var titleEl = document.getElementById("submitModalAssignmentTitle");
    var courseInfo = document.getElementById("submitModalCourseInfo");
    var deadlineInfo = document.getElementById("submitModalDeadlineInfo");
    var instructions = document.getElementById("submitModalInstructions");
    var textInput = document.getElementById("submitTextContent");
    var fileInput = document.getElementById("submitFileInput");
    var errBox = document.getElementById("submitAssignmentError");
    var btn = document.getElementById("btnConfirmSubmit");

    var sub = a.submission || a.mySubmission || {};
    var isLocked = a.isLocked || sub.isLocked || (a.isSubmitted && sub.isLocked !== false);

    if (errBox) errBox.innerHTML = "";
    if (modalId) modalId.value = a.id;
    if (titleEl) titleEl.textContent = (isLocked ? "Submission Ledger: " : "Submit: ") + a.title;
    if (courseInfo) courseInfo.textContent = (a.courseCode || '') + " — " + (a.courseTitle || 'Coursework');
    if (deadlineInfo) deadlineInfo.textContent = "Deadline: " + (a.dueDate ? new Date(a.dueDate).toLocaleString() : 'No cutoff');
    if (instructions) instructions.textContent = a.description || "Submit written answer or attach file.";
    if (textInput) textInput.value = sub.submissionText || "";
    if (fileInput) fileInput.value = "";

    if (a.isSubmitted && isLocked) {
      if (errBox) {
        errBox.innerHTML = '<div class="inline-banner" style="margin-bottom:14px; background: rgba(16,185,129,0.08); border-left: 4px solid var(--success); padding: 12px 14px; border-radius: 4px; font-size: 13px; color: var(--text-main);">' +
          '🔒 <strong>Assignment submitted successfully. Editing and resubmission are disabled.</strong><br>' +
          '<small style="color:var(--text-muted); display:block; margin-top:4px;">Submitted at: ' + (sub.submittedAt ? new Date(sub.submittedAt).toLocaleString() : 'Recorded') + (sub.fileName ? ' • Attachment: ' + escapeHtml(sub.fileName) : '') + '</small>' +
          '</div>';
      }
      if (textInput) textInput.disabled = true;
      if (fileInput) fileInput.disabled = true;
      if (btn) btn.style.display = "none";
    } else {
      if (a.isSubmitted && !isLocked) {
        if (errBox) {
          errBox.innerHTML = '<div class="inline-banner" style="margin-bottom:14px; background: rgba(245,158,11,0.08); border-left: 4px solid var(--warning); padding: 10px 14px; border-radius: 4px; font-size: 13px; color: var(--text-main);">' +
            '⚠️ <strong>Exceptional correction unlocked by administration:</strong> ' + escapeHtml(sub.unlockReason || "Permission granted") +
            '</div>';
        }
      }
      if (textInput) textInput.disabled = false;
      if (fileInput) fileInput.disabled = false;
      if (btn) {
        btn.style.display = "inline-block";
        resetButton(btn, a.isSubmitted ? "Submit Correction" : "Submit Work");
      }
    }

    openModal("submitAssignmentModal");
  };

  window.confirmStudentSubmission = function () {
    var assignmentId = document.getElementById("submitModalAssignmentId").value;
    var textInput = document.getElementById("submitTextContent");
    var fileInput = document.getElementById("submitFileInput");
    var btn = document.getElementById("btnConfirmSubmit");
    var errBox = document.getElementById("submitAssignmentError");

    var textVal = textInput ? textInput.value.trim() : "";
    var file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;

    if (!textVal && !file) {
      if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Please provide either written answers or an attachment file.</div>';
      return;
    }

    setButtonLoading(btn, "Submitting...");

    var promise;
    if (file) {
      var formData = new FormData();
      formData.append("submissionText", textVal);
      formData.append("file", file);
      var token = sessionStorage.getItem("campus_session_token");
      var headers = {};
      if (token) headers["X-Session-Token"] = token;
      promise = fetch("/api/assignments/" + encodeURIComponent(assignmentId) + "/submit", {
        method: "POST",
        headers: headers,
        body: formData,
        credentials: "include"
      }).then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok || !data.success) throw new Error(data.error || "Submission failed");
          return data;
        });
      });
    } else {
      promise = api("/api/assignments/" + encodeURIComponent(assignmentId) + "/submit", {
        method: "POST",
        body: { submissionText: textVal }
      });
    }

    promise.then(function (res) {
      resetButton(btn, "Submit Work");
      closeModal("submitAssignmentModal");
      showToast("Submission Locked", "Assignment submitted successfully. Editing and resubmission are disabled.", "success", 5000);
      loadStudentAssignments();
    }).catch(function (err) {
      resetButton(btn, "Submit Work");
      if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">' + escapeHtml(err.message || "Failed to submit assignment.") + '</div>';
    });
  };

  function initFacultyAssignments() {
    var courseFilter = document.getElementById("facultyCourseFilter");
    var newCourseSelect = document.getElementById("newAssignmentCourse");
    var tbody = document.getElementById("facultyAssignmentsTableBody");

    api("/api/courses").then(function (res) {
      var courses = res.data || [];
      if (courseFilter) {
        courseFilter.innerHTML = '<option value="all">All Assigned Courses</option>' +
          courses.map(function (c) {
            return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
          }).join("");
      }
      if (newCourseSelect) {
        newCourseSelect.innerHTML = '<option value="">Select Course...</option>' +
          courses.map(function (c) {
            return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
          }).join("");
      }
      loadFacultyAssignmentsList();
    }).catch(function () {
      loadFacultyAssignmentsList();
    });

    if (courseFilter) courseFilter.addEventListener("change", loadFacultyAssignmentsList);

    function loadFacultyAssignmentsList() {
      var selectedCourse = courseFilter ? courseFilter.value : "all";
      if (tbody) tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading course assignments...</td></tr>';
      api("/api/assignments").then(function (res) {
        var assignments = res.data || [];
        if (selectedCourse !== "all") {
          assignments = assignments.filter(function (a) { return a.courseCode === selectedCourse; });
        }
        currentAssignmentsList = assignments;

        var total = assignments.length;
        var totalSubs = 0;
        var totalPending = 0;
        var totalEval = 0;

        assignments.forEach(function (a) {
          var counts = a.evaluationCounts || {};
          totalSubs += counts.submissions || 0;
          totalPending += counts.awaiting_evaluation || 0;
          totalEval += counts.evaluated || 0;
        });

        var totEl = document.getElementById("totalAssignmentsCount");
        var subEl = document.getElementById("submittedAssignmentsCount");
        var penEl = document.getElementById("pendingEvaluationCount");
        var evaEl = document.getElementById("evaluatedAssignmentsCount");

        if (totEl) totEl.textContent = total;
        if (subEl) subEl.textContent = totalSubs;
        if (penEl) penEl.textContent = totalPending;
        if (evaEl) evaEl.textContent = totalEval;

        if (!tbody) return;
        if (!assignments.length) {
          tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);">No assignments found. Click "+ Create Assignment" to publish.</td></tr>';
          return;
        }

        tbody.innerHTML = assignments.map(function (a) {
          var counts = a.evaluationCounts || {};
          var deadlineStr = a.dueDate ? new Date(a.dueDate).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';
          return '<tr data-assignment-id="' + a.id + '">' +
            '<td><strong>' + escapeHtml(a.courseCode || '-') + '</strong></td>' +
            '<td><span class="badge badge-info">Div ' + escapeHtml(a.division || 'ALL') + '</span></td>' +
            '<td><strong>' + escapeHtml(a.title) + '</strong></td>' +
            '<td>' + escapeHtml(deadlineStr) + '</td>' +
            '<td><span class="badge badge-secondary">' + (a.totalPoints || 10) + ' pts</span></td>' +
            '<td>' + (counts.eligible_students || 0) + '</td>' +
            '<td><strong style="color:var(--primary);">' + (counts.submissions || 0) + '</strong></td>' +
            '<td><strong style="color:var(--warning);">' + (counts.awaiting_evaluation || 0) + '</strong></td>' +
            '<td><strong style="color:var(--success);">' + (counts.evaluated || 0) + '</strong></td>' +
            '<td><button class="btn btn-primary btn-sm" onclick="openSubmissionsRoster(' + a.id + ')">Review Submissions</button></td>' +
            '</tr>';
        }).join("");
      }).catch(function (err) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--danger);">Failed to load assignments.</td></tr>';
      });
    }

    window.submitCreateAssignment = function () {
      var title = document.getElementById("newAssignmentTitle").value.trim();
      var course = document.getElementById("newAssignmentCourse").value;
      var division = document.getElementById("newAssignmentDivision").value;
      var deadline = document.getElementById("newAssignmentDeadline").value;
      var description = document.getElementById("newAssignmentDescription").value.trim();
      var errBox = document.getElementById("createAssignmentError");
      var btn = document.getElementById("btnPublishAssignment");

      if (!title || !course || !deadline || !description) {
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Please fill in all required fields.</div>';
        return;
      }

      setButtonLoading(btn, "Publishing...");

      api("/api/assignments", {
        method: "POST",
        body: {
          title: title,
          courseCode: course,
          division: division,
          dueDate: deadline,
          description: description,
          totalPoints: 10
        }
      }).then(function (res) {
        resetButton(btn, "Publish Assignment");
        closeModal("createAssignmentModal");
        showToast("Success", "Assignment published successfully!", "success");
        document.getElementById("newAssignmentTitle").value = "";
        document.getElementById("newAssignmentDescription").value = "";
        loadFacultyAssignmentsList();
      }).catch(function (err) {
        resetButton(btn, "Publish Assignment");
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">' + escapeHtml(err.message || "Failed to create assignment.") + '</div>';
      });
    };

    window.openSubmissionsRoster = function (assignmentId) {
      var subCard = document.getElementById("assignmentSubmissionsCard");
      var titleEl = document.getElementById("submissionsCardTitle");
      var subTitleEl = document.getElementById("submissionsCardSubtitle");
      var tbody = document.getElementById("assignmentSubmissionsTableBody");

      if (subCard) subCard.style.display = "block";
      if (tbody) tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading student roster...</td></tr>';

      api("/api/assignments/" + encodeURIComponent(assignmentId) + "/evaluation-roster").then(function (res) {
        var data = res.data || {};
        var assignment = data.assignment || {};
        var roster = data.roster || [];
        var counts = data.counts || {};

        if (titleEl) titleEl.textContent = "Submissions Roster: " + assignment.title;
        if (subTitleEl) subTitleEl.textContent = (assignment.courseCode || '') + " (Div " + (assignment.division || 'ALL') + ") — " +
          counts.submissions + " Submissions (" + counts.awaiting_evaluation + " Awaiting Review, " + counts.evaluated + " Evaluated)";

        window.currentRosterSubmissions = roster;
        window.currentRosterAssignment = assignment;

        if (!tbody) return;
        if (!roster.length) {
          tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--text-muted);">No enrolled students found for this assignment cohort.</td></tr>';
          return;
        }

        tbody.innerHTML = roster.map(function (s) {
          var isSubmitted = s.id !== null && s.id !== undefined;
          var statusBadge = '';
          if (s.isEvaluated) {
            statusBadge = '<span class="badge badge-success">Evaluated</span>';
          } else if (s.status === "late") {
            statusBadge = '<span class="badge badge-warning">Late Submission</span>';
          } else if (isSubmitted) {
            statusBadge = '<span class="badge badge-primary">Submitted</span>';
          } else {
            statusBadge = '<span class="badge badge-secondary">Not Submitted</span>';
          }

          var marksDisplay = '-';
          if (s.isEvaluated && s.grade !== null) {
            marksDisplay = '<strong style="color:var(--success); font-size:14px;">' + s.grade + ' / 10</strong>';
          }

          var contentPreview = '-';
          if (isSubmitted) {
            var parts = [];
            if (s.submissionText) parts.push('<span title="' + escapeHtml(s.submissionText) + '">📝 ' + escapeHtml(s.submissionText.substring(0, 30)) + '...</span>');
            if (s.isPdf) {
              parts.push('<button type="button" class="btn btn-primary btn-sm btn-view-pdf" style="padding:2px 8px; font-size:11px; margin-right:4px;" onclick="openPdfViewerFromRoster(' + s.id + ')">📄 View PDF</button>');
              if (s.downloadUrl) {
                parts.push('<a href="' + escapeHtml(s.downloadUrl) + '" target="_blank" class="btn btn-secondary btn-sm" style="padding:2px 8px; font-size:11px;" title="Download PDF to device">📥</a>');
              }
            } else if (s.downloadUrl) {
              parts.push('<a href="' + escapeHtml(s.downloadUrl) + '" target="_blank" class="btn btn-secondary btn-sm" style="padding:2px 8px; font-size:11px;">📥 ' + escapeHtml(s.fileName || 'File') + '</a>');
              if (s.fileExtension) {
                parts.push('<span class="badge badge-secondary" style="font-size:10px; margin-left:3px;">' + escapeHtml(s.fileExtension.toUpperCase()) + '</span>');
              }
            }
            contentPreview = parts.join(" ") || 'Submitted';
          }

          var actionBtn = '';
          if (isSubmitted) {
            var escapedStudentName = escapeHtml(s.studentName || '').replace(/'/g, "\\'");
            var escapedPrn = escapeHtml(s.prn || '').replace(/'/g, "\\'");
            var escapedTitle = escapeHtml(assignment.title || '').replace(/'/g, "\\'");
            var escapedFeedback = escapeHtml(s.feedback || '').replace(/'/g, "\\'");
            var escapedText = escapeHtml(s.submissionText || '').replace(/'/g, "\\'");
            var downloadUrl = s.downloadUrl ? escapeHtml(s.downloadUrl).replace(/'/g, "\\'") : '';
            var gradeVal = s.grade !== null && s.grade !== undefined ? s.grade : 'null';
            var escapedFileName = s.fileName ? escapeHtml(s.fileName).replace(/'/g, "\\'") : '';
            var isPdfFlag = s.isPdf ? 'true' : 'false';

            var evalBtn = '<button class="btn btn-primary btn-sm" onclick="openEvaluationModal(' + assignmentId + ', ' + s.id + ', \'' + escapedStudentName + '\', \'' + escapedPrn + '\', \'' + escapedTitle + '\', ' + gradeVal + ', \'' + escapedFeedback + '\', \'' + escapedText + '\', \'' + downloadUrl + '\', \'' + escapedFileName + '\', ' + isPdfFlag + ')">' + (s.isEvaluated ? 'Edit Marks' : 'Evaluate') + '</button>';
            var pdfBtn = s.isPdf ? ' <button type="button" class="btn btn-secondary btn-sm" onclick="openPdfViewerFromRoster(' + s.id + ')" title="View assignment PDF in-screen">📄 View PDF</button>' : '';
            actionBtn = evalBtn + pdfBtn;
          } else {
            actionBtn = '<span style="color:var(--text-muted); font-size:12px;">Awaiting</span>';
          }

          return '<tr data-submission-id="' + (s.id || '') + '">' +
            '<td><strong>' + escapeHtml(s.prn || '-') + '</strong></td>' +
            '<td><span class="badge badge-secondary">' + escapeHtml(s.rollNumber || '-') + '</span></td>' +
            '<td><strong>' + escapeHtml(s.studentName || '-') + '</strong></td>' +
            '<td>' + (s.submittedAt ? new Date(s.submittedAt).toLocaleString([], { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '-') + '</td>' +
            '<td>' + statusBadge + '</td>' +
            '<td>' + contentPreview + '</td>' +
            '<td>' + marksDisplay + '</td>' +
            '<td style="max-width:180px;">' + (s.feedback ? escapeHtml(s.feedback) : '-') + '</td>' +
            '<td>' + actionBtn + '</td>' +
            '</tr>';
        }).join("");

        subCard.scrollIntoView({ behavior: "smooth" });
      }).catch(function (err) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color: var(--danger);">' + escapeHtml(err.message || 'Error loading roster.') + '</td></tr>';
      });
    };

    window.closeSubmissionsRoster = function () {
      var subCard = document.getElementById("assignmentSubmissionsCard");
      if (subCard) subCard.style.display = "none";
    };

    var currentEvalSubmissionData = null;
    var activePdfSubmission = null;
    var activePdfBlobUrl = null;

    window.openEvaluationModal = function (assignmentId, submissionId, studentName, prn, title, existingGrade, existingFeedback, textContent, downloadUrl, fileName, isPdf) {
      currentEvalSubmissionData = {
        id: submissionId,
        assignmentId: assignmentId,
        studentName: studentName,
        prn: prn,
        assignmentTitle: title,
        grade: (existingGrade !== null && existingGrade !== undefined) ? existingGrade : null,
        feedback: existingFeedback || "",
        submissionText: textContent || "",
        downloadUrl: downloadUrl || null,
        fileName: fileName || null,
        isPdf: isPdf === true || isPdf === "true",
        previewUrl: (isPdf === true || isPdf === "true") ? ("/api/assignments/submissions/" + submissionId + "/preview") : null
      };

      document.getElementById("evalSubmissionId").value = submissionId;
      document.getElementById("evalStudentName").textContent = studentName;
      document.getElementById("evalStudentPRN").textContent = prn;
      document.getElementById("evalAssignmentTitle").textContent = title;
      document.getElementById("evalSubmissionTextPreview").textContent = textContent || "No written text provided.";

      var dlGroup = document.getElementById("evalFileDownloadGroup");
      var dlLink = document.getElementById("evalDownloadLink");
      var dlText = document.getElementById("evalDownloadText");
      var viewPdfBtn = document.getElementById("evalViewPdfBtn");
      var nonPdfNotice = document.getElementById("evalFileNonPdfNotice");

      if (downloadUrl) {
        if (dlGroup) dlGroup.style.display = "block";
        if (dlLink) dlLink.href = downloadUrl;
        if (dlText) dlText.textContent = fileName ? ("Download (" + fileName + ")") : "Download Student File";

        if (currentEvalSubmissionData.isPdf) {
          if (viewPdfBtn) viewPdfBtn.style.display = "inline-flex";
          if (nonPdfNotice) nonPdfNotice.style.display = "none";
        } else {
          if (viewPdfBtn) viewPdfBtn.style.display = "none";
          if (nonPdfNotice) {
            nonPdfNotice.style.display = "block";
            var ext = fileName && fileName.indexOf(".") !== -1 ? fileName.split(".").pop().toUpperCase() : "File";
            nonPdfNotice.textContent = "ℹ️ In-screen viewer is available for PDF files. Use Download for " + ext + " format.";
          }
        }
      } else {
        if (dlGroup) dlGroup.style.display = "none";
        if (viewPdfBtn) viewPdfBtn.style.display = "none";
        if (nonPdfNotice) nonPdfNotice.style.display = "none";
      }

      var marksInput = document.getElementById("evalMarksInput");
      var feedbackInput = document.getElementById("evalFeedbackInput");
      var errBox = document.getElementById("evaluationError");

      if (errBox) errBox.innerHTML = "";
      if (marksInput) marksInput.value = (existingGrade !== null && existingGrade !== undefined) ? existingGrade : "";
      if (feedbackInput) feedbackInput.value = existingFeedback || "";

      openModal("evaluateSubmissionModal");
    };

    window.openPdfViewerFromEvalModal = function () {
      if (!currentEvalSubmissionData) return;
      var em = document.getElementById("evalMarksInput");
      var ef = document.getElementById("evalFeedbackInput");
      if (em && em.value !== "") currentEvalSubmissionData.grade = parseFloat(em.value);
      if (ef && ef.value !== "") currentEvalSubmissionData.feedback = ef.value;
      openPdfViewer(currentEvalSubmissionData, "evalModal");
    };

    window.openPdfViewerFromRoster = function (subId) {
      var s = (window.currentRosterSubmissions || []).find(function (item) { return item.id === subId; });
      if (!s) return;
      var data = Object.assign({}, s, {
        assignmentTitle: (window.currentRosterAssignment ? window.currentRosterAssignment.title : "Assignment")
      });
      openPdfViewer(data, "roster");
    };

    window.openPdfViewer = function (data, origin) {
      activePdfSubmission = data;
      data.openedFromEvalModal = (origin === "evalModal");

      var iframe = document.getElementById("pdfViewerIframe");
      var overlay = document.getElementById("pdfLoadingOverlay");
      var titleEl = document.getElementById("pdfViewerTitle");
      var subTitleEl = document.getElementById("pdfViewerSubtitle");
      var fileNameEl = document.getElementById("pdfViewerFileName");
      var dlBtn = document.getElementById("pdfViewerDownloadBtn");
      var extBtn = document.getElementById("pdfViewerExternalBtn");

      var stuNameEl = document.getElementById("pdfEvalStudentName");
      var prnEl = document.getElementById("pdfEvalPRN");
      var rollEl = document.getElementById("pdfEvalRoll");
      var submittedEl = document.getElementById("pdfEvalSubmittedAt");
      var statusBadge = document.getElementById("pdfEvalStatusBadge");
      var textGroup = document.getElementById("pdfEvalTextGroup");
      var textContent = document.getElementById("pdfEvalTextContent");
      var marksInput = document.getElementById("pdfEvalMarksInput");
      var feedbackInput = document.getElementById("pdfEvalFeedbackInput");
      var errBox = document.getElementById("pdfViewerEvalError");

      if (errBox) errBox.innerHTML = "";
      if (titleEl) titleEl.textContent = (data.studentName || "Student") + " — " + (data.assignmentTitle || "Assignment Submission");
      if (subTitleEl) subTitleEl.textContent = "PRN: " + (data.prn || "-") + " • " + (data.fileName || "document.pdf");
      if (fileNameEl) fileNameEl.textContent = data.fileName || "document.pdf";
      if (stuNameEl) stuNameEl.textContent = data.studentName || "Student";
      if (prnEl) prnEl.textContent = "PRN: " + (data.prn || "-");
      if (rollEl) rollEl.textContent = "Roll: " + (data.rollNumber || "-");
      if (submittedEl) submittedEl.textContent = data.submittedAt ? ("Submitted: " + new Date(data.submittedAt).toLocaleString()) : "Submitted";
      if (statusBadge) {
        statusBadge.textContent = data.isEvaluated ? "Evaluated" : (data.status === "late" ? "Late" : "Submitted");
        statusBadge.className = "badge " + (data.isEvaluated ? "badge-success" : (data.status === "late" ? "badge-warning" : "badge-primary"));
      }

      if (data.submissionText) {
        if (textGroup) textGroup.style.display = "block";
        if (textContent) textContent.textContent = data.submissionText;
      } else {
        if (textGroup) textGroup.style.display = "none";
      }

      // Synchronize grading fields from eval modal if opened from there, or from submission data
      var existingMarks = "";
      var existingFeedback = "";
      if (data.openedFromEvalModal) {
        var em = document.getElementById("evalMarksInput");
        var ef = document.getElementById("evalFeedbackInput");
        existingMarks = (em && em.value !== "") ? em.value : (data.grade !== null && data.grade !== undefined ? data.grade : "");
        existingFeedback = (ef && ef.value !== "") ? ef.value : (data.feedback || "");
      } else {
        existingMarks = (data.grade !== null && data.grade !== undefined) ? data.grade : "";
        existingFeedback = data.feedback || "";
      }

      if (marksInput) marksInput.value = existingMarks;
      if (feedbackInput) feedbackInput.value = existingFeedback;

      var token = sessionStorage.getItem("campus_session_token");
      var previewEndpoint = data.previewUrl || ("/api/assignments/submissions/" + data.id + "/preview");
      var downloadEndpoint = data.downloadUrl || ("/api/assignments/submissions/" + data.id + "/download");

      if (dlBtn) dlBtn.href = downloadEndpoint + (token ? ("?token=" + encodeURIComponent(token)) : "");
      if (extBtn) extBtn.href = previewEndpoint + (token ? ("?token=" + encodeURIComponent(token)) : "");

      if (overlay) {
        overlay.style.display = "flex";
        overlay.innerHTML = '<span class="btn-spinner" style="width: 24px; height: 24px; border-width: 3px;"></span><span>Loading in-screen PDF document...</span>';
      }
      if (iframe) iframe.src = "about:blank";

      if (activePdfBlobUrl) {
        URL.revokeObjectURL(activePdfBlobUrl);
        activePdfBlobUrl = null;
      }

      openModal("assignmentPdfViewerModal");

      var authHeaders = {};
      if (token) {
        authHeaders["Authorization"] = "Bearer " + token;
        authHeaders["X-Session-Token"] = token;
      }

      fetch(previewEndpoint, {
        method: "GET",
        headers: authHeaders
      }).then(function (res) {
        if (!res.ok) {
          return res.json().then(function (errData) {
            throw new Error(errData.error || ("Failed to load preview (HTTP " + res.status + ")"));
          }).catch(function (e) {
            throw new Error(e.message || "Failed to load PDF preview");
          });
        }
        return res.blob();
      }).then(function (blob) {
        if (overlay) overlay.style.display = "none";
        var pdfBlob = new Blob([blob], { type: "application/pdf" });
        activePdfBlobUrl = URL.createObjectURL(pdfBlob);
        if (iframe) {
          iframe.src = activePdfBlobUrl;
        }
      }).catch(function (err) {
        if (overlay) {
          overlay.innerHTML = '<div style="color:#ef4444; font-weight:600; text-align:center; padding:20px;">' +
            '<div>⚠️ ' + escapeHtml(err.message || "Could not render PDF preview in-screen.") + '</div>' +
            '<div style="margin-top:12px;"><a href="' + escapeHtml(downloadEndpoint) + '" class="btn btn-secondary btn-sm" download>📥 Download File Instead</a></div>' +
            '</div>';
        }
      });
    };

    window.closePdfViewerModal = function () {
      if (activePdfSubmission) {
        var pdfMarks = document.getElementById("pdfEvalMarksInput");
        var pdfFeed = document.getElementById("pdfEvalFeedbackInput");
        var evalMarks = document.getElementById("evalMarksInput");
        var evalFeed = document.getElementById("evalFeedbackInput");

        if (activePdfSubmission.openedFromEvalModal && evalMarks && evalFeed && pdfMarks && pdfFeed) {
          if (pdfMarks.value !== "") evalMarks.value = pdfMarks.value;
          if (pdfFeed.value !== "") evalFeed.value = pdfFeed.value;
        }
      }

      closeModal("assignmentPdfViewerModal");

      var iframe = document.getElementById("pdfViewerIframe");
      if (iframe) iframe.src = "about:blank";

      if (activePdfBlobUrl) {
        URL.revokeObjectURL(activePdfBlobUrl);
        activePdfBlobUrl = null;
      }
    };

    window.savePdfViewerEvaluation = function () {
      if (!activePdfSubmission || !activePdfSubmission.id) return;
      var subId = activePdfSubmission.id;
      var marksInput = document.getElementById("pdfEvalMarksInput");
      var feedbackInput = document.getElementById("pdfEvalFeedbackInput");
      var btn = document.getElementById("btnPdfSaveEvaluation");
      var errBox = document.getElementById("pdfViewerEvalError");

      var marksVal = parseFloat(marksInput ? marksInput.value : "");
      var feedbackVal = feedbackInput ? feedbackInput.value.trim() : "";

      if (isNaN(marksVal) || marksVal < 0 || marksVal > 10) {
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Marks must be a valid number between 0 and 10 inclusive.</div>';
        return;
      }
      if (!feedbackVal) {
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Please provide feedback for the student.</div>';
        return;
      }

      setButtonLoading(btn, "Saving Marks...");

      api("/api/assignments/submissions/" + encodeURIComponent(subId) + "/grade", {
        method: "POST",
        body: { marks_obtained: marksVal, feedback: feedbackVal }
      }).then(function (res) {
        resetButton(btn, "Save Evaluation");
        showToast("Marks Recorded", "Evaluated " + marksVal + "/10 with feedback.", "success");

        var evalMarks = document.getElementById("evalMarksInput");
        var evalFeed = document.getElementById("evalFeedbackInput");
        if (evalMarks) evalMarks.value = marksVal;
        if (evalFeed) evalFeed.value = feedbackVal;

        if (activePdfSubmission.assignmentId) {
          openSubmissionsRoster(activePdfSubmission.assignmentId);
        }
        loadFacultyAssignmentsList();
      }).catch(function (err) {
        resetButton(btn, "Save Evaluation");
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">' + escapeHtml(err.message || "Failed to record evaluation.") + '</div>';
      });
    };

    window.saveSubmissionEvaluation = function () {
      var subId = document.getElementById("evalSubmissionId").value;
      var marksInput = document.getElementById("evalMarksInput");
      var feedbackInput = document.getElementById("evalFeedbackInput");
      var btn = document.getElementById("btnSaveEvaluation");
      var errBox = document.getElementById("evaluationError");

      var marksVal = parseFloat(marksInput ? marksInput.value : "");
      var feedbackVal = feedbackInput ? feedbackInput.value.trim() : "";

      if (isNaN(marksVal) || marksVal < 0 || marksVal > 10) {
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Marks must be a valid number between 0 and 10 inclusive.</div>';
        return;
      }
      if (!feedbackVal) {
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">Please provide feedback for the student.</div>';
        return;
      }

      setButtonLoading(btn, "Saving Marks...");

      api("/api/assignments/submissions/" + encodeURIComponent(subId) + "/grade", {
        method: "POST",
        body: { marks_obtained: marksVal, feedback: feedbackVal }
      }).then(function (res) {
        resetButton(btn, "Save Evaluation");
        closeModal("evaluateSubmissionModal");
        showToast("Marks Recorded", "Evaluated " + marksVal + "/10 with feedback.", "success");
        if (currentEvalSubmissionData && currentEvalSubmissionData.assignmentId) {
          openSubmissionsRoster(currentEvalSubmissionData.assignmentId);
        }
        loadFacultyAssignmentsList();
      }).catch(function (err) {
        resetButton(btn, "Save Evaluation");
        if (errBox) errBox.innerHTML = '<div class="inline-banner inline-banner-error">' + escapeHtml(err.message || "Failed to record evaluation.") + '</div>';
      });
    };
  }
}

// ---- Results module (Modules 2, 3, 4, 5, 6, 7) --------------------------------
function initResults(role) {
  var studentView = document.getElementById("studentResultView");
  var facultyView = document.getElementById("facultyResultView");
  var adminView = document.getElementById("adminResultView");
  if (!studentView && !facultyView && !adminView) return;

  if (role === "student") {
    if (studentView) { studentView.style.display = "block"; loadStudentResults(); }
    if (facultyView) facultyView.remove();
    if (adminView) adminView.remove();
  } else if (role === "faculty") {
    if (facultyView) { facultyView.style.display = "block"; loadFacultyMarksSheet(); }
    if (studentView) studentView.remove();
    if (adminView) adminView.remove();
  } else if (role === "admin") {
    if (adminView) {
      adminView.style.display = "block";
      loadAdminLifecycle();
      // Populate department dropdowns across admin tabs
      api("/api/departments").then(function (res) {
        var depts = res.data || [];
        ["adminCardDeptFilter", "toppersDeptSelect", "analyticsDeptSelect"].forEach(function (id) {
          var sel = document.getElementById(id);
          if (sel && depts.length) {
            sel.innerHTML = '<option value="all">All Departments</option>' + depts.map(function (d) {
              return '<option value="' + escapeHtml(d.code || d.name) + '">' + escapeHtml(d.name) + '</option>';
            }).join("");
          }
        });
      }).catch(function () {});
    }
    if (studentView) studentView.remove();
    if (facultyView) facultyView.remove();
  }

  // =========================================================================
  // 1. STUDENT VIEW LOGIC (Modules 4 & 7)
  // =========================================================================
  window.switchStudentResultsTab = function (tab) {
    var pubSec = document.getElementById("studentPublishedSection");
    var histSec = document.getElementById("studentHistorySection");
    var btnPub = document.getElementById("btnStudentTabPublished");
    var btnHist = document.getElementById("btnStudentTabHistory");

    if (tab === "history") {
      if (pubSec) pubSec.style.display = "none";
      if (histSec) histSec.style.display = "block";
      if (btnPub) btnPub.classList.remove("active");
      if (btnHist) btnHist.classList.add("active");
      loadStudentHistory();
    } else {
      if (pubSec) pubSec.style.display = "block";
      if (histSec) histSec.style.display = "none";
      if (btnPub) btnPub.classList.add("active");
      if (btnHist) btnHist.classList.remove("active");
      loadStudentResults();
    }
  };

  function loadStudentResults() {
    var tbody = document.getElementById("studentResultsTableBody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading academic results...</td></tr>';

    var sgpaEl = document.getElementById("studentSgpa");
    var cgpaEl = document.getElementById("studentCgpa");
    var creditsEl = document.getElementById("studentCredits");
    var statusEl = document.getElementById("studentResultStatus");

    api("/api/results").then(function (res) {
      var rows = res.data || [];
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);">No examination results have been officially published for your account yet.</td></tr>';
        if (sgpaEl) sgpaEl.textContent = "N/A";
        if (cgpaEl) cgpaEl.textContent = "N/A";
        if (creditsEl) creditsEl.textContent = "0";
        if (statusEl) {
          statusEl.textContent = "Awaiting Publication";
          statusEl.style.color = "var(--text-muted)";
        }
        return;
      }

      var totalMarks = 0;
      var totalPossible = 0;
      var totalCredits = 0;
      var passedCount = 0;

      tbody.innerHTML = rows.map(function (r) {
        var isPass = r.isPassed;
        if (isPass) passedCount++;
        totalMarks += (r.total || 0);
        totalPossible += (r.maxTotal || 100);
        var cred = r.credits || 4;
        if (isPass) totalCredits += cred;

        return '<tr>' +
          '<td><strong>' + escapeHtml(r.courseCode) + '</strong></td>' +
          '<td>' + escapeHtml(r.courseTitle || '-') + '</td>' +
          '<td>' + (r.ca1 !== undefined ? r.ca1 : '-') + '</td>' +
          '<td>' + (r.ca2 !== undefined ? r.ca2 : '-') + '</td>' +
          '<td>' + (r.midSem !== undefined ? r.midSem : '-') + '</td>' +
          '<td>' + (r.endSem !== undefined ? r.endSem : '-') + '</td>' +
          '<td><strong>' + r.total + '</strong></td>' +
          '<td><span class="badge badge-' + (isPass ? 'success' : 'danger') + '">' + escapeHtml(r.grade || (isPass ? 'P' : 'F')) + '</span></td>' +
          '<td>' + cred + '</td>' +
          '<td><span class="badge badge-' + (isPass ? 'success' : 'danger') + '">' + (isPass ? 'Pass' : 'Fail') + '</span></td>' +
          '</tr>';
      }).join("");

      var pct = totalPossible > 0 ? (totalMarks / totalPossible) * 100 : 0;
      var sgpa = (pct / 10).toFixed(2);
      var allPassed = passedCount === rows.length;

      if (sgpaEl) sgpaEl.textContent = sgpa;
      if (cgpaEl) cgpaEl.textContent = sgpa;
      if (creditsEl) creditsEl.textContent = String(totalCredits);
      if (statusEl) {
        statusEl.textContent = allPassed ? "PASSED (First Class)" : "ATKT / Backlog (" + (rows.length - passedCount) + ")";
        statusEl.style.color = allPassed ? "var(--success)" : "var(--danger)";
      }
    }).catch(function (err) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--danger);">Failed to load academic results.</td></tr>';
    });
  }

  function loadStudentHistory() {
    var cont = document.getElementById("studentHistoryContainer");
    if (!cont) return;
    cont.innerHTML = '<div style="text-align:center; padding: 24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading performance history...</div>';

    var ref = (CURRENT_USER && (CURRENT_USER.prn || CURRENT_USER.studentId || CURRENT_USER.id)) || "me";
    api("/api/results/history/" + encodeURIComponent(ref)).then(function (res) {
      var history = res.data || [];
      if (!history.length) {
        cont.innerHTML = '<div style="text-align:center; padding: 28px; color: var(--text-muted);">No multi-semester academic progression records found yet.</div>';
        return;
      }

      var html = '<div style="display: grid; gap: 16px;">';
      history.forEach(function (h) {
        var backlogsBadge = h.backlogs === 0
          ? '<span class="badge badge-success">0 Backlogs (All Cleared)</span>'
          : '<span class="badge badge-danger">' + h.backlogs + ' Backlog(s)</span>';

        html += '<div style="background: var(--bg-subtle); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 16px;">' +
          '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">' +
            '<h4 style="margin: 0; font-size: 15px; color: var(--text-main); font-weight: 700;">' + escapeHtml(h.semester) + '</h4>' +
            '<div style="display: flex; gap: 8px; align-items: center;">' +
              '<span class="badge badge-primary">SGPA: ' + h.sgpa + '</span>' +
              '<span class="badge badge-info">' + h.percentage + '%</span>' +
              backlogsBadge +
            '</div>' +
          '</div>' +
          '<div style="display: flex; gap: 16px; font-size: 13px; color: var(--text-muted);">' +
            '<div>Total Marks: <strong>' + h.totalMarks + ' / ' + h.maxMarks + '</strong></div>' +
            '<div>Subjects Evaluated: <strong>' + (h.subjects ? h.subjects.length : 0) + '</strong></div>' +
          '</div>' +
        '</div>';
      });
      html += '</div>';
      cont.innerHTML = html;
    }).catch(function (err) {
      cont.innerHTML = '<div style="text-align:center; padding: 24px; color: var(--danger);">Failed to load academic history.</div>';
    });
  }

  window.printStudentOwnResultCard = function () {
    var ref = CURRENT_USER ? (CURRENT_USER.prn || CURRENT_USER.studentId || CURRENT_USER.id) : null;
    if (ref) {
      window.openStudentResultCard(ref);
    } else {
      window.print();
    }
  };

  // =========================================================================
  // 2. FACULTY VIEW LOGIC (Module 2: Complete 4 Assessments Entry)
  // =========================================================================
  function loadFacultyMarksSheet() {
    var courseSelect = document.getElementById("facultyResultCourseSelect");
    var divSelect = document.getElementById("facultyResultDivisionSelect");
    var assessSelect = document.getElementById("facultyResultAssessmentType");
    var searchInput = document.getElementById("facultyRosterSearch");
    var tbody = document.getElementById("facultyMarksTableBody");
    var titleEl = document.getElementById("facultyMarksSheetTitle");
    var rosterBadge = document.getElementById("facultyMarksRosterBadge");
    if (!tbody) return;

    var coursesList = [];

    function updateDivisions() {
      if (!divSelect || !courseSelect) return;
      var selectedCode = courseSelect.value;
      var matchedCourse = coursesList.find(function (c) { return c.code === selectedCode; });
      var divs = (matchedCourse && matchedCourse.assignedDivisions && matchedCourse.assignedDivisions.length)
        ? matchedCourse.assignedDivisions
        : ["A"];
      divSelect.innerHTML = divs.map(function (d) {
        return '<option value="' + escapeHtml(d) + '">Division ' + escapeHtml(d) + '</option>';
      }).join("");
    }

    api("/api/courses").then(function (res) {
      coursesList = res.data || [];
      if (courseSelect && coursesList.length) {
        courseSelect.innerHTML = coursesList.map(function (c) {
          return '<option value="' + escapeHtml(c.code) + '">' + escapeHtml(c.code + ' - ' + c.title) + '</option>';
        }).join("");
      }
      updateDivisions();
      renderRoster();
    }).catch(function () {
      renderRoster();
    });

    if (courseSelect) courseSelect.addEventListener("change", function () {
      updateDivisions();
      renderRoster();
    });
    if (divSelect) divSelect.addEventListener("change", renderRoster);
    if (assessSelect) assessSelect.addEventListener("change", renderRoster);
    if (searchInput) searchInput.addEventListener("input", debounce(filterRosterRows, 250));

    function filterRosterRows() {
      var q = searchInput ? searchInput.value.trim().toLowerCase() : "";
      tbody.querySelectorAll("tr[data-student-id]").forEach(function (tr) {
        var text = tr.textContent.toLowerCase();
        tr.style.display = (!q || text.indexOf(q) !== -1) ? "" : "none";
      });
    }

    function renderRoster() {
      var courseCode = courseSelect ? courseSelect.value : "";
      var division = divSelect ? divSelect.value : "A";
      if (!courseCode) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:20px; color:var(--text-muted);">Please select a course.</td></tr>';
        return;
      }

      if (titleEl) {
        titleEl.textContent = "Continuous Assessment & Exam Sheet (" + courseCode + " - Div " + division + ")";
      }
      if (rosterBadge) rosterBadge.textContent = "--";

      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading student marks roster...</td></tr>';

      Promise.all([
        api("/api/attendance/roll-call?courseCode=" + encodeURIComponent(courseCode) + "&division=" + encodeURIComponent(division)),
        api("/api/results?courseCode=" + encodeURIComponent(courseCode) + "&division=" + encodeURIComponent(division))
      ]).then(function (responses) {
        var roster = responses[0].data && responses[0].data.roster ? responses[0].data.roster : [];
        var results = responses[1].data || [];
        var resultMap = {};
        results.forEach(function (r) {
          resultMap[r.studentId] = r;
          if (r.prn) resultMap[r.prn] = r;
        });

        if (rosterBadge) {
          rosterBadge.textContent = roster.length + (roster.length === 1 ? " Student" : " Students");
        }

        if (!roster.length) {
          tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color:var(--text-muted);">No enrolled students found in course ' + escapeHtml(courseCode) + ' (Div ' + escapeHtml(division) + ').</td></tr>';
          return;
        }

        tbody.innerHTML = roster.map(function (s) {
          var r = resultMap[s.studentId] || resultMap[s.prn] || {};
          var ca1 = r.ca1 !== undefined ? r.ca1 : "";
          var ca2 = r.ca2 !== undefined ? r.ca2 : "";
          var mid = r.midSem !== undefined ? r.midSem : "";
          var end = r.endSem !== undefined ? r.endSem : "";
          var att = r.attendanceStatus || "present";
          var total = r.total !== undefined ? r.total : 0;
          var grade = r.grade || "-";
          var status = r.status || "draft";
          var isLocked = status === "submitted" || status === "under_review" || status === "approved" || status === "published";

          var statusBadge = '<span class="badge badge-secondary">Draft</span>';
          if (status === "submitted") statusBadge = '<span class="badge badge-primary">Submitted</span>';
          else if (status === "under_review") statusBadge = '<span class="badge badge-warning">Under Review</span>';
          else if (status === "approved") statusBadge = '<span class="badge badge-info">Approved</span>';
          else if (status === "published") statusBadge = '<span class="badge badge-success">Published</span>';
          else if (status === "reopened") statusBadge = '<span class="badge badge-danger">Reopened</span>';

          var disabledAttr = (isLocked && getActiveRole() !== "admin") ? " disabled" : "";

          return '<tr data-student-id="' + escapeHtml(s.studentId || s.prn) + '" data-course="' + escapeHtml(courseCode) + '">' +
            '<td><strong>' + escapeHtml(s.rollNumber || s.prn || s.studentId) + '</strong></td>' +
            '<td><span class="stu-name-col">' + escapeHtml(s.name) + '</span></td>' +
            '<td><input type="number" class="form-input mark-ca1" value="' + ca1 + '" min="0" max="20" step="0.5" style="width:75px; padding:4px;" placeholder="Max 20"' + disabledAttr + '></td>' +
            '<td><input type="number" class="form-input mark-ca2" value="' + ca2 + '" min="0" max="20" step="0.5" style="width:75px; padding:4px;" placeholder="Max 20"' + disabledAttr + '></td>' +
            '<td><input type="number" class="form-input mark-mid" value="' + mid + '" min="0" max="30" step="0.5" style="width:75px; padding:4px;" placeholder="Max 30"' + disabledAttr + '></td>' +
            '<td><input type="number" class="form-input mark-end" value="' + end + '" min="0" max="70" step="0.5" style="width:75px; padding:4px;" placeholder="Max 70"' + disabledAttr + '></td>' +
            '<td>' +
              '<select class="form-select mark-att" style="width:auto; padding:4px 6px; font-size:12px;"' + disabledAttr + '>' +
                '<option value="present"' + (att === 'present' ? ' selected' : '') + '>Present</option>' +
                '<option value="absent"' + (att === 'absent' ? ' selected' : '') + '>Absent</option>' +
                '<option value="incomplete"' + (att === 'incomplete' ? ' selected' : '') + '>Incomplete</option>' +
                '<option value="withheld"' + (att === 'withheld' ? ' selected' : '') + '>Withheld</option>' +
              '</select>' +
            '</td>' +
            '<td><strong class="col-total">' + total + '</strong>/100</td>' +
            '<td><span class="badge badge-primary col-grade">' + escapeHtml(grade) + '</span></td>' +
            '<td><span class="col-status-wrap">' + statusBadge + '</span></td>' +
            '<td><button class="btn btn-secondary btn-sm save-single-row-btn" type="button"' + disabledAttr + '>Save</button></td>' +
            '</tr>';
        }).join("");

        wireMarksRecalculation();
      }).catch(function (err) {
        console.error("Error loading marks roster:", err);
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color:var(--danger);">Error loading student marks roster.</td></tr>';
      });
    }

    function wireMarksRecalculation() {
      tbody.querySelectorAll("tr[data-student-id]").forEach(function (row) {
        var ca1Inp = row.querySelector(".mark-ca1");
        var ca2Inp = row.querySelector(".mark-ca2");
        var midInp = row.querySelector(".mark-mid");
        var endInp = row.querySelector(".mark-end");
        var totalEl = row.querySelector(".col-total");
        var gradeEl = row.querySelector(".col-grade");
        var saveBtn = row.querySelector(".save-single-row-btn");

        function recalculate() {
          var c1 = parseFloat(ca1Inp.value) || 0;
          var c2 = parseFloat(ca2Inp.value) || 0;
          var m = parseFloat(midInp.value) || 0;
          var e = parseFloat(endInp.value) || 0;

          // Institutional formula: CA avg + MidSem + EndSem or standard combination
          var internal = Math.round(((c1 + c2) / 40.0 * 15.0) + (m / 30.0 * 15.0));
          var total = Math.round(internal + e);
          if (totalEl) totalEl.textContent = String(total);
          var pct = total;
          var g = pct >= 90 ? "A+" : (pct >= 80 ? "A" : (pct >= 70 ? "B+" : (pct >= 60 ? "B" : (pct >= 50 ? "C" : (pct >= 40 ? "D" : "F")))));
          if (gradeEl) {
            gradeEl.textContent = g;
            gradeEl.className = "badge badge-" + (pct >= 40 ? "success" : "danger") + " col-grade";
          }
        }

        [ca1Inp, ca2Inp, midInp, endInp].forEach(function (inp) {
          if (inp) inp.addEventListener("input", recalculate);
        });

        if (saveBtn) {
          saveBtn.addEventListener("click", function () {
            var studentId = row.getAttribute("data-student-id");
            var courseCode = row.getAttribute("data-course");
            setButtonLoading(saveBtn, "Saving...");
            api("/api/results/marks", {
              method: "POST",
              body: {
                studentId: studentId,
                courseCode: courseCode,
                ca1Marks: ca1Inp.value !== "" ? parseFloat(ca1Inp.value) : null,
                ca2Marks: ca2Inp.value !== "" ? parseFloat(ca2Inp.value) : null,
                midSemMarks: midInp.value !== "" ? parseFloat(midInp.value) : null,
                endSemMarks: endInp.value !== "" ? parseFloat(endInp.value) : null,
                attendanceStatus: row.querySelector(".mark-att").value,
                action: "save_draft"
              }
            }).then(function (res) {
              highlightRow(row, "update");
              resetButton(saveBtn, "✓ Saved");
              setTimeout(function () { resetButton(saveBtn, "Save"); }, 2000);
              showToast("Draft Saved", "Marks updated for student " + studentId, "success");
            }).catch(function (err) {
              resetButton(saveBtn, "Save");
              showToast("Save Error", err.message || "Failed to save marks.", "error");
            });
          });
        }
      });
    }

    window.saveFacultyAllMarks = function (action) {
      var courseCode = courseSelect ? courseSelect.value : "";
      var division = divSelect ? divSelect.value : "A";
      var rows = tbody.querySelectorAll("tr[data-student-id]");
      if (!rows.length) {
        showToast("No Records", "No students loaded to save.", "warning");
        return;
      }

      var isSubmit = action === "submit";
      var btn = isSubmit ? document.getElementById("btnFacultySubmitMarks") : document.getElementById("btnFacultySaveDraft");
      setButtonLoading(btn, isSubmit ? "Submitting..." : "Saving Drafts...");

      var entries = [];
      rows.forEach(function (row) {
        var stuId = row.getAttribute("data-student-id");
        var ca1 = row.querySelector(".mark-ca1").value;
        var ca2 = row.querySelector(".mark-ca2").value;
        var mid = row.querySelector(".mark-mid").value;
        var end = row.querySelector(".mark-end").value;
        var att = row.querySelector(".mark-att").value;

        entries.push({
          studentId: stuId,
          ca1Marks: ca1 !== "" ? parseFloat(ca1) : null,
          ca2Marks: ca2 !== "" ? parseFloat(ca2) : null,
          midSemMarks: mid !== "" ? parseFloat(mid) : null,
          endSemMarks: end !== "" ? parseFloat(end) : null,
          attendanceStatus: att
        });
      });

      var promises = entries.map(function (item) {
        return api("/api/results/marks", {
          method: "POST",
          body: Object.assign({}, item, { courseCode: courseCode, action: isSubmit ? "submit" : "save_draft" })
        });
      });

      Promise.all(promises).then(function () {
        resetButton(btn, isSubmit ? "🚀 Submit for Review" : "💾 Save Draft");
        showToast(
          isSubmit ? "Marks Submitted" : "Drafts Saved",
          isSubmit ? "All student marks submitted for HOD review. Editing locked." : "Draft marks saved successfully.",
          "success"
        );
        renderRoster();
      }).catch(function (err) {
        resetButton(btn, isSubmit ? "🚀 Submit for Review" : "💾 Save Draft");
        showToast("Operation Failed", err.message || "Could not process marks entries.", "error");
      });
    };
  }

  // =========================================================================
  // 3. ADMIN VIEW LOGIC (Modules 3, 4, 5, 6)
  // =========================================================================
  window.switchAdminTab = function (tab) {
    var secLifecycle = document.getElementById("adminTabSectionLifecycle");
    var secCards = document.getElementById("adminTabSectionCards");
    var secToppers = document.getElementById("adminTabSectionToppers");
    var secAnalytics = document.getElementById("adminTabSectionAnalytics");

    var tabLifecycle = document.getElementById("tabAdminLifecycle");
    var tabCards = document.getElementById("tabAdminCards");
    var tabToppers = document.getElementById("tabAdminToppers");
    var tabAnalytics = document.getElementById("tabAdminAnalytics");

    [secLifecycle, secCards, secToppers, secAnalytics].forEach(function (s) { if (s) s.style.display = "none"; });
    [tabLifecycle, tabCards, tabToppers, tabAnalytics].forEach(function (t) { if (t) t.classList.remove("active"); });

    if (tab === "cards") {
      if (secCards) secCards.style.display = "block";
      if (tabCards) tabCards.classList.add("active");
      loadAdminResultCardsList();
    } else if (tab === "toppers") {
      if (secToppers) secToppers.style.display = "block";
      if (tabToppers) tabToppers.classList.add("active");
      loadToppersMeritList();
    } else if (tab === "analytics") {
      if (secAnalytics) secAnalytics.style.display = "block";
      if (tabAnalytics) tabAnalytics.classList.add("active");
      loadAnalyticsDashboard();
    } else {
      if (secLifecycle) secLifecycle.style.display = "block";
      if (tabLifecycle) tabLifecycle.classList.add("active");
      loadAdminLifecycle();
    }
  };

  function loadAdminLifecycle() {
    var tbody = document.getElementById("adminResultsTableBody");
    var batchTbody = document.getElementById("adminBatchResultsTableBody");
    var countBadge = document.getElementById("adminResultCountBadge");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading student scorecards...</td></tr>';
    if (batchTbody) {
      batchTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading departmental course batches...</td></tr>';
    }

    Promise.all([
      api("/api/results"),
      api("/api/courses")
    ]).then(function (responses) {
      var rows = responses[0].data || [];
      var courses = responses[1].data || [];

      if (countBadge) {
        countBadge.textContent = rows.length + (rows.length === 1 ? " Student Record" : " Student Records");
      }

      var publishedCount = 0;
      var pendingCount = 0;
      var passedCount = 0;

      rows.forEach(function (r) {
        if (r.isPublished) publishedCount++;
        else pendingCount++;
        if (r.isPassed) passedCount++;
      });

      var passRate = rows.length ? Math.round((passedCount / rows.length) * 100) + "%" : "0%";

      var pubEl = document.getElementById("statAdminPublishedResults");
      var pendEl = document.getElementById("statAdminPendingResults");
      var totalEl = document.getElementById("statAdminTotalScorecards");
      var rateEl = document.getElementById("statAdminPassingRate");

      if (pubEl) pubEl.textContent = publishedCount.toLocaleString();
      if (pendEl) pendEl.textContent = pendingCount.toLocaleString();
      if (totalEl) totalEl.textContent = rows.length.toLocaleString();
      if (rateEl) rateEl.textContent = passRate;

      // Render Departmental Course Batches (Module 3 Lifecycle)
      if (batchTbody) {
        if (!courses.length) {
          batchTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color: var(--text-muted);">No academic courses configured.</td></tr>';
        } else {
          batchTbody.innerHTML = courses.map(function (c) {
            var courseRes = rows.filter(function (r) { return r.courseCode === c.code; });
            var totalInCourse = courseRes.length;
            var anyPub = courseRes.some(function (r) { return r.isPublished; });
            var allPub = totalInCourse > 0 && courseRes.every(function (r) { return r.isPublished; });
            var anySubmitted = courseRes.some(function (r) { return r.status === "submitted"; });
            var anyApproved = courseRes.some(function (r) { return r.status === "approved"; });
            var anyUnderReview = courseRes.some(function (r) { return r.status === "under_review"; });

            var statusBadge = '<span class="badge badge-secondary">Draft Marks</span>';
            var actionBtn = '';

            if (totalInCourse === 0) {
              statusBadge = '<span class="badge badge-secondary">Pending Evaluation</span>';
              actionBtn = '<span style="color:var(--text-muted);font-size:12px;">Awaiting Faculty Entry</span>';
            } else if (allPub) {
              statusBadge = '<span class="badge badge-success">Published to Students</span>';
              actionBtn = '<button class="btn btn-danger btn-sm" onclick="openReopenModal(\'' + escapeHtml(c.code) + '\', \'ALL\')">Reopen Results</button>';
            } else if (anyApproved) {
              statusBadge = '<span class="badge badge-info">Approved by Exam Cell</span>';
              actionBtn = '<button class="btn btn-success btn-sm" onclick="transitionBatchStatus(\'' + escapeHtml(c.code) + '\', \'ALL\', \'published\')">Publish to Students</button>';
            } else if (anyUnderReview) {
              statusBadge = '<span class="badge badge-warning">Under Review</span>';
              actionBtn = '<button class="btn btn-primary btn-sm" onclick="transitionBatchStatus(\'' + escapeHtml(c.code) + '\', \'ALL\', \'approved\')">Approve Batch</button>';
            } else if (anySubmitted) {
              statusBadge = '<span class="badge badge-primary">Submitted by Faculty</span>';
              actionBtn = '<button class="btn btn-warning btn-sm" onclick="transitionBatchStatus(\'' + escapeHtml(c.code) + '\', \'ALL\', \'under_review\')">Review Batch</button>';
            } else {
              statusBadge = '<span class="badge badge-secondary">Draft</span>';
              actionBtn = '<button class="btn btn-primary btn-sm" onclick="transitionBatchStatus(\'' + escapeHtml(c.code) + '\', \'ALL\', \'submitted\')">Submit Batch</button>';
            }

            var auditInfo = anyPub
              ? '<span style="font-size:12px; color:var(--success);">Verified & Published</span>'
              : (totalInCourse ? '<span style="font-size:12px; color:var(--text-muted);">' + totalInCourse + ' records pending publish</span>' : '<span style="color:var(--text-muted); font-size:12px;">--</span>');

            return '<tr>' +
              '<td><strong>' + escapeHtml(c.department || 'Computer Engineering') + '</strong></td>' +
              '<td>' + escapeHtml(c.code + ' - ' + c.title) + '</td>' +
              '<td>' + totalInCourse + ' Enrolled</td>' +
              '<td>' + statusBadge + '</td>' +
              '<td>' + auditInfo + '</td>' +
              '<td>' + actionBtn + '</td>' +
              '</tr>';
          }).join("");
        }
      }

      // Render Individual Student Scorecards
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color: var(--text-muted);">No student scorecards recorded yet.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(function (r) {
        var isPass = r.isPassed;
        var pubBadge = r.isPublished
          ? '<span class="badge badge-success">Published</span>'
          : '<span class="badge badge-warning">Draft</span>';

        return '<tr>' +
          '<td><strong>' + escapeHtml(r.studentId || r.prn) + '</strong></td>' +
          '<td>' + escapeHtml(r.studentName || '-') + '</td>' +
          '<td>' + escapeHtml(r.courseCode) + '</td>' +
          '<td>' + (r.ca1 !== undefined ? r.ca1 : '-') + '</td>' +
          '<td>' + (r.ca2 !== undefined ? r.ca2 : '-') + '</td>' +
          '<td>' + (r.midSem !== undefined ? r.midSem : '-') + '</td>' +
          '<td>' + (r.endSem !== undefined ? r.endSem : '-') + '</td>' +
          '<td><strong>' + r.total + '</strong></td>' +
          '<td><span class="badge badge-' + (isPass ? 'success' : 'danger') + '">' + escapeHtml(r.grade) + '</span></td>' +
          '<td>' + pubBadge + '</td>' +
          '<td><button class="btn btn-secondary btn-sm" onclick="openStudentResultCard(\'' + encodeURIComponent(r.studentId || r.prn) + '\')">View Card</button></td>' +
          '</tr>';
      }).join("");

    }).catch(function (err) {
      console.log("Could not load admin lifecycle:", err.message);
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color: var(--danger);">Failed to load student scorecards.</td></tr>';
    });
  }

  window.transitionBatchStatus = function (courseCode, division, targetStatus) {
    if (getActiveRole() !== "admin") {
      showToast("Restricted", "Only Administrators can approve or publish examination results.", "warning");
      return;
    }

    api("/api/results/batch-status", {
      method: "POST",
      body: { courseCode: courseCode, division: division, status: targetStatus }
    }).then(function (res) {
      showToast("Batch Updated", res.message || ("Batch transitioned to " + targetStatus), "success");
      loadAdminLifecycle();
    }).catch(function (err) {
      showToast("Update Failed", err.message || "Failed to update batch status.", "error");
    });
  };

  // Reopen Modal Handlers
  window.openReopenModal = function (courseCode, division) {
    document.getElementById("reopenCourseCode").value = courseCode;
    document.getElementById("reopenDivision").value = division;
    document.getElementById("reopenTargetLabel").value = courseCode + " (Division " + division + ")";
    document.getElementById("reopenReasonInput").value = "";
    openModal("reopenResultsModal");
  };

  window.confirmReopenResults = function () {
    var cCode = document.getElementById("reopenCourseCode").value;
    var div = document.getElementById("reopenDivision").value;
    var reason = document.getElementById("reopenReasonInput").value.trim();
    var btn = document.getElementById("btnConfirmReopen");

    if (!reason) {
      showToast("Reason Required", "Please provide a mandatory official reason for reopening published results.", "warning");
      return;
    }

    setButtonLoading(btn, "Reopening...");
    api("/api/results/batch-status", {
      method: "POST",
      body: { courseCode: cCode, division: div, status: "reopened", reason: reason }
    }).then(function (res) {
      resetButton(btn, "Confirm Reopen with Audit");
      closeModal("reopenResultsModal");
      showToast("Results Reopened", "Results reopened with audit trail: " + reason, "info");
      loadAdminLifecycle();
    }).catch(function (err) {
      resetButton(btn, "Confirm Reopen with Audit");
      showToast("Reopen Failed", err.message || "Could not reopen results.", "error");
    });
  };

  // =========================================================================
  // 4. ADMIN STUDENT RESULT CARDS DIRECTORY (Module 4)
  // =========================================================================
  window.loadAdminResultCardsList = function () {
    var tbody = document.getElementById("adminCardsListBody");
    var search = document.getElementById("adminCardStudentSearch") ? document.getElementById("adminCardStudentSearch").value.trim() : "";
    var dept = document.getElementById("adminCardDeptFilter") ? document.getElementById("adminCardDeptFilter").value : "all";
    var sem = document.getElementById("adminCardSemFilter") ? document.getElementById("adminCardSemFilter").value : "all";
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Searching student result cards...</td></tr>';

    var params = new URLSearchParams();
    if (search) params.set("q", search);
    params.set("role", "student");
    if (dept && dept !== "all") params.set("department", dept);
    if (sem && sem !== "all") params.set("semester", sem);

    api("/api/users?" + params.toString()).then(function (res) {
      var students = res.data || [];
      if (!students.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color: var(--text-muted);">No student records matched your search.</td></tr>';
        return;
      }

      tbody.innerHTML = students.map(function (s) {
        return '<tr>' +
          '<td><strong>' + escapeHtml(s.publicId || s.prn || s.id) + '</strong></td>' +
          '<td>' + escapeHtml(s.rollNumber || '-') + '</td>' +
          '<td>' + escapeHtml(s.name) + '</td>' +
          '<td>' + escapeHtml(s.department || '-') + '</td>' +
          '<td>Semester ' + (s.semester || '-') + '</td>' +
          '<td>Division ' + escapeHtml(s.division || 'A') + '</td>' +
          '<td><span class="badge badge-success">Active Enrolled</span></td>' +
          '<td><button class="btn btn-primary btn-sm" onclick="openStudentResultCard(\'' + encodeURIComponent(s.publicId || s.id) + '\')">📄 View Result Card</button></td>' +
          '</tr>';
      }).join("");
    }).catch(function (err) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color: var(--danger);">Failed to search student result cards.</td></tr>';
    });
  };

  // Open Printable Result Card Modal (Module 4)
  window.openStudentResultCard = function (studentRef) {
    api("/api/results/card/" + encodeURIComponent(studentRef)).then(function (res) {
      var card = res.data || {};
      var stu = card.student || {};
      var sum = card.summary || {};
      var subjects = card.subjects || [];

      var nameEl = document.getElementById("cardStuName");
      var prnEl = document.getElementById("cardStuPRN");
      var rollEl = document.getElementById("cardStuRoll");
      var deptEl = document.getElementById("cardStuDept");
      var semEl = document.getElementById("cardStuSem");
      var divEl = document.getElementById("cardStuDiv");
      var yearEl = document.getElementById("cardStuYear");
      var pubEl = document.getElementById("cardStuPubDate");
      var unpubWarn = document.getElementById("cardUnpublishedWarning");
      var genDateEl = document.getElementById("cardGeneratedDate");

      if (nameEl) nameEl.textContent = stu.name || "-";
      if (prnEl) prnEl.textContent = stu.prn || stu.studentCode || "-";
      if (rollEl) rollEl.textContent = stu.rollNumber || "-";
      if (deptEl) deptEl.textContent = stu.department || "-";
      if (semEl) semEl.textContent = "Semester " + (stu.semester || "-");
      if (divEl) divEl.textContent = "Division " + (stu.division || "A");
      if (yearEl) yearEl.textContent = stu.academicYear || "2025-2026";
      if (pubEl) pubEl.textContent = sum.publishedAt ? new Date(sum.publishedAt).toLocaleDateString() : "Official Publication Pending";
      if (genDateEl) genDateEl.textContent = new Date().toLocaleString();

      if (unpubWarn) {
        unpubWarn.style.display = sum.hasUnpublishedRecords ? "block" : "none";
      }

      var subTbody = document.getElementById("cardSubjectsTableBody");
      if (subTbody) {
        if (!subjects.length) {
          subTbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:16px;">No examination marks recorded for this student.</td></tr>';
        } else {
          subTbody.innerHTML = subjects.map(function (s) {
            return '<tr>' +
              '<td><strong>' + escapeHtml(s.courseCode) + '</strong></td>' +
              '<td class="text-left">' + escapeHtml(s.courseTitle || '-') + '</td>' +
              '<td>' + (s.ca1 !== undefined ? s.ca1 : '-') + '</td>' +
              '<td>' + (s.ca2 !== undefined ? s.ca2 : '-') + '</td>' +
              '<td>' + (s.midSem !== undefined ? s.midSem : '-') + '</td>' +
              '<td>' + (s.endSem !== undefined ? s.endSem : '-') + '</td>' +
              '<td><strong>' + s.total + '</strong></td>' +
              '<td>' + (s.credits || 4) + '</td>' +
              '<td><strong>' + escapeHtml(s.grade) + '</strong></td>' +
              '<td><span class="badge badge-' + (s.isPassed ? 'success' : 'danger') + '">' + (s.isPassed ? 'PASS' : 'FAIL') + '</span></td>' +
              '</tr>';
          }).join("");
        }
      }

      // Populate summary totals
      var totEl = document.getElementById("cardSumTotalMarks");
      var pctEl = document.getElementById("cardSumPercentage");
      var gradeEl = document.getElementById("cardSumGrade");
      var credEl = document.getElementById("cardSumCredits");
      var backEl = document.getElementById("cardSumBacklogs");
      var resEl = document.getElementById("cardSumResultStatus");

      if (totEl) totEl.textContent = sum.aggregateMarks + " / " + sum.maximumMarks;
      if (pctEl) pctEl.textContent = sum.percentage + "%";
      if (gradeEl) gradeEl.textContent = sum.grade || "-";
      if (credEl) credEl.textContent = sum.totalCredits + " / " + sum.maxCredits;
      if (backEl) backEl.textContent = String(sum.backlogsCount || 0);
      if (resEl) {
        resEl.textContent = sum.resultStatus || "PASSED";
        resEl.style.color = sum.backlogsCount > 0 ? "#dc2626" : "#16a34a";
      }

      openModal("resultCardModal");
    }).catch(function (err) {
      showToast("Card Error", err.message || "Failed to load student result card.", "error");
    });
  };

  // =========================================================================
  // 5. TOPPERS & MERIT LIST (Module 5)
  // =========================================================================
  window.loadToppersMeritList = function () {
    var tbody = document.getElementById("toppersTableBody");
    var dept = document.getElementById("toppersDeptSelect") ? document.getElementById("toppersDeptSelect").value : "all";
    var sem = document.getElementById("toppersSemSelect") ? document.getElementById("toppersSemSelect").value : "all";
    var limit = document.getElementById("toppersLimitSelect") ? document.getElementById("toppersLimitSelect").value : "10";
    var search = document.getElementById("toppersSearchInput") ? document.getElementById("toppersSearchInput").value.trim() : "";
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Generating official merit list from published results...</td></tr>';

    var params = new URLSearchParams();
    if (dept && dept !== "all") params.set("department", dept);
    if (sem && sem !== "all") params.set("semester", sem);
    params.set("limit", limit);
    if (search) params.set("q", search);

    api("/api/results/toppers?" + params.toString()).then(function (res) {
      var meritList = res.data || [];
      if (!meritList.length) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--text-muted);">No finalized, published results found matching the selected criteria.</td></tr>';
        return;
      }

      tbody.innerHTML = meritList.map(function (m) {
        var rankBadge = '<strong>#' + m.rank + '</strong>';
        if (m.rank === 1) rankBadge = '<span style="font-size:16px;">🥇</span> <strong>#1 (Gold)</strong>';
        else if (m.rank === 2) rankBadge = '<span style="font-size:16px;">🥈</span> <strong>#2 (Silver)</strong>';
        else if (m.rank === 3) rankBadge = '<span style="font-size:16px;">🥉</span> <strong>#3 (Bronze)</strong>';

        return '<tr>' +
          '<td>' + rankBadge + '</td>' +
          '<td><strong>' + escapeHtml(m.prn || m.studentId) + '</strong></td>' +
          '<td><strong>' + escapeHtml(m.name) + '</strong></td>' +
          '<td>' + escapeHtml(m.department) + '</td>' +
          '<td>Sem ' + (m.semester || '-') + '</td>' +
          '<td><strong>' + m.totalMarks + '</strong> / ' + m.maxMarks + '</td>' +
          '<td><strong style="color:var(--primary); font-size:14px;">' + m.percentage + '%</strong></td>' +
          '<td><span class="badge badge-success">' + escapeHtml(m.grade) + '</span></td>' +
          '<td><span class="badge badge-success">' + escapeHtml(m.status) + '</span></td>' +
          '<td><button class="btn btn-secondary btn-sm" onclick="openStudentResultCard(\'' + encodeURIComponent(m.prn || m.studentId) + '\')">View Card</button></td>' +
          '</tr>';
      }).join("");
    }).catch(function (err) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:24px; color: var(--danger);">Failed to calculate merit list.</td></tr>';
    });
  };

  // =========================================================================
  // 6. EXAMINATION ANALYTICS (Module 6)
  // =========================================================================
  window.loadAnalyticsDashboard = function () {
    var dept = document.getElementById("analyticsDeptSelect") ? document.getElementById("analyticsDeptSelect").value : "all";
    var sem = document.getElementById("analyticsSemSelect") ? document.getElementById("analyticsSemSelect").value : "all";

    var params = new URLSearchParams();
    if (dept && dept !== "all") params.set("department", dept);
    if (sem && sem !== "all") params.set("semester", sem);

    api("/api/results/analytics?" + params.toString()).then(function (res) {
      var d = res.data || {};
      var passPctEl = document.getElementById("anaPassPercentage");
      var passDescEl = document.getElementById("anaPassDesc");
      var passedEl = document.getElementById("anaPassedCount");
      var failedEl = document.getElementById("anaFailedCount");
      var avgEl = document.getElementById("anaAverageScore");
      var rangeEl = document.getElementById("anaScoreRange");

      var totalRecEl = document.getElementById("anaTotalRecords");
      var pubRecEl = document.getElementById("anaPublishedRecords");
      var unpubRecEl = document.getElementById("anaUnpublishedRecords");
      var absentRecEl = document.getElementById("anaAbsentRecords");
      var withheldRecEl = document.getElementById("anaWithheldRecords");

      if (passPctEl) passPctEl.textContent = d.passPercentage + "%";
      if (passDescEl) passDescEl.textContent = d.passedCount + " passed out of " + d.publishedCount + " published";
      if (passedEl) passedEl.textContent = (d.passedCount || 0).toLocaleString();
      if (failedEl) failedEl.textContent = (d.failedCount || 0).toLocaleString();
      if (avgEl) avgEl.textContent = (d.averageMarks || 0) + " / 100";
      if (rangeEl) rangeEl.textContent = "High: " + d.highestMarks + " • Low: " + d.lowestMarks;

      if (totalRecEl) totalRecEl.textContent = (d.totalEvaluated || 0).toLocaleString();
      if (pubRecEl) pubRecEl.textContent = (d.publishedCount || 0).toLocaleString();
      if (unpubRecEl) unpubRecEl.textContent = (d.unpublishedCount || 0).toLocaleString();
      if (absentRecEl) absentRecEl.textContent = (d.absentCount || 0).toLocaleString();
      if (withheldRecEl) withheldRecEl.textContent = (d.withheldCount || 0).toLocaleString();

      var gradeCont = document.getElementById("anaGradeDistributionList");
      if (gradeCont && d.gradeDistribution) {
        var gd = d.gradeDistribution;
        var totalPub = d.publishedCount || 1;
        var gHtml = '<div style="display:grid; gap:10px;">';
        Object.keys(gd).forEach(function (gradeKey) {
          var count = gd[gradeKey] || 0;
          var barPct = Math.round((count / totalPub) * 100);
          gHtml += '<div>' +
            '<div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">' +
              '<strong>Grade ' + gradeKey + '</strong>' +
              '<span>' + count + ' students (' + barPct + '%)</span>' +
            '</div>' +
            '<div style="height:8px; background:var(--bg-hover); border-radius:4px; overflow:hidden;">' +
              '<div style="width:' + barPct + '%; height:100%; background:var(--primary); border-radius:4px;"></div>' +
            '</div>' +
          '</div>';
        });
        gHtml += '</div>';
        gradeCont.innerHTML = gHtml;
      }
    }).catch(function (err) {
      console.log("Could not load analytics:", err.message);
    });
  };
}

// ---- Notices module ------------------------------------------------------------------
function initNotices(role) {
  var postBtn = document.getElementById("postNoticeBtn");
  var modal = document.getElementById("newNoticeModal");
  var list = document.getElementById("noticesContainer") || document.querySelector(".item-list");

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

  function loadNotices() {
    if (!list) return;
    list.innerHTML = '<div style="text-align:center; padding:36px; color:var(--text-muted);"><span class="page-spinner"></span> Loading campus notices...</div>';
    api("/api/notices").then(function (res) {
      var notices = (res && res.data ? res.data : []);
      if (!notices.length) {
        renderEmptyState(list, {
          icon: "📢",
          title: "No notices available.",
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
    }).catch(function (err) {
      list.innerHTML = '<div style="text-align:center; padding:36px; color:var(--danger);">' +
        '<div style="font-size:32px; margin-bottom:8px;">⚠️</div>' +
        '<h4 style="margin-bottom:6px;">Failed to load notices</h4>' +
        '<p style="color:var(--text-muted); font-size:13px; margin-bottom:14px;">' + escapeHtml((err && err.message) || "Unable to retrieve notices from server.") + '</p>' +
        '<button class="btn btn-secondary btn-sm" onclick="loadNotices()">🔄 Retry</button>' +
      '</div>';
    });
  }
  window.loadNotices = loadNotices;
  if (list) loadNotices();
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

    targetBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color: var(--text-muted);"><span class="page-spinner"></span> Loading study materials...</td></tr>';

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
      targetBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color: var(--danger);">Failed to load study materials.</td></tr>';
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

  var normRole = (role || getActiveRole() || (CURRENT_USER && CURRENT_USER.role) || sessionStorage.getItem("campus_user_role") || "").toLowerCase().trim();
  if (normRole !== "admin" && normRole !== "administrator") {
    if (addBtn) addBtn.remove();
    if (modal) modal.remove();
    return;
  }

  // Setup initial toggle state
  window.toggleMemberTypeFields();

  // Dynamically load directory filters and department options from /api/users/filters
  api("/api/users/filters").then(function (res) {
    var filterData = res.data || res;
    var depts = filterData.departments || [];
    var stats = filterData.stats || {};
    var deptSelect = document.getElementById("newMemberDept");
    var filterDept = document.getElementById("filterDeptSelect");
    if (filterDept && depts.length) {
      filterDept.innerHTML = '<option value="all">All Departments</option>' + depts.map(function (d) {
        return '<option value="' + escapeHtml(d.code || d.name) + '">' + escapeHtml(d.name) + '</option>';
      }).join('');
    }
    if (deptSelect && depts.length) {
      var currentVal = deptSelect.value;
      deptSelect.innerHTML = depts.map(function (d) {
        return '<option value="' + escapeHtml(d.name) + '">' + escapeHtml(d.name) + '</option>';
      }).join('');
      if (currentVal && Array.from(deptSelect.options).some(function (opt) { return opt.value === currentVal; })) {
        deptSelect.value = currentVal;
      }
    }
    var statStudents = document.getElementById("statTotalStudents");
    var statFaculty = document.getElementById("statTotalFaculty");
    var statDepts = document.getElementById("statTotalDepts");
    if (statStudents && stats.totalStudents !== undefined) statStudents.textContent = stats.totalStudents.toLocaleString();
    if (statFaculty && stats.totalFaculty !== undefined) statFaculty.textContent = stats.totalFaculty.toLocaleString();
    if (statDepts && stats.totalDepartments !== undefined) statDepts.textContent = stats.totalDepartments.toLocaleString();
  }).catch(function () {
    // Fallback to /api/departments if filters endpoint is unavailable
    api("/api/departments").then(function (res) {
      var depts = res.data || [];
      var deptSelect = document.getElementById("newMemberDept");
      var filterDept = document.getElementById("filterDeptSelect");
      if (filterDept && depts.length) {
        filterDept.innerHTML = '<option value="all">All Departments</option>' + depts.map(function (d) {
          return '<option value="' + escapeHtml(d.code || d.name) + '">' + escapeHtml(d.name) + '</option>';
        }).join('');
      }
      if (deptSelect && depts.length) {
        deptSelect.innerHTML = depts.map(function (d) {
          return '<option value="' + escapeHtml(d.name) + '">' + escapeHtml(d.name) + '</option>';
        }).join('');
      }
    }).catch(function () {});
  });

  var globalSearch = document.getElementById("globalSearchInput");
  if (globalSearch) {
    globalSearch.addEventListener("input", debounce(function () {
      window.applyUserDirectoryFilters();
    }, 350));
  }
  ["filterRoleSelect", "filterDeptSelect", "filterSemesterSelect", "filterDivisionSelect", "filterStatusSelect"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("change", window.applyUserDirectoryFilters);
  });

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

var _userDirState = {
  page: 1,
  limit: 20,
  q: "",
  role: "all",
  department: "all",
  semester: "",
  division: "",
  status: "",
  sortBy: "name",
  sortOrder: "asc"
};

function fetchUsersFromAPI(role) {
  var tbody = document.getElementById("usersTableBody");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:28px; color: var(--text-muted);"><span class="page-spinner"></span> Loading directory records...</td></tr>';

  var params = new URLSearchParams();
  if (_userDirState.q) params.set("q", _userDirState.q);
  if (_userDirState.role && _userDirState.role !== "all") params.set("role", _userDirState.role);
  if (_userDirState.department && _userDirState.department !== "all") params.set("department", _userDirState.department);
  if (_userDirState.semester) params.set("semester", _userDirState.semester);
  if (_userDirState.division) params.set("division", _userDirState.division);
  if (_userDirState.status) params.set("status", _userDirState.status);
  params.set("sort_by", _userDirState.sortBy);
  params.set("sort_order", _userDirState.sortOrder);
  params.set("page", _userDirState.page);
  params.set("limit", _userDirState.limit);

  api("/api/users?" + params.toString()).then(function (res) {
    var items = res.data || [];
    var pagination = res.pagination || { total: 0, page: 1, totalPages: 1 };
    var stats = res.stats || {};

    var statStudents = document.getElementById("statTotalStudents");
    var statFaculty = document.getElementById("statTotalFaculty");
    var statDepts = document.getElementById("statTotalDepts");
    var userCountLabel = document.getElementById("userDirectoryCountLabel");
    var pageInfo = document.getElementById("userPaginationInfo");
    var pageBadge = document.getElementById("userCurrentPageBadge");
    var prevBtn = document.getElementById("userPrevPageBtn");
    var nextBtn = document.getElementById("userNextPageBtn");

    if (statStudents && stats.totalStudents !== undefined) statStudents.textContent = stats.totalStudents.toLocaleString();
    if (statFaculty && stats.totalFaculty !== undefined) statFaculty.textContent = stats.totalFaculty.toLocaleString();
    if (statDepts && stats.totalDepartments !== undefined) statDepts.textContent = stats.totalDepartments.toLocaleString();
    if (userCountLabel) {
      userCountLabel.textContent = "Showing " + items.length + " of " + pagination.total + " registered members";
    }
    if (pageInfo) {
      pageInfo.textContent = "Page " + pagination.page + " of " + Math.max(1, pagination.totalPages) + " (" + pagination.total + " total records)";
    }
    if (pageBadge) pageBadge.textContent = String(pagination.page);
    if (prevBtn) prevBtn.disabled = pagination.page <= 1;
    if (nextBtn) nextBtn.disabled = pagination.page >= pagination.totalPages;

    if (!items.length) {
      renderEmptyState(tbody, {
        icon: "👥",
        title: "No Directory Records Found",
        message: "No registered members matched your search and filter criteria.",
        actionText: (role === "admin" || getActiveRole() === "admin") ? "Enroll New Member" : null,
        onAction: function () { openModal("addUserModal"); },
        colSpan: 7
      });
      return;
    }

    var html = items.map(function (m) {
      var roleBadge = '<span class="badge badge-primary">Student</span>';
      if (m.role === 'admin') roleBadge = '<span class="badge badge-purple">Admin</span>';
      else if (m.role === 'faculty') roleBadge = m.isHod ? '<span class="badge badge-warning">Faculty (HOD)</span>' : '<span class="badge badge-success">Faculty</span>';

      var classBadge = '-';
      if (m.role === 'student') {
        classBadge = '<span class="badge badge-secondary">' + escapeHtml(m.year || '-') + ' • Sem ' + (m.semester || '-') + ' • Div ' + escapeHtml(m.division || 'A') + '</span>';
      } else if (m.role === 'faculty') {
        classBadge = '<span class="badge badge-secondary">' + escapeHtml(m.designation || 'Faculty') + '</span>';
      } else if (m.role === 'admin') {
        classBadge = '<span class="badge badge-secondary">System Administrator</span>';
      }

      var statusBadge = m.isActive
        ? '<span class="badge badge-success">Active</span>'
        : '<span class="badge badge-danger">Inactive</span>';

      var actionsHtml = '<button class="btn btn-secondary btn-sm" onclick="viewDirectoryMember(\'' + m.role + '\', \'' + encodeURIComponent(m.id) + '\')">View</button> ';
      if (m.role === 'student') {
        actionsHtml += '<button class="btn btn-secondary btn-sm" onclick="openStudentResultCard(\'' + encodeURIComponent(m.publicId || m.id) + '\')" title="View official student result card">Grade Card</button> ';
      }
      if (m.role !== 'admin') {
        actionsHtml += '<button class="btn btn-danger btn-sm" onclick="deleteDirectoryMember(\'' + m.role + '\', \'' + encodeURIComponent(m.id) + '\', \'' + escapeHtml(m.name).replace(/'/g, "\\'") + '\', this)">Delete</button>';
      }

      return '<tr class="filterable-item" id="member-row-' + escapeHtml(m.id) + '">' +
        '<td><strong class="col-member-id">' + escapeHtml(m.publicId || m.prn || m.id) + '</strong></td>' +
        '<td><span class="col-member-name">' + escapeHtml(m.name) + '</span><div class="col-member-email" style="font-size:12px;color:var(--text-muted);">' + escapeHtml(m.email) + '</div></td>' +
        '<td>' + roleBadge + '</td>' +
        '<td class="col-member-dept">' + escapeHtml(m.department || '-') + '</td>' +
        '<td class="col-member-class">' + classBadge + '</td>' +
        '<td>' + statusBadge + '</td>' +
        '<td style="white-space:nowrap;">' + actionsHtml + '</td>' +
        '</tr>';
    }).join("");

    tbody.innerHTML = html;
  }).catch(function (err) {
    console.log("Could not load users:", err.message);
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:28px; color: var(--danger);">' +
      '<div style="margin-bottom:10px;">⚠️ Failed to load directory records: ' + escapeHtml(err.message || "Request failed") + '</div>' +
      '<button class="btn btn-primary btn-sm" onclick="fetchUsersFromAPI(getActiveRole())">🔄 Retry</button>' +
      '</td></tr>';
  });
}

window.applyUserDirectoryFilters = function () {
  var searchInp = document.getElementById("globalSearchInput");
  var roleSel = document.getElementById("filterRoleSelect");
  var deptSel = document.getElementById("filterDeptSelect");
  var semSel = document.getElementById("filterSemesterSelect");
  var divSel = document.getElementById("filterDivisionSelect");
  var statSel = document.getElementById("filterStatusSelect");
  var sortSel = document.getElementById("userDirectorySortBy");

  if (searchInp) _userDirState.q = searchInp.value.trim();
  if (roleSel) _userDirState.role = roleSel.value;
  if (deptSel) _userDirState.department = deptSel.value;
  if (semSel) _userDirState.semester = semSel.value;
  if (divSel) _userDirState.division = divSel.value;
  if (statSel) _userDirState.status = statSel.value;
  if (sortSel) _userDirState.sortBy = sortSel.value;

  _userDirState.page = 1;
  fetchUsersFromAPI(getActiveRole());
};

window.resetUserDirectoryFilters = function () {
  var searchInp = document.getElementById("globalSearchInput");
  var roleSel = document.getElementById("filterRoleSelect");
  var deptSel = document.getElementById("filterDeptSelect");
  var semSel = document.getElementById("filterSemesterSelect");
  var divSel = document.getElementById("filterDivisionSelect");
  var statSel = document.getElementById("filterStatusSelect");
  var sortSel = document.getElementById("userDirectorySortBy");

  if (searchInp) searchInp.value = "";
  if (roleSel) roleSel.value = "all";
  if (deptSel) deptSel.value = "all";
  if (semSel) semSel.value = "";
  if (divSel) divSel.value = "";
  if (statSel) statSel.value = "";
  if (sortSel) sortSel.value = "name";

  _userDirState = {
    page: 1,
    limit: 20,
    q: "",
    role: "all",
    department: "all",
    semester: "",
    division: "",
    status: "",
    sortBy: "name",
    sortOrder: "asc"
  };
  fetchUsersFromAPI(getActiveRole());
};

window.changeUserDirectoryPage = function (delta) {
  _userDirState.page = Math.max(1, _userDirState.page + delta);
  fetchUsersFromAPI(getActiveRole());
};

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
  var endpoint = (type === "faculty") ? "/api/faculty/" : ((type === "admin") ? "/api/users/" : "/api/students/");
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

    } else if (type === "admin") {
      var adminDetails = [
        ["Full Name", d.name || d.full_name],
        ["Email / Login ID", d.email],
        ["Phone Number", d.phone || "Not provided"],
        ["Role", "System Administrator"],
        ["Public ID", d.publicId || ("ADM" + String(d.id).padStart(6, "0"))],
        ["Department", "Administration"],
        ["Status", d.isActive ? "Active" : "Inactive"]
      ];
      html = '<div style="margin-bottom:12px;padding:10px;background:var(--bg-subtle);border-radius:var(--radius-sm);border:1px solid var(--border);">' +
        '<div style="font-size:12px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:4px;">🏛️ Administrator Profile</div>' +
        '<div style="font-size:13px;color:var(--text-muted);">' + escapeHtml(d.name || d.full_name) + ' (System Administrator)</div>' +
      '</div>';
      html += adminDetails.map(function (x) {
        return '<div style="display:flex;justify-content:space-between;gap:20px;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;">' +
          '<strong style="color:var(--text-main);">' + escapeHtml(x[0]) + '</strong>' +
          '<span style="color:var(--text-muted);text-align:right;">' + escapeHtml(x[1]) + '</span>' +
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
  var grid = document.getElementById("eventsContainer") || document.querySelector(".grid-3");
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

  function loadEvents() {
    if (!grid) return;
    grid.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding:36px; color:var(--text-muted);"><span class="page-spinner"></span> Loading campus events...</div>';
    api("/api/events").then(function (res) {
      var events = (res && res.data ? res.data : []);
      if (!events.length) {
        renderEmptyState(grid, {
          icon: "🎉",
          title: "No events available.",
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
    }).catch(function (err) {
      grid.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding:36px; color:var(--danger);">' +
        '<div style="font-size:32px; margin-bottom:8px;">⚠️</div>' +
        '<h4 style="margin-bottom:6px;">Failed to load events</h4>' +
        '<p style="color:var(--text-muted); font-size:13px; margin-bottom:14px;">' + escapeHtml((err && err.message) || "Unable to retrieve events from server.") + '</p>' +
        '<button class="btn btn-secondary btn-sm" onclick="loadEvents()">🔄 Retry</button>' +
      '</div>';
    });
  }
  window.loadEvents = loadEvents;
  if (grid) loadEvents();
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
  if (id === "createAssignmentModal" && role === "student") {
    showToast("Access Restricted", "Only Faculty and Administrators can create assignments.", "warning");
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
  if (id === "assignmentPdfViewerModal" && typeof window.closePdfViewerModal === "function") {
    var el = document.getElementById(id);
    if (el) el.classList.remove("active");
    var iframe = document.getElementById("pdfViewerIframe");
    if (iframe) iframe.src = "about:blank";
    return;
  }
  var el = document.getElementById(id);
  if (el) el.classList.remove("active");
}

document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    var pdfModal = document.getElementById("assignmentPdfViewerModal");
    if (pdfModal && pdfModal.classList.contains("active")) {
      if (typeof window.closePdfViewerModal === "function") {
        window.closePdfViewerModal();
      } else {
        closeModal("assignmentPdfViewerModal");
      }
    }
  }
});

// Global visibility and lifecycle management for optimized background polling
document.addEventListener("visibilitychange", function () {
  if (!document.hidden) {
    if (attendancePollTimer && typeof window.renderStudentAttendance === "function") {
      window.renderStudentAttendance();
    }
    if (assignmentsPollTimer && typeof window.loadStudentAssignments === "function") {
      window.loadStudentAssignments();
    }
  }
});

window.addEventListener("beforeunload", function () {
  if (attendancePollTimer) {
    clearInterval(attendancePollTimer);
    attendancePollTimer = null;
  }
  if (assignmentsPollTimer) {
    clearInterval(assignmentsPollTimer);
    assignmentsPollTimer = null;
  }
});

