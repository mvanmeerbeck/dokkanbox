(function () {
  const A = JSON.parse(document.getElementById("anims").textContent);
  let current = null;

  const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__lwf = String(u).indexOf(".lwf") !== -1; this.__url = String(u);
    return this.__lwf ? undefined : open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    if (!this.__lwf) return send.apply(this, arguments);
    const key = this.__url.replace(/^.*\//, "").replace(/\.lwf$/, "");
    const bin = atob(A[key].lwf), b = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
    const self = this;
    setTimeout(() => {
      for (const [k, v] of [["readyState", 4], ["status", 200], ["response", b.buffer]])
        Object.defineProperty(self, k, { value: v, configurable: true });
      if (self.onreadystatechange) self.onreadystatechange();
    }, 0);
  };
  const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "src");
  Object.defineProperty(HTMLImageElement.prototype, "src", {
    configurable: true,
    get() { return desc.get.call(this); },
    set(v) {
      const bank = current && A[current] ? A[current].img : {};
      const k = Object.keys(bank).find(n => String(v).indexOf(n) !== -1);
      desc.set.call(this, k ? bank[k] : v);
    }
  });

  LWF.useCanvasRenderer();
  const SIZE = 224;

  /* Each piece is played one after the other: the texture shim answers for whichever
     animation is loading, so two must never load at once. */
  const queue = [];
  function pump() {
    const job = queue.shift();
    if (!job) return;
    const { file, seq, canvas } = job;
    current = file;
    LWF.ResourceCache.get().loadLWF({
      lwf: file + ".lwf", prefix: "./", worker: false, stage: canvas,
      onload: lwf => {
        pump();
        if (!lwf) return;
        lwf.rendererFactory.clearColor = null;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        const m = lwf.rootMovie.attachMovie(seq, "show");
        let scale = 1, reach = 0, seen = 0;
        if (m) { m.moveTo(SIZE / 2, SIZE / 2); m.scaleTo(scale, scale); }
        let prev = performance.now();
        (function step(now) {
          lwf.exec((now - prev) / 1000); lwf.render(); prev = now;
          if (m && seen++ < 400) {                       // fit live: textures arrive late
            const d = ctx.getImageData(0, 0, SIZE, SIZE).data;
            let x0 = SIZE, x1 = -1, y0 = SIZE, y1 = -1;
            for (let y = 0; y < SIZE; y += 4) for (let x = 0; x < SIZE; x += 4) {
              if (d[(y * SIZE + x) * 4 + 3] > 12) {
                if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
              }
            }
            if (x1 >= 0) {
              const r = (Math.max(x1 - x0, y1 - y0) + 6) / scale;
              if (r > reach * 1.02) {
                reach = r;
                const s2 = Math.min(1, (SIZE * 0.9) / reach);
                if (Math.abs(s2 - scale) > 0.015) { scale = s2; m.scaleTo(scale, scale); }
              }
            }
          }
          requestAnimationFrame(step);
        })(prev);
      }
    });
  }

  const PIECES = JSON.parse(document.getElementById("pieces").textContent);
  const host = document.getElementById("cards");
  for (const p of PIECES) {
    const card = document.createElement("div"); card.className = "card";
    const screen = document.createElement("div"); screen.className = "screen";
    const cv = document.createElement("canvas"); cv.width = cv.height = SIZE;
    screen.appendChild(cv);
    const body = document.createElement("div"); body.className = "body";
    body.innerHTML =
      '<span class="tag' + (p.app ? ' app' : '') + '">' + (p.app ? 'application' : 'serveur d’images') + '</span>' +
      '<h3>' + p.title + '</h3>' +
      '<div class="src">' + p.file + ' · ' + p.seq + '</div>' +
      '<dl><dt>durée</dt><dd>' + p.dur + '</dd>' +
      '<dt>images</dt><dd>' + p.frames + ' à ' + p.fps + ' i/s</dd></dl>';
    card.append(screen, body); host.appendChild(card);
    queue.push({ file: p.file, seq: p.seq, canvas: cv });
  }
  pump();
})();
