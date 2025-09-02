// Minimal JS for live admin view
(function () {
  const liveListEl = document.getElementById("liveList");
  const sectionTabs = document.getElementById("sectionTabs");
  if (!liveListEl || !sectionTabs) return;

  let currentSection = "CSE-A";

  function renderList(section, payload) {
    liveListEl.innerHTML = "";
    if (!payload.active) {
      const el = document.createElement("div");
      el.className = "text-muted";
      el.textContent = "No active session. Start a session to see live attendance.";
      liveListEl.appendChild(el);
      return;
    }
    const students = payload.students || [];
    if (!students.length) {
      const el = document.createElement("div");
      el.className = "text-muted";
      el.textContent = "No students found in this section.";
      liveListEl.appendChild(el);
      return;
    }

    students.forEach(s => {
      const row = document.createElement("div");
      row.className = "list-item";

      const meta = document.createElement("div");
      meta.className = "meta";

      const roll = document.createElement("span");
      roll.className = "roll";
      roll.textContent = s.roll_no;

      const name = document.createElement("span");
      name.className = "name text-muted";
      name.textContent = s.name;

      meta.appendChild(roll);
      meta.appendChild(name);

      const badge = document.createElement("span");
      badge.className = "badge rounded-pill " + (s.present ? "badge-present" : "badge-absent");
      badge.textContent = s.present ? "Present" : "Absent";

      row.appendChild(meta);
      row.appendChild(badge);
      liveListEl.appendChild(row);
    });
  }

  async function fetchLive() {
    try {
      const res = await fetch(`/api/live_attendance?section=${encodeURIComponent(currentSection)}`);
      const data = await res.json();
      renderList(currentSection, data);
    } catch (e) {
      liveListEl.innerHTML = `<div class="text-danger">Failed to load live data.</div>`;
    }
  }

  // Tab behavior
  sectionTabs.querySelectorAll(".nav-link").forEach(btn => {
    btn.addEventListener("click", (e) => {
      sectionTabs.querySelectorAll(".nav-link").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      currentSection = e.target.getAttribute("data-section");
      fetchLive();
    });
  });

  // Initial + interval refresh
  fetchLive();
  setInterval(fetchLive, 5000);
})();
