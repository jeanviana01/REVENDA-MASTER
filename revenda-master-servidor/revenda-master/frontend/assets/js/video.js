/* Vídeo da página inicial: respeita "reduzir movimento" e toca no primeiro toque se o autoplay for bloqueado. */
(function () {
  "use strict";
  var v = document.getElementById("video-onix");
  if (!v) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { v.removeAttribute("autoplay"); v.pause(); return; }
  function tocar() { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
  v.addEventListener("loadeddata", tocar);
  ["click", "touchstart", "keydown"].forEach(function (e) { document.addEventListener(e, tocar, { once: true, passive: true }); });
})();
