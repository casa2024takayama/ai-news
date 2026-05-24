(function () {
  const STORAGE_KEY = "ai-news-region";
  const tabs = Array.from(document.querySelectorAll(".tab"));
  const cards = document.querySelectorAll(".card[data-region]");
  const empty = document.getElementById("empty-state");
  const grid = document.getElementById("article-grid");

  function applyFilter(region) {
    let visible = 0;
    cards.forEach((card) => {
      const cardRegion = card.getAttribute("data-region");
      const show = region === "all" || cardRegion === region;
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  }

  function selectTab(tab, scroll) {
    const region = tab.getAttribute("data-region") || "all";
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", active ? "true" : "false");
    });
    applyFilter(region);
    try {
      sessionStorage.setItem(STORAGE_KEY, region);
    } catch (err) {
      /* ignore */
    }
    if (scroll && grid) {
      grid.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => selectTab(tab, true));
  });

  let initial = "all";
  try {
    initial = sessionStorage.getItem(STORAGE_KEY) || "all";
  } catch (err) {
    initial = "all";
  }
  const savedTab = tabs.find((tab) => tab.getAttribute("data-region") === initial) || tabs[0];
  if (savedTab) selectTab(savedTab, false);
})();
