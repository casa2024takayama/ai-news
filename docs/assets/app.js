(function () {
  const tabs = document.querySelectorAll(".tab");
  const cards = document.querySelectorAll(".card[data-region]");
  const empty = document.getElementById("empty-state");

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

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      applyFilter(tab.getAttribute("data-region") || "all");
    });
  });
})();
