"""Render an LWF sequence to a filmstrip, offline, using the game's own player."""
import base64, io, json, os, re, subprocess, sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SHIM = '''
var A = JSON.parse(document.getElementById("A").textContent);
(function(){
  var open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u){ this.__lwf = String(u).indexOf(".lwf")!==-1;
    return this.__lwf ? undefined : open.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(){
    if(!this.__lwf) return send.apply(this, arguments);
    var bin = atob(A.lwf), b = new Uint8Array(bin.length);
    for (var i=0;i<bin.length;i++) b[i]=bin.charCodeAt(i);
    var self=this;
    setTimeout(function(){
      Object.defineProperty(self,"readyState",{value:4,configurable:true});
      Object.defineProperty(self,"status",{value:200,configurable:true});
      Object.defineProperty(self,"response",{value:b.buffer,configurable:true});
      if(self.onreadystatechange) self.onreadystatechange();
    },0);
  };
  var d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,"src");
  Object.defineProperty(HTMLImageElement.prototype,"src",{configurable:true,
    get:function(){return d.get.call(this);},
    set:function(v){
      var k = Object.keys(A.images).find(function(n){return String(v).indexOf(n)!==-1;});
      d.set.call(this, k ? A.images[k] : v);
    }});
})();
'''


def payload(lwf_path, image_dir):
    imgs = {f: "data:image/png;base64," + base64.b64encode(open(os.path.join(image_dir, f), 'rb').read()).decode()
            for f in sorted(os.listdir(image_dir)) if f.endswith('.png')}
    return {"lwf": base64.b64encode(open(lwf_path, 'rb').read()).decode(), "images": imgs}


def page(pay, player_js, driver):
    return ('<title>x</title><style>body{margin:0;background:#0b0c10}</style>'
            '<pre id="o" style="color:#ccc;font:12px monospace">…</pre><canvas id="strip"></canvas>'
            '<script id="A" type="application/json">' + json.dumps(pay) + '</script>'
            '<script>' + SHIM + '</script><script>' + player_js + '</script><script>' + driver + '</script>')


def render(html, out_png, size, budget=25000, tmp='work/_play.html'):
    io.open(tmp, 'w', encoding='utf-8').write(html)
    subprocess.run([CHROME, '--headless', '--disable-gpu', f'--screenshot={out_png}',
                    f'--window-size={size[0]},{size[1]}', '--hide-scrollbars',
                    f'--virtual-time-budget={budget}', 'file://' + os.path.abspath(tmp)],
                   capture_output=True)


def dump(html, budget=25000, tmp='work/_play.html'):
    io.open(tmp, 'w', encoding='utf-8').write(html)
    r = subprocess.run([CHROME, '--headless', '--disable-gpu', '--virtual-time-budget=%d' % budget,
                        '--dump-dom', 'file://' + os.path.abspath(tmp)], capture_output=True, text=True)
    m = re.search(r'<pre id="o"[^>]*>(.*?)</pre>', r.stdout, re.S)
    import html as H
    return H.unescape(m.group(1)) if m else ''
