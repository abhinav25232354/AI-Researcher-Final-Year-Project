// static/app.js
document.addEventListener("htmx:beforeRequest", (e) => {
  // Add a spinner class on the triggering button
  if (e.detail.elt.classList.contains("loading")) return;
  e.detail.elt.classList.add("loading");
});
document.addEventListener("htmx:afterRequest", (e) => {
  e.detail.elt.classList.remove("loading");
});
