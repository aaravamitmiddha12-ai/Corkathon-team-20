// Picks light or dark before first paint. Order: ?stage (forces dark for the stage demo),
// then the viewer's saved choice from the toggle, then the OS setting.
(function () {
  var KEY = "hc-theme";
  var root = document.documentElement;
  var stage = /[?&]stage\b/.test(location.search);
  var os = window.matchMedia("(prefers-color-scheme: light)");

  function saved() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function apply(theme) {
    root.dataset.theme = theme;
  }

  apply(stage ? "dark" : saved() || (os.matches ? "light" : "dark"));

  os.addEventListener("change", function (e) {
    if (!stage && !saved()) apply(e.matches ? "light" : "dark");
  });

  window.toggleTheme = function () {
    var next = root.dataset.theme === "dark" ? "light" : "dark";
    apply(next);
    if (!stage) {
      try { localStorage.setItem(KEY, next); } catch (e) { /* still works for this page view */ }
    }
  };
})();
