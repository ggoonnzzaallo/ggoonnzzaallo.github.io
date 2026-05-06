(function () {
  var STORAGE_KEY = "portfolio-theme";

  function storedPreference() {
    var v = localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : null;
  }

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function effectiveTheme() {
    return storedPreference() || systemTheme();
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === "dark" ? "dark" : "light";
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      var isDark = theme === "dark";
      btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
      btn.setAttribute("aria-pressed", String(isDark));
      btn.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");
      btn.innerHTML = isDark ? sunSvg : moonSvg;
    }
  }

  applyTheme(effectiveTheme());

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function () {
      if (!storedPreference()) applyTheme(systemTheme());
    });

  function toggleTheme() {
    var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  var moonSvg =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.6 2.618 5.377 5.377 0 0 1-3.616-1.374 5.366 5.366 0 0 1-1.971-3.442 5.363 5.363 0 0 1 .783-3.77A9.05 9.05 0 0 0 12 3m0-2c-.156 0-.312.002-.466.014a11 11 0 1 0 11.466 11.466A11.012 11.012 0 0 0 12 1z"/></svg>';
  var sunSvg =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 1 1 0-6 3 3 0 0 1 0 6m0 2a5 5 0 1 0 0-10 5 5 0 0 0 0 10m0 5a1 1 0 0 1-1-1v-2a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1m0-17a1 1 0 0 1-1-1V2a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1m11 9a1 1 0 0 1-1 1h-2a1 1 0 1 1 0-2h2a1 1 0 0 1 1 1M5 12a1 1 0 0 1-1 1H2a1 1 0 1 1 0-2h2a1 1 0 0 1 1 1m13.657 7.657a1 1 0 0 1-1.414 0l-1.414-1.414a1 1 0 0 1 1.414-1.414l1.414 1.414a1 1 0 0 1 0 1.414M8.464 8.464a1 1 0 0 1-1.414 0L5.636 7.05A1 1 0 1 1 7.05 5.636l1.414 1.414a1 1 0 0 1 0 1.414m10.192 0a1 1 0 0 1-1.414-1.414l1.414-1.414a1 1 0 1 1 1.414 1.414l-1.414 1.414zM7.05 18.364a1 1 0 0 1-1.414-1.414l1.414-1.414a1 1 0 1 1 1.414 1.414z"/></svg>';

  function ensureToggle() {
    if (document.getElementById("theme-toggle")) {
      applyTheme(document.documentElement.dataset.theme);
      return;
    }
    var btn = document.createElement("button");
    btn.id = "theme-toggle";
    btn.type = "button";
    btn.className = "theme-toggle";
    btn.innerHTML = document.documentElement.dataset.theme === "dark" ? sunSvg : moonSvg;
    btn.addEventListener("click", toggleTheme);
    document.body.appendChild(btn);
    applyTheme(document.documentElement.dataset.theme);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureToggle);
  } else {
    ensureToggle();
  }
})();
