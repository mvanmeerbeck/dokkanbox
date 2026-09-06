(function () {
  const IMG = JSON.parse(document.getElementById("gImg").textContent);
  const FONT = JSON.parse(document.getElementById("gFont").textContent);
  const LAY = JSON.parse(document.getElementById("gLay").textContent);
  const ANIM = JSON.parse(document.getElementById("gAnim").textContent);
  const CARDS = JSON.parse(document.getElementById("gCards").textContent);
  const CATS = JSON.parse(document.getElementById("gCats").textContent);
  const THUMB = JSON.parse(document.getElementById("gThumbs").textContent);

  const W = LAY.w, H = LAY.h, N = LAY.nodes, NAT = IMG.native;
  const pc = (v, t) => (v / t * 100) + "%";
  const RARE = ["n", "r", "sr", "ssr", "ur", "lr"];

  /* ---- language: the WHOLE page speaks one language — chrome, card names, category names,
     type codes and their badge image. One base is one language, so the switch only exists
     once a second base is dropped in: LANGS then has two entries and the buttons appear. */
  const LANGS = IMG.langs;                       // ['en'] today, ['en','fr'] once FR names land
  const NOMFB = IMG.nameFallback;                // the language names really exist in
  const CLE_LANG = "dokkan.langue";
  let lang = LANGS[0];                            // English by default
  try { const s = localStorage.getItem(CLE_LANG); if (LANGS.includes(s)) lang = s; } catch (e) {}
  // the game's own type codes, per language — the badge shows them, so the text must match
  const TYPES = { en: ["AGL", "TEQ", "INT", "STR", "PHY"],
                  fr: ["AGI", "TEC", "INT", "PUI", "END"] };
  const types = () => TYPES[lang] || TYPES[NOMFB];
  // names come from the base: French when we have it, English until then — never blank
  const nomC = c => c.name[lang] || c.name[NOMFB];
  const nomCat = id => { const m = CATS[id]; return m ? (m[lang] || m[NOMFB]) : ""; };
  const LOCA = () => IMG.loc[lang] || IMG.loc[LANGS[0]];      // this lang's badges + label

  /* Every word of chrome, per language. Today the page runs in English; the French is kept
     ready so that adding a French base flips the whole page, not only the card names. `allF`
     is the feminine "toutes" French needs and English does not. */
  const I18N = {
    en: { filters: "Filters", clearFilters: "clear filters",
          columns: "Columns · the game shows 5", rarity: "Rarity", type: "Type",
          maxAwk: "Max awakening", category: "Category", collection: "Collection",
          search: "Search", cardNamePH: "card name", language: "Language",
          all: "all", allF: "all", owned: "owned", missing: "missing", allCards: "all cards",
          export: "export", import: "import", clearAll: "clear all",
          cards: "cards", animated: "animated", onScreen: "on screen", builtIn: "built in",
          awakening: "awakening", lv: "Lv", columnsWord: "columns",
          ev: ["none", "Z", "Dokkan", "Extreme Z", "Super Extreme Z"],
          confirmClear: n => "Clear the " + n + " cards in your box?\n" +
            "This cannot be undone — export them first if you want to keep them." },
    fr: { filters: "Filtres", clearFilters: "effacer les filtres",
          columns: "Colonnes · le jeu en met 5", rarity: "Rareté", type: "Type",
          maxAwk: "Éveil maximum", category: "Catégorie", collection: "Collection",
          search: "Chercher", cardNamePH: "nom de la carte", language: "Langue",
          all: "tous", allF: "toutes", owned: "possédées", missing: "manquantes",
          allCards: "toutes les cartes", export: "exporter", import: "importer",
          clearAll: "tout décocher", cards: "cartes", animated: "animées",
          onScreen: "à l'écran", builtIn: "construites en", awakening: "éveil", lv: "Nv",
          columnsWord: "colonnes",
          ev: ["aucun", "Z", "Dokkan", "Z suprême", "Z suprême super"],
          confirmClear: n => "Décocher les " + n + " cartes de votre box ?\n" +
            "C'est sans retour : exportez-les d'abord si vous voulez pouvoir y revenir." }
  };
  const t = () => I18N[lang] || I18N[NOMFB];
  /* the static chrome carries its key in data-i18n / data-i18n-ph; applied on load and on
     every language switch, so one table drives markup and script alike */
  function appliquerTextes() {
    const T = t();
    document.querySelectorAll("[data-i18n]").forEach(e => { e.textContent = T[e.dataset.i18n]; });
    document.querySelectorAll("[data-i18n-ph]").forEach(e => {
      e.setAttribute("placeholder", T[e.dataset.i18nPh]); });
  }
  const back = document.getElementById("back"), front = document.getElementById("front");
  const cAur = document.getElementById("auras"), cPul = document.getElementById("pulses");
  /* Each card carries what it should show, so there is nothing to switch: the album is the
     honest view, and the stress test lived long enough to prove the cost is flat. */
  const state = { cols: 5, rare: -1, type: -1, own: "tous", nom: "", ev: -1, cat: -1 };

  /* ---- what the player owns ------------------------------------------------
     Kept in the browser, exported on demand: no account to create before knowing whether
     the album is worth the trouble. One entry per evolution chain, keyed by the id the
     grid draws — awakening consumes a card, so a chain is owned or not, never twice. */
  const CLE = "dokkan.possede";
  let possede = new Set();
  try { possede = new Set(JSON.parse(localStorage.getItem(CLE) || "[]")); } catch (e) {}
  let sauveEnAttente = 0;
  function sauver() {
    clearTimeout(sauveEnAttente);
    sauveEnAttente = setTimeout(() => {
      try { localStorage.setItem(CLE, JSON.stringify([...possede])); } catch (e) {}
    }, 400);                       /* painting a row must not write a thousand times */
  }
  let live = [];          // {kind, col, row} for every animated tile

  function place(el, node, nat) {
    const n = N[node], s = n.scale || 1, dw = nat[0] * s, dh = nat[1] * s;
    el.style.left = pc(n.x + n.w / 2 - dw / 2, W);
    el.style.top = pc(H - (n.y + n.h / 2) - dh / 2, H);
    el.style.width = pc(dw, W); el.style.height = pc(dh, H);
    el.style.zIndex = n.z;
  }
  /* `loading` has to be set BEFORE `src`: assigning src starts the fetch, and an
     attribute added afterwards arrives too late to defer anything. */
  function sprite(cell, node, src, nat, lazy) {
    const e = document.createElement("img");
    /* a card thumbnail can wait; the shared chrome and the timelines cannot */
    if (lazy) { e.loading = "lazy"; e.fetchPriority = "low"; }
    e.src = src; e.alt = ""; place(e, node, nat); cell.appendChild(e); return e;
  }
  function text(cell, node, str) {
    const n = N[node], sc = n.scale || 1, kern = n.kerning || 0, lh = FONT.lineHeight;
    let lw = 0;
    for (const ch of str) { const g = FONT.glyphs[ch.codePointAt(0)]; if (g) lw += g[6] + kern; }
    const ay = 0.5 + sc * (n.h - lh) / (2 * lh);
    const box = document.createElement("b");
    box.className = "txt";
    box.style.left = pc((n.x + n.w / 2) - lw * sc / 2, W);
    box.style.top = pc(H - ((n.y + 3 + n.h / 2) - lh * ay * sc + lh * sc), H);
    box.style.width = pc(lw * sc, W); box.style.height = pc(lh * sc, H);
    box.style.zIndex = n.z;
    let pen = 0;
    for (const ch of str) {
      const g = FONT.glyphs[ch.codePointAt(0)];
      if (!g) continue;
      if (g[2] && g[3]) {
        const i = document.createElement("i");
        i.className = "g";
        i.style.left = (pen + g[4]) / lw * 100 + "%";
        i.style.top = g[5] / lh * 100 + "%";
        i.style.width = g[2] / lw * 100 + "%";
        i.style.height = g[3] / lh * 100 + "%";
        i.style.backgroundSize = (FONT.atlasW / g[2] * 100) + "% " + (FONT.atlasH / g[3] * 100) + "%";
        i.style.backgroundPosition = (g[0] / (FONT.atlasW - g[2]) * 100) + "% " +
                                     (g[1] / (FONT.atlasH - g[3]) * 100) + "%";
        box.appendChild(i);
      }
      pen += g[6] + kern;
    }
    box.setAttribute("role", "img"); box.setAttribute("aria-label", str);
    cell.appendChild(box);
  }

  function paint() {
    const t0 = performance.now();
    back.style.setProperty("--cols", state.cols);
    front.style.setProperty("--cols", state.cols);
    const q = state.nom.trim().toLowerCase();
    const shown = CARDS.filter(c =>
      (state.rare < 0 || c.rarity === state.rare) &&
      (state.type < 0 || c.element % 10 === state.type) &&
      (state.ev < 0 || c.ev === state.ev) &&
      (state.cat < 0 || c.cats.includes(state.cat)) &&
      (state.own === "tous" || (state.own === "oui") === possede.has(c.top)) &&
      (!q || nomC(c).toLowerCase().includes(q)));
    back.textContent = ""; front.textContent = "";
    drawnEl = null;              /* the stat line is rebuilt below; the old node is gone */
    const fb = document.createDocumentFragment(), ff = document.createDocumentFragment();
    live = [];
    shown.forEach((card, idx) => {
      const type = card.element % 10, rare = Math.min(card.rarity, 3);
      const a = possede.has(card.top);
      const b = document.createElement("div");
      b.className = a ? "cell" : "cell non";
      b.dataset.id = card.top; b.dataset.i = idx;
      /* the tooltip has to live on the plane that receives the pointer: #front is
         pointer-events:none, so a title there is never shown */
      b.title = nomC(card) + " · " + RARE[card.rarity].toUpperCase() + " · " + t().lv + " " + card.lv +
                " · " + card.top;
      sprite(b, "img_bg", IMG.bg[type + "_" + rare], NAT.bg);
      fb.appendChild(b);

      const f = document.createElement("div");
      /* Each card shows what it is, not what the demonstration wants: the level turns
         yellow at the cap, the big star marks an awakened form, the Extreme Z aura belongs
         to the cards that have one, and the LR lightning to the LR alone. */
      f.className = "cell max" + (a ? "" : " non");
      sprite(f, "image_thumb", THUMB[card.id], [250, 250], true);
      sprite(f, "image_chara_bottom_base", IMG.band[String(type)], NAT.band);
      sprite(f, "image_rare_ssr", IMG.rare[RARE[card.rarity]], NAT.rare);
      /* Only the big star. In the game's own box the awakened tile carries that one and
         nothing else; the row of small stars beside it says the same thing twice. */
      if (card.awk) sprite(f, "image_star_evo_big", IMG.star["5"], NAT.star["5"]);
      sprite(f, "image_label_lv", LOCA().label, LOCA().natLabel);
      text(f, "font_num", String(card.lv));
      sprite(f, "image_icon_type", LOCA().type[String(card.element)], LOCA().natType);
      ff.appendChild(f);

      const col = idx % state.cols, row = (idx / state.cols) | 0;
      /* the game plays fla_bg_effect on LR alone; the demonstration puts it everywhere,
         so the three timelines can be judged on the same card */
      if (a) live.push(...anims(card, col, row));
    });
    affichees = shown;
    back.appendChild(fb); front.appendChild(ff);
    compter();
    resize();
    const ms = Math.round(performance.now() - t0);
    document.getElementById("stat").innerHTML =
      "<b>" + shown.length + "</b> " + t().cards + " · <b>" + live.length +
      "</b> " + t().animated + " · <b id='drawn'>0</b> " + t().onScreen +
      " · " + t().builtIn + " <b>" + ms + " ms</b> · <b id='fps'>—</b>";
  }

  /* ---- one instance per timeline, rendered once and copied everywhere ---- */
  const PLAY = {};
  let cell = { w: 0, h: 0, x: 0, y: 0, gap: 4 };
  let affichees = [];                   /* the cards currently laid out, in grid order */

  function resize() {
    const r = back.getBoundingClientRect();
    cell.gap = 4;
    cell.w = (r.width - cell.gap * (state.cols - 1)) / state.cols;
    cell.h = cell.w * H / W;
    /* full bleed: the game's sky reaches every edge of the screen, so it is sized on the
       window and not on the grid, which the page insets by its own padding */
    fit(cSky, innerWidth, innerHeight);
    /* two screens of band at most, and never past the texture cap */
    band.h = Math.max(innerHeight, Math.min(innerHeight * 2, Math.floor(CAP / dpr())));
    /* The effect layer reaches past the grid so a star on an edge card is not cut — but
       only as far as the window allows. Wider than the window and the page becomes
       scrollable sideways, which shifts everything centred to the left and leaves a
       black band on the right. The room available is the page's own margin. */
    const libre = Math.min(r.left, document.documentElement.clientWidth - r.right);
    band.x = Math.max(0, Math.min(Math.round(cell.w * 0.6), Math.floor(libre)));
    for (const c of [cAur, cPul]) {
      bandD = fit(c, r.width + band.x * 2, band.h);
      c.style.left = -band.x + "px";
    }
    band.top = null;
    fitSky();
    fitPlays();
  }

  /* Each timeline renders into its own little canvas, once, and that image is blitted to
     every tile that needs it. Rendering it larger than a tile is pure waste: at twelve
     columns a tile is 90 px and a fixed 400 px canvas throws away eight ninths of the
     work. Sized to what is actually shown, never above the old ceiling. */
  function fitPlays() {
    const d = dpr();
    for (const k in PLAY) {
      const p = PLAY[k];
      if (!p) continue;
      const px = Math.max(48, Math.min(p.span * 2, Math.round(p.span / W * cell.w * d)));
      if (px === p.px) continue;
      p.px = px;
      p.canvas.width = p.canvas.height = px;
      const r = px / p.span;
      p.lwf.rootMovie.moveTo(px / 2, px / 2);
      p.lwf.rootMovie.scaleTo(r, r);
    }
  }

  /* The game draws this timeline over its whole 852 x 1136 design area, edge to edge. A
     browser window is any shape, so it is scaled to cover it and centred on it — never on
     the canvas, which only covers the slice of window the grid occupies. The sky never
     tiles: the maquette gives it no repeat, and it does not need one. */
  function fitSky() {
    if (!sky) return;
    const s = Math.max(cSky.width / 852, cSky.height / 1136);
    sky.rootMovie.moveTo(cSky.width / 2, cSky.height / 2);
    sky.rootMovie.scaleTo(s, s);
  }
  /* No scroll handler: the overlays are fixed, so scrolling moves nothing about them —
     only the grid slides underneath, and tick() reads that offset once per frame.
     Resizing the canvas would reallocate its buffer on every scroll event. */
  addEventListener("resize", resize);

  const cSky = document.getElementById("sky");
  const gAur = cAur.getContext("2d"), gPul = cPul.getContext("2d");
  let sky = null;                       /* the outgame timeline, drawn straight into #sky */

  /* A phone reports 3 device pixels per CSS pixel; at that rate the sky alone is some
     3,6 million pixels redrawn every frame. These are soft glows over a blurred starfield
     — 1,5 is indistinguishable and a quarter of the work. */
  const dpr = () => Math.min(devicePixelRatio || 1, 1.5);
  /* Past a few thousand pixels a side, a mobile GPU cannot hold the canvas as a texture and
     the browser silently falls back to software rasterising — measured on a phone: a band
     of three screens made one canvas 11,5 Mpx and the frame took SIX SECONDS. Nothing is
     ever allowed to cross this. */
  const CAP = 2048;

  function fit(c, wCss, hCss) {
    const d = Math.max(0.5, Math.min(dpr(), CAP / wCss, CAP / hCss));
    c.style.width = wCss + "px";
    c.style.height = hCss + "px";
    c.width = Math.max(1, Math.round(wCss * d));
    c.height = Math.max(1, Math.round(hCss * d));
    return d;
  }
  let bandD = 1;
  /* the effect layers cover three screens and are only moved when the window drifts out */
  /* The effects overflow their tile — the star sticks out to the right of the last column
     and to the left of the first — so the layer is wider than the grid on both sides. */
  const band = { top: null, h: 0, x: 0 };
  let drawnEl = null;

  /* LWF timelines are authored at 30 images a second: running them at the display's rate
     doubles the work and shows nothing more. The blit to the overlays still happens every
     frame, so scrolling stays smooth. */
  /* ---- diagnostic, on ?debug ----------------------------------------------
     Guessing at a phone from a desktop does not work. This panel makes the page say
     where its time goes, and lets each layer be switched off one at a time — the only
     way to find out which one costs, on the machine that is actually slow. */
  const DBG = /[?&]debug\b/.test(location.search);
  const off = { sky: false, auras: false, pulses: false };
  const acc = { sky: 0, play: 0, blit: 0, all: 0, gap: 0, n: 0 };
  let dbgEl = null;
  if (DBG) {
    dbgEl = document.createElement("div");
    dbgEl.style.cssText = "position:fixed;left:8px;bottom:8px;z-index:9;padding:8px 10px;" +
      "background:rgba(6,8,12,.88);border:1px solid #2A3040;border-radius:7px;" +
      "font:11.5px/1.5 ui-monospace,monospace;color:#D6D9E0;white-space:pre;";
    document.body.appendChild(dbgEl);
    dbgEl.addEventListener("click", e => {
      const k = e.target.getAttribute && e.target.getAttribute("data-k");
      if (!k) return;
      off[k] = !off[k];
      const c = k === "sky" ? cSky : k === "auras" ? cAur : cPul;
      c.style.visibility = off[k] ? "hidden" : "";
    });
  }

  if (DBG) setInterval(() => {
    if (!acc.n) return;
    const d = dpr();
    const mpx = c => (c.width * c.height / 1e6).toFixed(2);
    const box = (k, l) => "<span data-k='" + k + "' style='cursor:pointer;padding:1px 5px;" +
      "border:1px solid #39435A;border-radius:4px;background:" +
      (off[k] ? "#3A2430" : "#1E2431") + "'>" + l + (off[k] ? " ✕" : "") + "</span>";
    dbgEl.innerHTML =
      Math.round(1000 / (acc.gap / acc.n)) + " i/s · " +
      (acc.all / acc.n).toFixed(2) + " ms de js par image\n" +
      "  ciel   " + (acc.sky / acc.n).toFixed(2) + " ms\n" +
      "  anims  " + (acc.play / acc.n).toFixed(2) + " ms\n" +
      "  report " + (acc.blit / acc.n).toFixed(2) + " ms · " + (acc.drawn || 0) + " vignettes\n" +
      "  canevas " + mpx(cSky) + " + " + mpx(cAur) + " + " + mpx(cPul) + " Mpx · dpr " +
      (devicePixelRatio || 1) + " plafonne a " + d.toFixed(2) + "\n  " +
      box("sky", "ciel") + " " + box("auras", "auras") + " " + box("pulses", "pulsations");
    acc.sky = acc.play = acc.blit = acc.all = acc.gap = acc.n = 0;
  }, 600);

  const STEP = 1 / 30;
  let prev = 0, skyAcc = 0, skyDone = false;
  let used = null;                    /* which timelines a visible tile actually needs */

  function tick(now) {
    const dt = prev ? Math.min((now - prev) / 1000, 0.1) : 0;
    const gap = prev ? now - prev : 0;
    prev = now;
    const t0 = DBG ? performance.now() : 0;
    /* the sky covers the whole window, so it is the one that costs: half rate again */
    if (sky && !off.sky) {
      skyAcc += dt;
      if (skyAcc >= STEP * 2) {
        sky.exec(skyAcc); sky.render(); skyAcc = 0;
        /* the still sky held the place while the timeline loaded; now that the timeline
           is drawing, drop it — two starfields at once read as a doubled grid */
        if (!skyDone) { skyDone = true; document.body.classList.remove("attente"); }
      }
    }
    const t1 = DBG ? performance.now() : 0;
    for (const k in PLAY) {
      const p = PLAY[k];
      if (!p || (used && !used[k])) continue;     /* nothing on screen needs this one */
      p.acc = (p.acc || 0) + dt;
      if (p.acc >= STEP) { p.lwf.exec(p.acc); p.lwf.render(); p.acc = 0; }
    }
    const t2 = DBG ? performance.now() : 0;
    const d = bandD;
    const seen = {};

    /* one layout read per frame, then pure arithmetic for every tile */
    const gr = back.getBoundingClientRect();
    const view = -gr.top;                       /* how far into the grid the window is */
    /* the band is centred on the window, so the margin either side is what is left over —
       and it is moved only once the window has eaten most of that margin */
    const margin = (band.h - innerHeight) / 2;
    const want = Math.max(0, Math.min(view - margin, back.scrollHeight - band.h));
    if (band.top === null || Math.abs(want - band.top) > margin * 0.6) {
      band.top = want;
      cAur.style.top = cPul.style.top = want + "px";
    }
    /* clear only the slice that can be seen, not three screens of canvas */
    const y0 = Math.max(0, view - band.top - 300);
    const y1 = Math.min(band.h, view - band.top + innerHeight + 300);
    for (const g of [gAur, gPul]) {
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, y0 * d, g.canvas.width, (y1 - y0) * d);
      g.globalCompositeOperation = "lighter";
    }
    let drawn = 0;
    for (const it of live) {
      const p = PLAY[it.k];
      if (!p) continue;
      const tx = it.col * (cell.w + cell.gap) + band.x;
      const ty = it.row * (cell.h + cell.gap) - band.top;
      if (ty + cell.h < y0 || ty > y1) continue;
      if (off.auras && it.k !== "pulse") continue;
      if (off.pulses && it.k === "pulse") continue;
      const g = it.k === "pulse" ? gPul : gAur;
      seen[it.k] = true;
      const s = p.span;
      g.drawImage(p.canvas,
        (tx + (p.ox - s / 2) / W * cell.w) * d, (ty + (H - p.oy - s / 2) / H * cell.h) * d,
        s / W * cell.w * d, s / H * cell.h * d);
      drawn++;
    }
    used = seen;
    if (DBG) {
      const t3 = performance.now();
      acc.sky += t1 - t0; acc.play += t2 - t1; acc.blit += t3 - t2;
      acc.all += t3 - t0; acc.gap += gap; acc.n++; acc.drawn = drawn;
    }
    drawnEl = drawnEl || document.getElementById("drawn");
    if (drawnEl && drawnEl.__n !== drawn) { drawnEl.textContent = drawn; drawnEl.__n = drawn; }
    requestAnimationFrame(tick);
  }

  /* ---- the player, fed from the payload ---------------------------------- */
  /* Embedded, the timelines arrive as base64 and the player is fed through a fake XHR.
     Served, each one is a folder of real files and the player fetches them itself — so the
     interception is installed only when there is something to intercept. */
  const EMBEDDED = Object.values(ANIM).some(a => a.lwf);
  const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  if (EMBEDDED) {
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__lwf = String(u).indexOf(".lwf") !== -1; this.__url = String(u);
    return this.__lwf ? undefined : open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    if (!this.__lwf) return send.apply(this, arguments);
    const key = this.__url.replace(/^.*\//, "").replace(/#.*$/, "").replace(/\.lwf$/, "");
    const bin = atob(ANIM[key].lwf), b = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
    const self = this;
    setTimeout(() => {
      for (const [k, v] of [["readyState", 4], ["status", 200], ["response", b.buffer]])
        Object.defineProperty(self, k, { value: v, configurable: true });
      if (self.onreadystatechange) self.onreadystatechange();
    }, 0);
  };
  }

  /* The player asks for its textures by the name the timeline carries. Embedded, that name
     maps to a data: URI; served, to a file — which is not even the same extension, since
     the textures go out as lossless WebP. One table either way. */
  const BANK = {};
  for (const k of Object.keys(ANIM)) Object.assign(BANK, ANIM[k].img || {});
  const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "src");
  Object.defineProperty(HTMLImageElement.prototype, "src", {
    configurable: true,
    get() { return desc.get.call(this); },
    set(v) {
      const k = Object.keys(BANK).find(n => String(v).indexOf(n) !== -1);
      desc.set.call(this, k ? BANK[k] : v);
    }
  });

  /* where the player should look for one timeline, whichever way it was built */
  const at = file => (ANIM[file] && ANIM[file].dir) || "./";

  LWF.useCanvasRenderer();
  const big = N.image_star_evo_big;
  const soe = N.fla_super_optimal_eff;
  const WANT = [
    ["lr_aura", "icon_rare_20000", "ef_001", N.fla_bg_effect.x, N.fla_bg_effect.y, 144],
    ["pulse", "icon_rare_20000", "ef_002", big.x + big.w / 2 + 15, big.y + big.h / 2, 120]
  ];
  /* The super Z awakening aura is not one animation but five: the controller formats
     "ef_{0:03d}" with (type % 10) + 1, so AGI gets ef_001 and END ef_005. Playing ef_001
     for every card painted the whole grid cyan. Five shared instances, one per type. */
  for (let t = 0; t < 5; t++)
    WANT.push(["seza_" + t, "super_optimal_eff", "ef_00" + (t + 1), soe.x, soe.y, 200]);
  /* anim_120000 is the outgame sky itself: z 2 of the same maquette whose z 1 is
     com_bg.png. It carries the grid, the starfield, the drifting nebula, the twinkles
     (bg_matataki) and the cyan ball that crosses (bg_ball). */
  LWF.ResourceCache.get().loadLWF({
    lwf: "anim_120000.lwf#sky", prefix: at("anim_120000"), worker: false, stage: cSky,
    onload: lwf => {
      if (!lwf) return;
      lwf.rendererFactory.clearColor = null;
      sky = lwf;
      lwf.rootMovie.attachMovie("ef_001", "m");
      fitSky();
    }
  });

  let pending = WANT.length;
  for (const [key, file, anime, ox, oy, span] of WANT) {
    /* The stage must keep its default size while LWF initialises — the renderer reads it
       to work out its own scale — and be resized in onload, the way the tile page does it.
       Sizing it beforehand shrank the effect to almost nothing behind the star. */
    const R = 2, cv = document.createElement("canvas");
    LWF.ResourceCache.get().loadLWF({
      lwf: file + ".lwf#" + key, prefix: at(file), worker: false, stage: cv,
      onload: lwf => {
        if (lwf) {
          lwf.rendererFactory.clearColor = null;
          cv.width = cv.height = span * R;
          lwf.rootMovie.moveTo(span * R / 2, span * R / 2);
          lwf.rootMovie.scaleTo(R, R);
          lwf.rootMovie.attachMovie(anime, "m");
          PLAY[key] = { lwf, canvas: cv, ox, oy, span, px: span * R };
          fitPlays();
        }
        if (--pending === 0) requestAnimationFrame(tick);
      }
    });
  }

  /* A label may be a string or a function: functions are re-read on every sync, so a
     language switch relabels every button without rebuilding the group. The count of
     buttons never changes with the language, so the DOM is built once. */
  function group(id, items, get, set) {
    const host = document.getElementById(id);
    const made = items.map(it => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "pick";
      b.addEventListener("click", () => { set(it.value); sync(); });
      host.appendChild(b);
      return [b, it.value, it.label];
    });
    return () => made.forEach(([b, v, label]) => {
      b.textContent = typeof label === "function" ? label() : label;
      b.setAttribute("aria-pressed", String(get() === v));
    });
  }
  const syncs = [
    group("cCols", [5, 10, 25].map(n => ({ label: String(n), value: n })), () => state.cols, v => state.cols = v),
    group("cRare", [{ label: () => t().allF, value: -1 }].concat(RARE.map((r, i) => ({ label: r.toUpperCase(), value: i }))),
          () => state.rare, v => state.rare = v),
    group("cType", [{ label: () => t().all, value: -1 }].concat(
            [0, 1, 2, 3, 4].map(i => ({ label: () => types()[i], value: i }))),
          () => state.type, v => state.type = v),
    group("cEv", [{ label: () => t().all, value: -1 },
                  { label: () => t().ev[4], value: 4 }, { label: () => t().ev[3], value: 3 },
                  { label: () => t().ev[2], value: 2 }, { label: () => t().ev[1], value: 1 },
                  { label: () => t().ev[0], value: 0 }],
          () => state.ev, v => state.ev = v),
    group("cOwn", [{ label: () => t().allF, value: "tous" }, { label: () => t().owned, value: "oui" },
                   { label: () => t().missing, value: "non" }],
          () => state.own, v => state.own = v)
  ];
  {
    const champ = document.getElementById("cName");
    let attente = 0;
    champ.addEventListener("input", () => {
      clearTimeout(attente);
      attente = setTimeout(() => { state.nom = champ.value; resume(); paint(); }, 180);
    });
  }
  const catSel = document.getElementById("cCat");
  /* (Re)build the menu in the current language, sorted by name so a known category is found
     by scanning, not by hunting an id order. Rebuilt on a language switch, selection kept. */
  function remplirCat() {
    const garde = catSel.value;
    catSel.length = 1; catSel.options[0].textContent = t().allF;   /* keep "all", relabel it, drop the rest */
    Object.keys(CATS).map(id => [id, nomCat(id)])
      .sort((a, b) => a[1].localeCompare(b[1]))
      .forEach(([id, nom]) => {
        const o = document.createElement("option");
        o.value = id; o.textContent = nom; catSel.appendChild(o);
      });
    catSel.value = garde;
  }
  remplirCat();
  catSel.addEventListener("change", () => {
    state.cat = +catSel.value;
    catSel.dataset.on = state.cat < 0 ? "0" : "1";
    resume(); paint();
  });
  /* What a tile animates, in one place: the render lists them for every owned card, and a
     click adds or removes exactly these. Keeping two copies of the rule is how a card ends
     up drawn as owned but still dark until the page is reloaded. */
  function anims(card, col, row) {
    const out = [];
    const awk = !!card.awk, eza = !!card.eza;
    if (card.rarity === 5) out.push({ k: "lr_aura", col, row });
    if (eza) out.push({ k: "seza_" + (card.element % 10), col, row });
    if (awk && card.rarity >= 4) out.push({ k: "pulse", col, row });
    return out;
  }

  function compter() {
    const par = {}, tot = {};
    for (const c of CARDS) {
      tot[c.rarity] = (tot[c.rarity] || 0) + 1;
      if (possede.has(c.top)) par[c.rarity] = (par[c.rarity] || 0) + 1;
    }
    const parts = RARE.map((r, i) => tot[i]
      ? `<span class="part">${r.toUpperCase()} <i>${par[i] || 0}</i>/${tot[i]}</span>` : "")
      .reverse().join("");
    document.getElementById("score").innerHTML =
      `<span><b>${possede.size}</b> / ${CARDS.length}</span>` + parts +
      `<span class="part lien">` +
      `<a href="#" id="exp">${t().export}</a> · <a href="#" id="imp">${t().import}</a>` +
      ` · <a href="#" id="vider">${t().clearAll}</a></span>`;
    document.getElementById("exp").onclick = e => {
      e.preventDefault();
      const b = new Blob([JSON.stringify([...possede])], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b); a.download = "ma-collection.json"; a.click();
    };
    document.getElementById("imp").onclick = e => {
      e.preventDefault();
      const i = document.createElement("input");
      i.type = "file"; i.accept = "application/json";
      i.onchange = () => i.files[0].text().then(txt => {   /* not `t`: that shadows the i18n helper */
        try { possede = new Set(JSON.parse(txt)); sauver(); sync(); } catch (err) {}
      });
      i.click();
    };
    /* Des centaines de cases cochées à la main, effaçables d'un doigt et sans retour :
       c'est le seul geste de la page qui mérite qu'on demande confirmation. */
    document.getElementById("vider").onclick = e => {
      e.preventDefault();
      if (!possede.size) return;
      if (!confirm(t().confirmClear(possede.size))) return;
      possede.clear(); sauver(); sync();
    };
  }

  /* ---- click to toggle, drag to paint -------------------------------------
     Five hundred clicks to enter a box is a chore; painting a row in one gesture is not.
     The value is decided on the first card touched and applied to every card the pointer
     crosses, the way a spreadsheet fills cells. Mouse only: on a touch screen the same
     gesture is how you scroll. */
  let peint = null;
  function marquer(el) {
    const id = el && el.dataset && +el.dataset.id;
    if (!id || peint === null) return;
    if (possede.has(id) === peint) return;
    peint ? possede.add(id) : possede.delete(id);
    const i = +el.dataset.i;              /* the rank is written once, at build time */
    for (const plane of [back, front]) {
      const cell = plane.children[i];
      if (cell) cell.classList.toggle("non", !peint);
    }
    const col = i % state.cols, row = (i / state.cols) | 0;
    live = live.filter(t => !(t.col === col && t.row === row));
    if (peint && affichees[i]) live.push(...anims(affichees[i], col, row));
    sauver(); compter();
  }
  /* toggle one cell, whatever it currently is */
  function basculer(cell) {
    peint = !possede.has(+cell.dataset.id);
    marquer(cell);
    peint = null;
  }
  /* A tap toggles, a scroll does not — and the browser already tells the two apart: it fires
     `click` for a real tap (mouse or finger) and swallows it the instant a touch turns into a
     scroll, with per-platform thresholds. So we key the single toggle on `click` rather than
     guess a pixel distance ourselves. A mouse drag paints a row; the trailing click is then
     swallowed so the first card is not flipped twice. */
  let origine = null, aPeint = false;
  back.addEventListener("click", e => {
    if (aPeint) { aPeint = false; return; }   /* a mouse drag already handled these cards */
    const cell = e.target.closest(".cell");
    if (cell) basculer(cell);
  });
  back.addEventListener("pointerdown", e => {
    /* touch: let the click decide, so scroll is free. Clear the paint flag so a mouse drag
       that ended off the grid, leaving it set, cannot swallow this tap. */
    if (e.pointerType !== "mouse") { aPeint = false; return; }
    const cell = e.target.closest(".cell");
    if (!cell) return;
    origine = cell; peint = null; aPeint = false;
    e.preventDefault();                        /* no text selection while dragging */
  });
  const survolEl = document.getElementById("survol");
  back.addEventListener("pointermove", e => {
    const cell = e.target.closest(".cell");
    if (cell && survolEl) {
      const card = affichees[+cell.dataset.i];
      if (card) survolEl.innerHTML =
        "<b>" + nomC(card) + "</b> · " + RARE[card.rarity].toUpperCase() +
        " · " + t().lv + " " + card.lv + " · " + types()[card.element % 10] +
        " · " + t().awakening + " " + t().ev[card.ev] +
        " · <span style='opacity:.6'>" + card.top + "</span>";
    }
    /* drag-to-paint, mouse only: the value is fixed from the first card and applied to every
       card the pointer crosses, the origin included */
    if (e.pointerType !== "mouse" || !e.buttons || !origine || !cell) return;
    if (peint === null) { peint = !possede.has(+origine.dataset.id); marquer(origine); aPeint = true; }
    marquer(cell);
  });
  back.addEventListener("pointerleave", () => { if (survolEl) survolEl.innerHTML = "&nbsp;"; });
  addEventListener("pointerup", () => { peint = null; origine = null; });

  /* Ce que le panneau replié annonce. Sans cela un filtre laissé actif se traduit par une
     grille amputée dont plus rien ne dit pourquoi. */
  const resumeEl = document.getElementById("fResume");
  const razEl = document.getElementById("fRaz");
  function resume() {
    const p = [];
    if (state.cols !== 5) p.push(state.cols + " " + t().columnsWord);
    if (state.rare >= 0) p.push(RARE[state.rare].toUpperCase());
    if (state.type >= 0) p.push(types()[state.type]);
    if (state.ev >= 0) p.push(t().ev[state.ev]);
    if (state.cat >= 0) p.push(nomCat(state.cat));
    if (state.own !== "tous") p.push(state.own === "oui" ? t().owned : t().missing);
    if (state.nom) p.push("« " + state.nom + " »");
    resumeEl.textContent = p.length ? p.join(" · ") : t().allCards;
    resumeEl.classList.toggle("vide", !p.length);
  }
  razEl.addEventListener("click", e => {
    /* le bouton est dans le summary : sans cela le clic replierait aussi le panneau */
    e.preventDefault(); e.stopPropagation();
    state.cols = 5; state.rare = state.type = state.ev = state.cat = -1;
    state.own = "tous"; state.nom = "";
    document.getElementById("cName").value = "";
    catSel.value = "-1"; catSel.dataset.on = "0";
    sync();
  });

  /* The language buttons exist only when a second base has been added — with one language
     there is nothing to switch, so the bar stays hidden. Switching retranslates the whole
     page: static chrome (appliquerTextes), the filter buttons and the summary (sync relabels
     them from their label functions), the category menu, and the tiles' names and badges
     (paint, called by sync). The choice is remembered. */
  function majLangBtns() {
    document.querySelectorAll("#cLang .pick").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.l === lang)));
  }
  function changerLangue(l) {
    if (!LANGS.includes(l) || l === lang) return;
    lang = l;
    try { localStorage.setItem(CLE_LANG, l); } catch (e) {}
    appliquerTextes(); remplirCat(); majLangBtns(); sync();
  }
  {
    const bar = document.getElementById("langbar");
    if (LANGS.length > 1 && bar) {
      bar.hidden = false;
      const host = document.getElementById("cLang");
      LANGS.forEach(l => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "pick"; b.textContent = l.toUpperCase();
        b.dataset.l = l;
        b.addEventListener("click", () => changerLangue(l));
        host.appendChild(b);
      });
      majLangBtns();
    }
  }

  function sync() { syncs.forEach(f => f()); resume(); paint(); }

  /* a frame counter, so the claim is checkable rather than asserted */
  let frames = 0, mark = performance.now();
  setInterval(() => {
    const el = document.getElementById("fps"), dt = (performance.now() - mark) / 1000;
    /* headless captures advance virtual time without ever painting: report nothing
       rather than a rate of zero that would only be an artefact of the capture */
    if (el && frames > 4) el.textContent = Math.round(frames / dt) + " i/s";
    frames = 0; mark = performance.now();
  }, 1000);
  const raf = requestAnimationFrame;
  requestAnimationFrame = function (f) { return raf(t => { frames++; f(t); }); };

  if (IMG.sky) {
    document.documentElement.style.setProperty("--sky", "url(" + IMG.sky + ")");
    document.body.classList.add("attente");
  }
  document.documentElement.style.setProperty("--atlas", "url(" + IMG.atlas + ")");
  document.documentElement.style.setProperty("--atlas-max", "url(" + IMG.atlasMax + ")");
  appliquerTextes();               /* the static chrome, in the current language, before first paint */
  sync();
})();
