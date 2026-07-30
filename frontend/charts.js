const SVG_NS = "http://www.w3.org/2000/svg";

function formatDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function renderLineChart(container, data, options = {}) {
  const width = options.width || container.clientWidth || 260;
  const height = options.height || 64;
  const color = options.color || "var(--series-1)";

  const points = data.filter((d) => d.value !== null && d.value !== undefined);
  if (points.length === 0) {
    container.innerHTML = '<div class="chart-empty">No data yet</div>';
    return;
  }

  const values = points.map((d) => d.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const pad = (maxV - minV) * 0.15 || 1;
  const yMin = minV - pad;
  const yMax = maxV + pad;

  const n = data.length;
  const xFor = (i) => (n === 1 ? width / 2 : (i / (n - 1)) * (width - 6) + 3);
  const yFor = (v) => height - 4 - ((v - yMin) / (yMax - yMin)) * (height - 8);

  const segments = [];
  let current = [];
  data.forEach((d, i) => {
    if (d.value === null || d.value === undefined) {
      if (current.length) segments.push(current);
      current = [];
      return;
    }
    current.push([xFor(i), yFor(d.value)]);
  });
  if (current.length) segments.push(current);

  const pathD = segments.map((seg) => "M" + seg.map((p) => p.join(",")).join("L")).join(" ");

  container.innerHTML = "";

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", String(height));
  svg.style.display = "block";

  const gridline = document.createElementNS(SVG_NS, "line");
  gridline.setAttribute("x1", "0");
  gridline.setAttribute("x2", String(width));
  gridline.setAttribute("y1", String(height - 2));
  gridline.setAttribute("y2", String(height - 2));
  gridline.setAttribute("stroke", "var(--gridline)");
  gridline.setAttribute("stroke-width", "1");
  svg.appendChild(gridline);

  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", pathD);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", color);
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);

  const crosshair = document.createElementNS(SVG_NS, "line");
  crosshair.setAttribute("y1", "0");
  crosshair.setAttribute("y2", String(height));
  crosshair.setAttribute("stroke", "var(--baseline)");
  crosshair.setAttribute("stroke-width", "1");
  crosshair.style.display = "none";
  svg.appendChild(crosshair);

  const dot = document.createElementNS(SVG_NS, "circle");
  dot.setAttribute("r", "3.5");
  dot.setAttribute("fill", color);
  dot.style.display = "none";
  svg.appendChild(dot);

  const overlay = document.createElementNS(SVG_NS, "rect");
  overlay.setAttribute("x", "0");
  overlay.setAttribute("y", "0");
  overlay.setAttribute("width", String(width));
  overlay.setAttribute("height", String(height));
  overlay.setAttribute("fill", "transparent");
  svg.appendChild(overlay);

  container.appendChild(svg);

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  tooltip.innerHTML = '<div class="tt-date"></div><div class="tt-value"></div>';
  container.appendChild(tooltip);

  function onMove(evt) {
    const rect = svg.getBoundingClientRect();
    const scaleX = width / rect.width;
    const px = (evt.clientX - rect.left) * scaleX;

    let nearestIdx = 0;
    let nearestDist = Infinity;
    data.forEach((d, i) => {
      const dist = Math.abs(xFor(i) - px);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = i;
      }
    });

    const d = data[nearestIdx];
    if (d.value === null || d.value === undefined) {
      onLeave();
      return;
    }

    const x = xFor(nearestIdx);
    const y = yFor(d.value);
    crosshair.setAttribute("x1", String(x));
    crosshair.setAttribute("x2", String(x));
    crosshair.style.display = "";
    dot.setAttribute("cx", String(x));
    dot.setAttribute("cy", String(y));
    dot.style.display = "";

    tooltip.style.display = "block";
    tooltip.style.left = `${x / scaleX}px`;
    tooltip.style.top = `${y}px`;
    tooltip.querySelector(".tt-date").textContent = formatDate(d.date);
    tooltip.querySelector(".tt-value").textContent = d.value;
  }

  function onLeave() {
    crosshair.style.display = "none";
    dot.style.display = "none";
    tooltip.style.display = "none";
  }

  svg.addEventListener("mousemove", onMove);
  svg.addEventListener("mouseleave", onLeave);
}
