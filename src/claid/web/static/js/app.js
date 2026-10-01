/* CLAID - one small progressive enhancement.
   A run takes about half a minute (greedy modularity, betweenness/closeness
   centrality and the Isolation Forest), so the form says so instead of leaving
   the browser looking frozen while the POST is in flight. */
document.addEventListener("DOMContentLoaded", function () {
  var form = document.querySelector("form.run-form");
  if (!form) {
    return;
  }
  var button = form.querySelector("button[type='submit']");
  var status = document.getElementById("run-status");
  form.addEventListener("submit", function () {
    if (button && !button.disabled) {
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.textContent = "Running...";
    }
    if (status) {
      status.classList.add("is-running");
      status.textContent = "Running the four modules. Greedy modularity, the "
        + "Isolation Forest and closeness centrality dominate a run, so this "
        + "takes about half a minute. The progress is printed in the terminal "
        + "that serves the app; the page reloads with the results when the run "
        + "is stored.";
    }
  });
});
