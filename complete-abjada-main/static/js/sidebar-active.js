/**
 * Highlights the matching sidebar link (no server-side Jinja required).
 */
(function () {
  function normPath(p) {
    if (!p) return "/";
    p = p.split("?")[0];
    if (p.length > 1 && p.endsWith("/")) return p.slice(0, -1);
    return p;
  }

  function run() {
    var path = normPath(window.location.pathname);

    document.querySelectorAll(".sidebar-modern-link").forEach(function (a) {
      a.classList.remove("is-active");
      var href = a.getAttribute("href");
      if (!href || href === "#") return;

      var u;
      try {
        u = new URL(href, window.location.origin);
      } catch (e) {
        return;
      }

      var p = normPath(u.pathname);

      if (p === "/category-page" || p === "/product-categories" || p === "/categories") {
        if (path === "/category-page" || path === "/product-categories" || path === "/categories") {
          a.classList.add("is-active");
        }
        return;
      }

      if (p === "/stock") {
        if (path === "/stock") a.classList.add("is-active");
        return;
      }

      if (p === "/reports") {
        if (path === "/reports" || path.indexOf("/reports/") === 0) {
          a.classList.add("is-active");
        }
        return;
      }

      if (p === "/store") {
        if (path === "/store" || path.indexOf("/products/") === 0) {
          a.classList.add("is-active");
        }
        return;
      }

      if (p === "/orders") {
        if (path === "/orders" || path.indexOf("/orders/") === 0) {
          a.classList.add("is-active");
        }
        return;
      }

      if (p === "/transaction-categories") {
        if (path === "/transaction-categories") {
          a.classList.add("is-active");
        }
        return;
      }

      if (p === "/accounts") {
        if (path === "/accounts") a.classList.add("is-active");
        return;
      }

      if (path === p) {
        a.classList.add("is-active");
      }
    });

    document.querySelectorAll(".sidebar-modern-util-link").forEach(function (a) {
      a.classList.remove("is-active");
      var href = a.getAttribute("href");
      if (!href) return;
      try {
        var u = new URL(href, window.location.origin);
        if (path === normPath(u.pathname)) a.classList.add("is-active");
      } catch (e) {}
    });

    // Report submenu links: highlight current (submenu stays visible via CSS)
    var reportSubmenu = document.getElementById("sidebarReportSubmenu");
    if (reportSubmenu) {
      reportSubmenu.setAttribute("aria-hidden", "false");
      reportSubmenu.querySelectorAll(".sidebar-modern-report-submenu-link").forEach(function (a) {
        var href = a.getAttribute("href");
        if (!href) return;
        try {
          var u = new URL(href, window.location.origin);
          var t = normPath(u.pathname);
          var active = path === t || (path === "/reports" && t === "/reports/orders");
          a.classList.toggle("is-active", active);
        } catch (e) {}
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
