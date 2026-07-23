const GLYPHS = "アイウエオカキクケコサシスセソ01234567890<>/[]{}#$%&";

export function startMatrixRain(canvas) {
  const ctx = canvas.getContext("2d");
  let columns, drops;
  const fontSize = 16;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    columns = Math.floor(canvas.width / fontSize);
    drops = new Array(columns).fill(0).map(() => Math.random() * -100);
  }

  function frame() {
    ctx.fillStyle = "rgba(3, 8, 5, 0.08)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = `${fontSize}px monospace`;

    for (let i = 0; i < columns; i++) {
      const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      const y = drops[i] * fontSize;
      ctx.fillStyle = Math.random() > 0.97 ? "#c8ffe0" : "rgba(57, 255, 156, 0.55)";
      ctx.fillText(glyph, i * fontSize, y);

      if (y > canvas.height && Math.random() > 0.975) drops[i] = 0;
      drops[i] += 0.6 + Math.random() * 0.4;
    }
    requestAnimationFrame(frame);
  }

  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(frame);
}
