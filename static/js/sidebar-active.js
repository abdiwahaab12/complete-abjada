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
    var section = (new URLSearchParams(window.location.search).get("section")) || "";

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
      var linkSec = u.searchParams.get("section") || "";

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
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
