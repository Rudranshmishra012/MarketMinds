/* =========================================================
   MarketMinds - Client-side JS
   Handles nav toggle, form validation hints, and Chart.js renders.
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
  // ---- Mobile nav toggle ----
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
  }

  // ---- Auto-dismiss flash messages ----
  document.querySelectorAll(".alert").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.5s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 500);
    }, 6000);
  });

  // ---- Simple client-side quantity validation on dashboard ----
  const dashboardForm = document.querySelector("#farmerForm");
  if (dashboardForm) {
    dashboardForm.addEventListener("submit", function (e) {
      const qty = dashboardForm.querySelector("#quantity");
      if (qty && (isNaN(qty.value) || Number(qty.value) <= 0)) {
        e.preventDefault();
        alert("Please enter a valid quantity greater than 0.");
        qty.focus();
      }
    });
  }
});

/* ---------------------------------------------------------
   Chart renderers - called from templates with inline data
   --------------------------------------------------------- */

function renderPriceTrendChart(canvasId, labels, historicalPrices, predictedLabel, predictedPrice) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const data = {
    labels: [...labels, predictedLabel],
    datasets: [
      {
        label: "Historical Price (₹/quintal)",
        data: [...historicalPrices, null],
        borderColor: "#1f7a4d",
        backgroundColor: "rgba(31,122,77,0.12)",
        tension: 0.3,
        fill: true,
      },
      {
        label: "Predicted Price",
        data: [...historicalPrices.map(() => null), predictedPrice],
        borderColor: "#ffb703",
        backgroundColor: "#ffb703",
        pointRadius: 6,
        showLine: false,
      },
    ],
  };

  new Chart(ctx, {
    type: "line",
    data: data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { beginAtZero: false, ticks: { callback: (v) => "₹" + v } },
      },
    },
  });
}

function renderMarketComparisonChart(canvasId, marketNames, profits, currentPrices, predictedPrices) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: marketNames,
      datasets: [
        {
          label: "Expected Net Profit (₹)",
          data: profits,
          backgroundColor: "#1f7a4d",
          borderRadius: 6,
        },
        {
          label: "Current Price (₹/quintal)",
          data: currentPrices,
          backgroundColor: "#a8d5bd",
          borderRadius: 6,
        },
        {
          label: "Predicted Price (₹/quintal)",
          data: predictedPrices,
          backgroundColor: "#ffb703",
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderReliabilityGauge(canvasId, score) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Reliability", "Remaining"],
      datasets: [{
        data: [score, 100 - score],
        backgroundColor: ["#1f7a4d", "#eef3ef"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}
