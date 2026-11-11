/* Deneb template gallery: renders every template with vega-embed on the published data.
   No build step. Every path is relative to this page, so it works on GitHub Pages and locally. */
(function () {
  "use strict";

  // Light-to-dark mapping for the validated palette and text/grid tokens used in the specs.
  // Specs are authored in light colours; dark mode swaps them here, once, for every chart.
  var DARK_MAP = {
    "#2a78d6": "#3987e5",
    "#eb6834": "#d95926",
    "#1baf7a": "#199e70",
    "#0b0b0b": "#f0efec",
    "#52514e": "#c3c2b7",
    "#e4e3df": "#3a3a37",
    "#a8a69e": "#6f6e68",
    "#fcfcfb": "#1a1a19",
    "#252423": "#e4e3df",   // direct labels (slope chart)
    "#767676": "#9c9b94",   // subtitles
    "#c8c6c4": "#5b5a56"    // muted bars (ranked bar, below the national value)
  };

  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  var cards = [];
  var lastWidth = 0;

  function isDark() {
    return darkQuery.matches;
  }

  // Deep copy with colour remapping. In dark mode, sequential colour scales are reversed so that
  // higher values stay the most visible against the dark surface.
  function themed(node, dark) {
    if (Array.isArray(node)) {
      return node.map(function (item) { return themed(item, dark); });
    }
    if (node && typeof node === "object") {
      var out = {};
      Object.keys(node).forEach(function (key) {
        out[key] = themed(node[key], dark);
      });
      if (dark && typeof out.scheme === "string") {
        out.reverse = true;
      }
      return out;
    }
    if (typeof node === "string" && dark) {
      var mapped = DARK_MAP[node.toLowerCase()];
      return mapped || node;
    }
    return node;
  }

  // Room a facet panel needs besides its own width: y-axis labels and the gap between panels.
  var PANEL_EXTRA = 55;
  var MIN_PANEL = 100;

  function fitSpec(spec, width) {
    var copy = themed(spec, isDark());
    // Charts sit on the page surface in both schemes, so no white canvas.
    copy.background = "transparent";
    // Small multiples: as many columns as the card holds (up to the spec's own), panels narrowed to fit.
    // The templates keep their fixed panel size for Power BI; only the gallery adapts.
    if (copy.facet && copy.columns && copy.spec && typeof copy.spec.width === "number" && width) {
      var columns = copy.columns;
      while (columns > 1 && Math.floor(width / columns) - PANEL_EXTRA < MIN_PANEL) {
        columns -= 1;
      }
      copy.columns = columns;
      copy.spec.width = Math.min(copy.spec.width, Math.floor(width / columns) - PANEL_EXTRA);
    }
    // Long title or subtitle: wrap to the card width, which Vega does not do on its own
    // (about 8.5 px per character for the 15 px bold title, 6 px for the subtitle).
    var title = copy.title;
    if (title && typeof title === "object" && width) {
      if (typeof title.text === "string") { title.text = wrapLines(title.text, Math.floor(width / 8.5)); }
      if (typeof title.subtitle === "string") { title.subtitle = wrapLines(title.subtitle, Math.floor(width / 6)); }
    }
    return copy;
  }

  // Split text into lines of at most maxChars characters, breaking between words.
  // Returns the text unchanged when it fits on one line.
  function wrapLines(text, maxChars) {
    if (text.length <= maxChars) { return text; }
    var lines = [];
    var line = "";
    text.split(" ").forEach(function (word) {
      if (line && (line + " " + word).length > maxChars) {
        lines.push(line);
        line = word;
      } else {
        line = line ? line + " " + word : word;
      }
    });
    if (line) { lines.push(line); }
    return lines;
  }

  function getText(url) {
    return fetch(url, { cache: "no-cache" }).then(function (response) {
      if (!response.ok) {
        throw new Error(url + " returned " + response.status);
      }
      return response.text();
    });
  }

  function setStatus(card, message) {
    card.status.textContent = message || "";
  }

  function render(card) {
    if (!card.spec) {
      return Promise.resolve();
    }
    if (card.result) {
      card.result.finalize();
      card.result = null;
    }
    card.chart.innerHTML = "";
    return vegaEmbed(card.chart, fitSpec(card.spec, card.chart.clientWidth), {
      actions: false,
      renderer: "svg",
      tooltip: true
    }).then(function (result) {
      card.result = result;
    }).catch(function (err) {
      setStatus(card, "Could not render this chart.");
      console.error(err);
    });
  }

  function renderAll() {
    cards.forEach(function (card) { render(card); });
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for non-secure contexts (for example a LAN address during local testing).
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok ? Promise.resolve() : Promise.reject(new Error("copy command refused"));
  }

  function buildCard(entry) {
    var article = document.createElement("article");
    article.className = "card";
    article.id = entry.id;

    var heading = document.createElement("h2");
    heading.textContent = entry.title;
    var desc = document.createElement("p");
    desc.className = "desc";
    desc.textContent = entry.description;
    var chart = document.createElement("div");
    chart.className = "chart";
    chart.setAttribute("role", "img");
    chart.setAttribute("aria-label", entry.title + ": " + entry.description);

    var actions = document.createElement("div");
    actions.className = "actions";
    var copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn";
    copy.textContent = "Copy template";
    copy.disabled = true;
    var readme = document.createElement("a");
    readme.href = entry.readme;
    readme.textContent = "README";
    readme.className = "btn secondary";
    readme.style.textDecoration = "none";
    var status = document.createElement("span");
    status.className = "status";
    status.setAttribute("role", "status");

    actions.appendChild(copy);
    actions.appendChild(readme);
    actions.appendChild(status);
    article.appendChild(heading);
    article.appendChild(desc);
    article.appendChild(chart);
    article.appendChild(actions);

    var card = { entry: entry, article: article, chart: chart, status: status, spec: null, result: null, template: null };
    cards.push(card);

    copy.addEventListener("click", function () {
      if (!card.template) {
        setStatus(card, "Template not loaded.");
        return;
      }
      copyText(card.template).then(function () {
        setStatus(card, "Copied. Paste it into the Deneb advanced editor.");
      }, function () {
        setStatus(card, "Copy failed. Open the template file and copy it by hand.");
      });
    });

    return { card: card, copy: copy };
  }

  function loadCard(entry, parts) {
    var card = parts.card;
    return Promise.all([getText(entry.spec), getText(entry.template)]).then(function (texts) {
      card.spec = JSON.parse(texts[0]);
      card.template = texts[1];
      parts.copy.disabled = false;
      return render(card);
    }).catch(function (err) {
      setStatus(card, "Could not load this template.");
      console.error(err);
    });
  }

  function init() {
    var gallery = document.getElementById("gallery");
    var notice = document.getElementById("load-error");

    getText("templates.json").then(function (text) {
      var entries = JSON.parse(text);
      var parts = entries.map(function (entry) {
        var built = buildCard(entry);
        gallery.appendChild(built.card.article);
        return built;
      });
      return Promise.all(entries.map(function (entry, i) { return loadCard(entry, parts[i]); }));
    }).catch(function (err) {
      notice.hidden = false;
      notice.textContent = "The gallery could not be loaded. Check that the page is served over HTTP (see README, local preview).";
      console.error(err);
    });

    darkQuery.addEventListener("change", renderAll);
    lastWidth = window.innerWidth;
    var timer = null;
    window.addEventListener("resize", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (Math.abs(window.innerWidth - lastWidth) > 40) {
          lastWidth = window.innerWidth;
          renderAll();
        }
      }, 250);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
