(function () {
  const IMG = JSON.parse(document.getElementById("tileImages").textContent);
  const FONT = JSON.parse(document.getElementById("tileFont").textContent);
  const ANIM = JSON.parse(document.getElementById("tileAnims").textContent);
  const LAY = JSON.parse(document.getElementById("tileLayout").textContent);

  const W = LAY.w, H = LAY.h, N = LAY.nodes;      // 130 x 150, origin bottom left
  const NAT = IMG.native;                          // native pixel size of each file

  const TYPES = [
    { i: 0, short: "AGI" }, { i: 1, short: "TEC" }, { i: 2, short: "INT" },
    { i: 3, short: "PUI" }, { i: 4, short: "END" }
  ];
  const RARES = ["n", "r", "sr", "ssr", "ur", "lr"];
  const RLABEL = ["N", "R", "SR", "SSR", "UR", "LR"];
  const CLASSES = [{ p: 0, label: "sans classe" }, { p: 1, label: "Super" }, { p: 2, label: "Extrême" }];

  /* only the fifteen type badges and the level label are translated; everything else on
     the tile is the same file in every locale */
  const LANGS = { fr: "français", en: "anglais", de: "allemand", es: "espagnol" };
  const state = { type: 1, rare: 3, cls: 1, stars: 4, lock: true, on: false, band: "lv",
                  awakened: false, maxlv: false, lang: "fr", seza: false };
  const tile = document.getElementById("tile");
  const pc = (v, t) => (v / t * 100) + "%";

  /* ---- the sprite rule, straight from the binary --------------------------
     setContentSize(w, h); setPosition(x + w/2, y + h/2); setAnchorPoint(0.5, 0.5),
     and loading the texture resets the content size to the texture's own — so the
     file is drawn at its native size times scale, centred on the box's centre. The
     transparent margins inside a PNG are part of that placement.                  */
  function placeSprite(el, name, nat) {
    const n = N[name], s = n.scale || 1;
    const dw = nat[0] * s, dh = nat[1] * s;
    el.style.left = pc(n.x + n.w / 2 - dw / 2, W);
    el.style.top = pc(H - (n.y + n.h / 2) - dh / 2, H);
    el.style.width = pc(dw, W);
    el.style.height = pc(dh, H);
  }
  function sprite(name) {
    const el = document.createElement("img");
    el.className = "node"; el.alt = ""; el.style.zIndex = N[name].z;
    tile.appendChild(el);
    return el;
  }

  const elBg = sprite("img_bg");
  const elArt = sprite("image_thumb");
  const elBand = sprite("image_chara_bottom_base");
  const elRare = sprite("image_rare_ssr");
  const elStars = sprite("image_star_evo");
  const elStarsDok = sprite("image_star_evo_dokkan");
  const elStarBig = sprite("image_star_evo_big");
  const elLock = sprite("image_cha_icon_lock");
  const elLabel = sprite("image_label_lv");
  const elType = sprite("image_icon_type");

  /* ---- the label rule, also from the binary -------------------------------
     For align/valign "center": position = (x + w/2, y + 3 + h/2) and
     anchor.y = 0.5 + scale * (h - lineHeight) / (2 * lineHeight), which lifts the
     glyphs out of the font's oversized line box and seats them in the band.       */
  const PAD = 8;                       // room so a glyph wider than its advance survives
  function textNode(name) {
    const cv = document.createElement("canvas");
    cv.className = "node"; cv.style.zIndex = N[name].z;
    tile.appendChild(cv);
    return { cv, name };
  }
  function drawText(t, s) {
    const n = N[t.name], sc = n.scale || 1, kern = n.kerning || 0, lh = FONT.lineHeight;
    let lw = 0;
    for (const ch of s) {
      const g = FONT.glyphs[ch.codePointAt(0)];
      if (g) lw += g[6] + kern;
    }
    t.cv.width = Math.max(1, Math.round(lw) + 2 * PAD);
    t.cv.height = lh + 2 * PAD;
    t.cv.setAttribute("role", "img");
    t.cv.setAttribute("aria-label", s);
    const c = t.cv.getContext("2d");
    c.clearRect(0, 0, t.cv.width, t.cv.height);
    let x = PAD;
    for (const ch of s) {
      const g = FONT.glyphs[ch.codePointAt(0)];
      if (!g) continue;
      if (atlasReady && g[2] && g[3])
        c.drawImage(atlas, g[0], g[1], g[2], g[3], x + g[4], PAD + g[5], g[2], g[3]);
      x += g[6] + kern;
    }
    /* the glyphs are white with a black outline; the game tints the label itself, so
       recolour only the white body and leave the outline alone */
    if (t.tint) {
      const im = c.getImageData(0, 0, t.cv.width, t.cv.height), p = im.data;
      for (let i = 0; i < p.length; i += 4) {
        if (p[i + 3] > 8 && p[i] > 150 && p[i + 1] > 150 && p[i + 2] > 150) {
          p[i] = t.tint[0]; p[i + 1] = t.tint[1]; p[i + 2] = t.tint[2];
        }
      }
      c.putImageData(im, 0, 0);
    }
    const ay = 0.5 + sc * (n.h - lh) / (2 * lh);
    const left = (n.x + n.w / 2) - lw * sc / 2 - PAD * sc;
    const bottom = (n.y + 3 + n.h / 2) - lh * ay * sc - PAD * sc;
    t.cv.style.left = pc(left, W);
    t.cv.style.top = pc(H - bottom - t.cv.height * sc, H);
    t.cv.style.width = pc(t.cv.width * sc, W);
    t.cv.style.height = pc(t.cv.height * sc, H);
    /* the italic shader leans the glyphs about the label's own origin — its baseline,
       which sits PAD above the padded canvas — not about the middle */
    t.cv.style.transform = n.italic ? "skewX(-" + LAY.italic_deg + "deg)" : "";
    t.cv.style.transformOrigin = "0% " + ((t.cv.height - PAD) / t.cv.height * 100) + "%";
  }
  const TXT = {
    lv: [[textNode("font_num"), () => FONT.samples.lv]],
    rate: [[textNode("font_text"), () => FONT.samples.rate]]
  };

  /* ---- two timelines, both out of icon_rare_20000.lwf ----------------------
     fla_bg_effect plays ef_001 behind the artwork, for LR only. PartsAwakenStar.cpp
     plays ef_002 over everything (z 100) at image_star_evo_big's own position shifted
     by (15, 0), once the card is awakened and its level has reached the cap.        */
  function lwfCanvas(z) {
    const cv = document.createElement("canvas");
    cv.className = "node lwf";
    cv.style.zIndex = z;
    tile.appendChild(cv);
    return cv;
  }
  const sezaBox = lwfCanvas(N.fla_super_optimal_eff.z);
  const effBox = lwfCanvas(N.fla_bg_effect.z);
  const pulseBox = lwfCanvas(100);

  /* ---- the game's bitmap font --------------------------------------------- */
  const atlas = new Image();
  let atlasReady = false;
  atlas.onload = () => { atlasReady = true; paintText(); };
  atlas.src = FONT.atlas;

  function paintText() {
    /* white normally; the controller overwrites it with yellow once level >= max */
    TXT.lv[0][0].tint = state.maxlv ? [255, 255, 0] : null;
    for (const mode of ["lv", "rate"])
      for (const [t, get] of TXT[mode]) {
        t.cv.hidden = mode !== state.band;
        if (mode === state.band) drawText(t, get());
      }
  }

  /* ---- repaint ------------------------------------------------------------ */
  const LINES = [
    ["Cadre + fond", () => "cha_base_0" + state.type + "_0" + Math.min(state.rare, 3) + ".png"],
    ["Illustration", () => "card_1024540_thumb.png"],
    ["Bandeau", () => "cha_base_bottom_0" + state.type + (state.on ? "_on" : "") + ".png"],
    ["Rareté", () => "cha_rare_sm_" + RARES[state.rare] + ".png"],
    ["Étoiles", () => state.stars
      ? "cha_evo_star" + state.stars + " · " + (state.awakened ? "image_star_evo_dokkan" : "image_star_evo")
      : "—"],
    ["Grande étoile", () => state.awakened ? "cha_evo_star5 · image_star_evo_big" : "—"],
    ["Niveau", () => state.maxlv ? "font_num en jaune (255,255,0)" : "font_num en blanc"],
    ["Cadenas", () => state.lock ? "cha_icon_lock.png" : "—"],
    ["Nv", () => state.band === "lv" ? "com_label_lv.png · " + state.lang : "—"],
    ["Nombre", () => state.band === "lv"
      ? "font_num · number.fnt"
      : "font_text · échelle 0,58, centré x 65"],
    ["Badge", () => "cha_type_icon_" + String(state.cls * 10 + state.type).padStart(2, "0")
      + ".png · " + state.lang],
    ["Éclat LR", () => state.rare === 5 ? "icon_rare_20000.lwf · ef_001" : "— (LR seulement)"],
    ["Éveil Z suprême", () => state.seza
      ? "super_optimal_eff.lwf · ef_" + String(state.type + 1).padStart(3, "0") : "—"],
    ["Pulsation", () => (state.awakened && state.maxlv && state.rare >= 4)
      ? "icon_rare_20000.lwf · ef_002" : "— (éveil + max, UR/LR)"]
  ];
  const list = document.getElementById("layerList");
  const cells = LINES.map(([label, f]) => {
    const li = document.createElement("li");
    const b = document.createElement("b"); b.textContent = label;
    const sp = document.createElement("span");
    li.append(b, sp); list.appendChild(li);
    return [sp, f];
  });

  function paint() {
    elBg.src = IMG.bg[state.type + "_" + Math.min(state.rare, 3)];
    placeSprite(elBg, "img_bg", NAT.bg);
    elArt.src = IMG.art;
    placeSprite(elArt, "image_thumb", NAT.art);
    elBand.src = IMG.band[state.type + (state.on ? "_on" : "")];
    placeSprite(elBand, "image_chara_bottom_base", NAT.band);
    elRare.src = IMG.rare[RARES[state.rare]];
    placeSprite(elRare, "image_rare_ssr", NAT.rare);
    /* the row goes into image_star_evo, or into image_star_evo_dokkan on an awakened
       card — one whose id does not end in 0 — which also lights the big star */
    const rowEl = state.awakened ? elStarsDok : elStars, rowNode =
      state.awakened ? "image_star_evo_dokkan" : "image_star_evo";
    elStars.hidden = elStarsDok.hidden = true;
    if (state.stars) {
      rowEl.hidden = false;
      rowEl.src = IMG.star[state.stars];
      placeSprite(rowEl, rowNode, NAT.star[state.stars]);
    }
    elStarBig.hidden = !state.awakened;
    if (state.awakened) {
      elStarBig.src = IMG.star[5];
      placeSprite(elStarBig, "image_star_evo_big", NAT.star[5]);
    }
    elLock.src = IMG.lock;
    elLock.hidden = !state.lock;
    placeSprite(elLock, "image_cha_icon_lock", NAT.lock);
    elLabel.src = IMG.label[state.lang];
    elLabel.hidden = state.band !== "lv";
    placeSprite(elLabel, "image_label_lv", NAT.label);
    elType.src = IMG.type[state.lang][state.cls * 10 + state.type];
    placeSprite(elType, "image_icon_type", NAT.type);
    /* the super Z awakening aura picks one timeline per type: ef_001 for AGI through
       ef_005 for END — the controller formats "ef_{0:03d}" with (type % 10) + 1 */
    sezaBox.hidden = !state.seza;
    if (state.seza && seza.lwf) seza.play("ef_" + String(state.type + 1).padStart(3, "0"));
    effBox.hidden = state.rare !== 5;
    pulseBox.hidden = !(state.awakened && state.maxlv && state.rare >= 4);
    paintText();
    cells.forEach(([sp, f]) => sp.textContent = f());
  }

  /* ---- controls ----------------------------------------------------------- */
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
    group("cType", TYPES.map(t => ({ label: t.short, value: t.i })), () => state.type, v => state.type = v),
    group("cRare", RLABEL.map((s, i) => ({ label: s, value: i })), () => state.rare, v => state.rare = v),
    group("cClass", CLASSES.map(c => ({ label: c.label, value: c.p })), () => state.cls, v => state.cls = v),
    /* the row's own files are cha_evo_star1..4, all 80 x 36 for a box of 80 x 36.
       cha_evo_star5 is the odd one out at 80 x 60 — the single big star — and the maquette
       has a node cut for it: image_star_evo_big, 80 x 50 at scale 0.85, i.e. 51 tall.
       Forced into the row instead, it overflows the box by 12 units top and bottom and
       lands flush against the tile's right edge at exactly 130. */
    group("cStar", [0, 1, 2, 3, 4].map(n => ({ label: n ? n + " ★" : "aucune", value: n })), () => state.stars, v => state.stars = v),
    group("cState", [{ label: "au repos", value: false }, { label: "sélectionnée", value: true }], () => state.on, v => state.on = v),
    group("cLock", [{ label: "verrouillée", value: true }, { label: "libre", value: false }], () => state.lock, v => state.lock = v),
    group("cBand", [{ label: "niveau", value: "lv" }, { label: "taux", value: "rate" }], () => state.band, v => state.band = v),
    group("cAwk", [{ label: "carte de base", value: false }, { label: "éveillée", value: true }], () => state.awakened, v => state.awakened = v),
    group("cMax", [{ label: "en cours", value: false }, { label: "niveau max", value: true }], () => state.maxlv, v => state.maxlv = v),
    group("cSeza", [{ label: "non", value: false }, { label: "oui", value: true }], () => state.seza, v => state.seza = v),
    group("cLang", Object.keys(LANGS).map(k => ({ label: LANGS[k], value: k })), () => state.lang, v => state.lang = v)
  ];
  function sync() { syncs.forEach(f => f()); paint(); }

  /* ---- the one live timeline ---------------------------------------------- */
  const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__lwf = String(u).indexOf(".lwf") !== -1; this.__url = String(u);
    return this.__lwf ? undefined : open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    if (!this.__lwf) return send.apply(this, arguments);
    const key = this.__url.replace(/^.*\//, "").replace(/\.lwf$/, "").replace(/_pulse$/, "");
    const bin = atob(ANIM[key].lwf), b = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
    const self = this;
    setTimeout(() => {
      for (const [k, v] of [["readyState", 4], ["status", 200], ["response", b.buffer]])
        Object.defineProperty(self, k, { value: v, configurable: true });
      if (self.onreadystatechange) self.onreadystatechange();
    }, 0);
  };
  /* The player asks for its textures by file name; serve them from whichever bank holds
     them. Looking in one bank only left the second timeline's textures unresolved, so its
     load never completed and its canvas stayed unsized. */
  const BANK = {};
  for (const k of Object.keys(ANIM)) Object.assign(BANK, ANIM[k].img);
  const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "src");
  Object.defineProperty(HTMLImageElement.prototype, "src", {
    configurable: true,
    get() { return desc.get.call(this); },
    set(v) {
      const k = Object.keys(BANK).find(n => String(v).indexOf(n) !== -1);
      desc.set.call(this, k ? BANK[k] : v);
    }
  });

  LWF.useCanvasRenderer();
  const status = document.getElementById("status");

  /* One LWF unit is one layout unit; R oversamples the bitmap so a 2x tile stays crisp.
     (ox, oy) is where the timeline's own origin goes — a node draws its content from its
     local origin, which is its position minus its anchor in points, not the position. */
  function playAt(canvas, url, anime, ox, oy, span, done) {
    LWF.ResourceCache.get().loadLWF({
      lwf: url, prefix: "./", worker: false, stage: canvas,
      onload: lwf => {
        if (!lwf) { done(null); return; }
        lwf.rendererFactory.clearColor = null;
        const R = 2;
        canvas.width = canvas.height = span * R;
        canvas.style.left = pc(ox - span / 2, W);
        canvas.style.top = pc(H - oy - span / 2, H);
        canvas.style.width = pc(span, W);
        canvas.style.height = pc(span, H);
        /* Oversample by scaling the ROOT, never the attached movie: attachMovie returns
           the timeline's own instance, and moving or scaling it throws away whatever
           transform the animation was authored with. */
        lwf.rootMovie.moveTo(span * R / 2, span * R / 2);
        lwf.rootMovie.scaleTo(R, R);
        lwf.rootMovie.attachMovie(anime, "m");
        let prev = performance.now();
        (function step(now) {
          lwf.exec((now - prev) / 1000); lwf.render(); prev = now;
          requestAnimationFrame(step);
        })(prev);
        done(lwf);
      }
    });
  }

  /* fla_bg_effect goes through the layout applier: contentSize is its 20 x 20 box and its
     anchor is centred, so the timeline's origin lands on (x, y) — which is exactly the
     centre of the frame, (65, 80). Placing it on the node's position instead pushed the
     whole aura 10 units up and right, off the top of the tile. */
  /* fla_super_optimal_eff shares fla_bg_effect's box, so its origin is (65, 80) too, and
     its z of 3 puts it under both the LR aura and the artwork */
  const soeN = N.fla_super_optimal_eff;
  const seza = { lwf: null, play: () => {} };
  /* measured frame by frame: this aura reaches 179 units across, wider than the
     130 x 150 tile itself, so the canvas has to be larger than the tile */
  playAt(sezaBox, "super_optimal_eff.lwf", "ef_001", soeN.x, soeN.y, 200, lwf => {
    if (!lwf) return;
    seza.lwf = lwf;
    let cur = null;
    seza.play = name => {
      if (name === cur) return;
      cur = name;
      lwf.rootMovie.attachMovie(name, "m");
    };
    sync();
  });

  const bg = N.fla_bg_effect;
  playAt(effBox, "icon_rare_20000.lwf", bg.anime, bg.x, bg.y, 144,
         lwf => { if (!lwf) status.textContent = "l’animation n’a pas pu s’ouvrir"; });

  /* PartsAwakenStar builds its own node instead — no layout box, so its origin is its
     position — and sets it to image_star_evo_big's position offset by (15, 0). */
  const bigN = N.image_star_evo_big;
  playAt(pulseBox, "icon_rare_20000_pulse.lwf", "ef_002",
         bigN.x + bigN.w / 2 + 15, bigN.y + bigN.h / 2, 120,
         lwf => {
           status.textContent = lwf
             ? "ef_001 derrière l’illustration (LR) · ef_002 sur la grande étoile (éveil + max)"
             : "l’animation n’a pas pu s’ouvrir";
         });

  /* ---- the maquette, printed ---------------------------------------------- */
  const ORDER = ["img_bg", "fla_bg_effect", "image_thumb", "image_chara_bottom_base",
    "image_rare_ssr", "image_cha_icon_lock", "image_label_lv", "font_num",
    "font_num02", "font_percent", "image_star_evo", "image_icon_type"];
  const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  let code = '{ "w": <i>130</i>, "h": <i>150</i>,\n';
  for (const k of ORDER) {
    const n = N[k], bits = [];
    bits.push('"x": <i>' + n.x + '</i>', '"y": <i>' + n.y + '</i>');
    bits.push('"w": <i>' + n.w + '</i>', '"h": <i>' + n.h + '</i>');
    bits.push('"scale": <i>' + n.scale + '</i>');
    if (n.kerning !== undefined) bits.push('"kerning": <i>' + n.kerning + '</i>');
    if (n.italic) bits.push('"italic": true');
    bits.push('"type": "' + n.type + '"');
    if (n.font) bits.push('"font": "' + n.font + '"');
    if (n.anime) bits.push('"anime": "' + n.anime + '"');
    if (n.file) bits.push('"file": "' + esc(n.file) + '"');
    code += '  <b>"' + k + '"</b>: { ' + bits.join(", ") + ' },\n';
  }
  code += "  … }";
  document.getElementById("maquette").innerHTML = code;

  /* ---- the frame matrix ---------------------------------------------------- */
  const mx = document.getElementById("matrix");
  mx.appendChild(document.createElement("div"));
  for (const r of RLABEL) {
    const h = document.createElement("div"); h.className = "hd"; h.textContent = r;
    mx.appendChild(h);
  }
  for (const t of TYPES) {
    const rw = document.createElement("div"); rw.className = "rw"; rw.textContent = t.short;
    mx.appendChild(rw);
    RLABEL.forEach((r, i) => {
      const box = document.createElement("div");
      if (i >= 3) box.className = "same";
      const im = document.createElement("img");
      im.src = IMG.bg[t.i + "_" + Math.min(i, 3)];
      im.alt = "Cadre " + t.short + " " + r;
      im.loading = "lazy";
      box.appendChild(im); mx.appendChild(box);
    });
  }

  /* ---- the bands ----------------------------------------------------------- */
  const strip = document.getElementById("bands");
  for (const t of TYPES) for (const v of ["", "_on"]) {
    const fig = document.createElement("figure");
    const pl = document.createElement("div"); pl.className = "plate";
    const im = document.createElement("img");
    im.src = IMG.band[t.i + v]; im.alt = "Bandeau " + t.short; im.style.width = "100%";
    pl.appendChild(im);
    const cap = document.createElement("figcaption");
    cap.textContent = "bottom_0" + t.i + v;
    fig.append(pl, cap); strip.appendChild(fig);
  }

  document.getElementById("atlasShot").src = IMG.atlas;
  sync();
})();
