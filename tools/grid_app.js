(function () {
  const IMG = JSON.parse(document.getElementById("gImg").textContent);
  const FONT = JSON.parse(document.getElementById("gFont").textContent);
  const LAY = JSON.parse(document.getElementById("gLay").textContent);
  const ANIM = JSON.parse(document.getElementById("gAnim").textContent);
  const CARDS = JSON.parse(document.getElementById("gCards").textContent);
  const THUMB = JSON.parse(document.getElementById("gThumbs").textContent);

  const W = LAY.w, H = LAY.h, N = LAY.nodes, NAT = IMG.native;
  const pc = (v, t) => (v / t * 100) + "%";
  const RARE = ["n", "r", "sr", "ssr", "ur", "lr"];
  const grid = document.getElementById("grid");
  const state = { cols: 6, rare: -1, anim: true, demo: false };

  /* the sprite rule from the binary: native size x scale, centred on the box's centre */
  function place(el, node, nat) {
    const n = N[node], s = n.scale || 1, dw = nat[0] * s, dh = nat[1] * s;
    el.style.left = pc(n.x + n.w / 2 - dw / 2, W);
    el.style.top = pc(H - (n.y + n.h / 2) - dh / 2, H);
    el.style.width = pc(dw, W);
    el.style.height = pc(dh, H);
    el.style.zIndex = n.z;
  }
  function sprite(tile, node, src, nat) {
    const e = document.createElement("img");
    e.src = src; e.alt = "";
    place(e, node, nat);
    tile.appendChild(e);
    return e;
  }

  /* The band's number, glyph by glyph, straight out of the atlas. Same rule as the single
     tile — position (x + w/2, y + 3 + h/2), anchor lifted out of the font's tall line box
     — but drawn as background slices instead of a canvas. */
  function text(tile, node, str) {
    const n = N[node], sc = n.scale || 1, kern = n.kerning || 0, lh = FONT.lineHeight;
    let lw = 0;
    for (const ch of str) {
      const g = FONT.glyphs[ch.codePointAt(0)];
      if (g) lw += g[6] + kern;
    }
    const ay = 0.5 + sc * (n.h - lh) / (2 * lh);
    const left = (n.x + n.w / 2) - lw * sc / 2;
    const topY = (n.y + 3 + n.h / 2) - lh * ay * sc + lh * sc;   // top of the line box
    const box = document.createElement("b");
    box.className = "txt";
    box.style.left = pc(left, W);
    box.style.top = pc(H - topY, H);
    box.style.width = pc(lw * sc, W);
    box.style.height = pc(lh * sc, H);
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
        /* a percentage background-position aligns the same relative point of image and
           box, so the offset is gx / (atlas - glyph), not -gx / glyph */
        i.style.backgroundSize = (FONT.atlasW / g[2] * 100) + "% " + (FONT.atlasH / g[3] * 100) + "%";
        i.style.backgroundPosition = (g[0] / (FONT.atlasW - g[2]) * 100) + "% " +
                                     (g[1] / (FONT.atlasH - g[3]) * 100) + "%";
        box.appendChild(i);
      }
      pen += g[6] + kern;
    }
    box.setAttribute("role", "img");
    box.setAttribute("aria-label", str);
    tile.appendChild(box);
    return box;
  }

  function baked(tile, key) {
    const a = ANIM[key], e = document.createElement("div");
    e.className = "anim";
    e.style.setProperty("--n", a.n);
    e.style.left = pc(a.x, W); e.style.top = pc(H - a.y - a.h, H);
    e.style.width = pc(a.w, W); e.style.height = pc(a.h, H);
    e.style.zIndex = a.z;
    const band = document.createElement("u");
    band.style.backgroundImage = "url(" + a.img + ")";
    e.appendChild(band);
    tile.appendChild(e);
    return e;
  }

  /* `o` forces states the card's own data does not carry: awakened (the row shifts and
     the big star appears, with its pulse), super Z awakening, level at its cap */
  function build(card, o) {
    o = o || {};
    const t = document.createElement("div");
    t.className = "tile" + (o.maxlv ? " max" : "");
    t.title = card.name + " · " + RARE[card.rarity].toUpperCase() + " · Nv " + card.lv;
    const type = card.element % 10, rare = Math.min(card.rarity, 3);
    sprite(t, "img_bg", IMG.bg[type + "_" + rare], NAT.bg);
    /* the tile only declares what it should play; the layers themselves are built when
       it comes near the viewport and thrown away when it leaves. Creating them eagerly
       is what made a fully animated grid unusable — the cost is in existing, not in
       being on screen. */
    const plays = [];
    if (o.seza || state.demo) plays.push("seza");
    if (card.rarity === 5) plays.push("lr_aura");
    const art = sprite(t, "image_thumb", THUMB[card.id], [250, 250]);
    art.loading = "lazy";
    sprite(t, "image_chara_bottom_base", IMG.band[String(type)], NAT.band);
    sprite(t, "image_rare_ssr", IMG.rare[RARE[card.rarity]], NAT.rare);
    const awakened = o.awakened || state.demo;
    const stars = o.stars || card.stars || (state.demo ? 3 : 0);
    if (stars) {
      const node = awakened ? "image_star_evo_dokkan" : "image_star_evo";
      sprite(t, node, IMG.star[Math.min(stars, 4)], NAT.star[Math.min(stars, 4)]);
    }
    if (awakened) {
      sprite(t, "image_star_evo_big", IMG.star["5"], NAT.star["5"]);
      if (card.rarity >= 4 || state.demo) plays.push("pulse");
    }
    if (o.lock) sprite(t, "image_cha_icon_lock", IMG.lock, NAT.lock);
    sprite(t, "image_label_lv", IMG.label, NAT.label);
    text(t, "font_num", String(card.lv));
    sprite(t, "image_icon_type", IMG.type[String(card.element)], NAT.type);
    if (plays.length) t.dataset.plays = plays.join(" ");
    return t;
  }

  /* one real card per rarity, run through the states the controller can produce */
  function matrix() {
    const host = document.getElementById("matrix");
    if (!host) return;
    const byRare = {};
    for (const c of CARDS) if (!(c.rarity in byRare)) byRare[c.rarity] = c;
    const STATES = [
      ["de base", {}],
      ["verrouillée", { lock: 1 }],
      ["4 ★", { stars: 4 }],
      ["éveillée", { awakened: 1, stars: 3 }],
      ["niveau max", { maxlv: 1, stars: 4 }],
      ["éveil Z suprême", { seza: 1, awakened: 1, stars: 3, maxlv: 1 }]
    ];
    for (let r = 5; r >= 0; r--) {
      const c = byRare[r];
      if (!c) continue;
      for (const [label, o] of STATES) {
        const fig = document.createElement("figure");
        const tile = build(c, o);
        for (const k of (tile.dataset.plays || "").split(" ").filter(Boolean)) baked(tile, k);
        fig.appendChild(tile);
        const cap = document.createElement("figcaption");
        cap.innerHTML = "<b>" + RARE[r].toUpperCase() + "</b>" + label;
        fig.appendChild(cap);
        host.appendChild(fig);
      }
    }
  }

  function paint() {
    const t0 = performance.now();
    grid.style.setProperty("--cols", state.cols);
    const shown = CARDS.filter(c => state.rare < 0 || c.rarity === state.rare);
    grid.textContent = "";
    const frag = document.createDocumentFragment();
    for (const c of shown) frag.appendChild(build(c));
    grid.appendChild(frag);
    document.body.classList.toggle("still", !state.anim);
    watch();
    const ms = Math.round(performance.now() - t0);
    document.getElementById("stat").innerHTML =
      "<b>" + shown.length + "</b> cartes · <b>" +
      grid.querySelectorAll("img,i,div.anim").length + "</b> éléments · construites en <b>" +
      ms + " ms</b>";
  }

  /* only the tiles near the viewport hold animation layers at all */
  let seer = null, liveNow = 0;
  function watch() {
    if (seer) seer.disconnect();
    liveNow = 0;
    seer = new IntersectionObserver(es => {
      for (const e of es) {
        const t = e.target;
        const on = e.isIntersecting, had = t.classList.contains("live");
        if (on === had) continue;
        t.classList.toggle("live", on);
        liveNow += on ? 1 : -1;
        if (on) for (const k of t.dataset.plays.split(" ")) baked(t, k);
        else for (const a of t.querySelectorAll(".anim")) a.remove();
      }
      const s = document.getElementById("statLive");
      if (s) s.textContent = liveNow + " animées à l'écran";
    }, { rootMargin: "300px 0px" });
    for (const t of grid.children) if (t.dataset.plays) seer.observe(t);
    for (const f of document.querySelectorAll("#matrix .tile")) f.classList.add("live");
  }

  function group(id, items, get, set) {
    const host = document.getElementById(id);
    const made = items.map(it => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "pick"; b.textContent = it.label;
      b.addEventListener("click", () => { set(it.value); sync(); });
      host.appendChild(b);
      return [b, it.value];
    });
    return () => made.forEach(([b, v]) => b.setAttribute("aria-pressed", String(get() === v)));
  }
  const syncs = [
    group("cCols", [4, 6, 8, 12].map(n => ({ label: String(n), value: n })),
          () => state.cols, v => state.cols = v),
    group("cRare", [{ label: "toutes", value: -1 }].concat(
            RARE.map((r, i) => ({ label: r.toUpperCase(), value: i }))),
          () => state.rare, v => state.rare = v),
    group("cAnim", [{ label: "en marche", value: true }, { label: "figées", value: false }],
          () => state.anim, v => state.anim = v),
    group("cDemo", [{ label: "réelles", value: false }, { label: "toutes animées", value: true }],
          () => state.demo, v => state.demo = v)
  ];
  function sync() { syncs.forEach(f => f()); paint(); }

  document.documentElement.style.setProperty("--atlas", "url(" + IMG.atlas + ")");
  document.documentElement.style.setProperty("--atlas-max", "url(" + IMG.atlasMax + ")");
  matrix();
  const tb = document.getElementById("baked");
  for (const [k, a] of Object.entries(ANIM)) {
    const tr = document.createElement("tr");
    const kb = Math.round(a.img.length * 0.75 / 1024);
    tr.innerHTML = "<td class='mono'>" + k + "</td><td>" + a.n +
      "</td><td class='mono'>" + Math.round(a.w) + " × " + Math.round(a.h) +
      " unités</td><td class='mono'>" + kb + " Ko</td>";
    tb.appendChild(tr);
  }
  sync();
})();
