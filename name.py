import time, gc, framebuf, struct
from machine import Pin, SoftSPI

TITULO    = "Gabriel Nascimento"
SUBTITULO = "Developer - Cybersecurity"
ESC_T   = 3      # tamanho do titulo (maior)
ESC_S   = 2      # tamanho do subtitulo (menor)
PASSO   = 2      # pixels por quadro (menor = mais lento e legivel)
GAP     = 30     # espaco vazio antes do texto reaparecer
ESPACO  = 10     # espaco entre titulo e subtitulo
DIRECAO = 1      # 1 = anda para a direita, -1 = anda para a esquerda

PRETO, BRANCO, AZUL = 0x0000, 0xFFFF, 0x001F
PARES = [(PRETO, BRANCO), (BRANCO, PRETO), (BRANCO, AZUL), (AZUL, BRANCO)]  # (fundo, fonte)

# (MADCTL, xoff, yoff, largura, altura)
ROTS = [
    (0x60, 40, 53, 240, 135),   # paisagem
    (0xC0, 53, 40, 135, 240),   # retrato
    (0xA0, 40, 52, 240, 135),   # paisagem invertida
    (0x00, 52, 40, 135, 240),   # retrato invertido
]

BTN_GIRAR = Pin(35, Pin.IN)               # GPIO 35 (pull-up externo na placa)
BTN_COR   = Pin(0,  Pin.IN, Pin.PULL_UP)  # GPIO 0 (BOOT)

cs  = Pin(5,  Pin.OUT, value=1)
dc  = Pin(16, Pin.OUT, value=0)
rst = Pin(23, Pin.OUT, value=1)
bl  = Pin(4,  Pin.OUT, value=0)
spi = SoftSPI(baudrate=10000000, polarity=0, phase=0,
              sck=Pin(18), mosi=Pin(19), miso=Pin(39))

XOFF = YOFF = 0
W, H = 240, 135

def cmd(c, d=None):
    dc(0); cs(0); spi.write(bytes([c])); cs(1)
    if d is not None:
        dc(1); cs(0); spi.write(d); cs(1)

def janela(x0, y0, x1, y1):
    cmd(0x2A, struct.pack(">HH", x0 + XOFF, x1 + XOFF))
    cmd(0x2B, struct.pack(">HH", y0 + YOFF, y1 + YOFF))
    cmd(0x2C)

def init():
    rst(1); time.sleep_ms(50); rst(0); time.sleep_ms(100); rst(1); time.sleep_ms(200)
    cmd(0x01); time.sleep_ms(200)
    cmd(0x11); time.sleep_ms(200)
    cmd(0x3A, b'\x55')
    cmd(0x21)
    cmd(0x13); time.sleep_ms(20)
    cmd(0x29); time.sleep_ms(200)
    bl(1)

def sw(c):  # troca bytes para o framebuf
    return ((c & 0xFF) << 8) | (c >> 8)

def pintar_fundo(bg):
    janela(0, 0, W - 1, H - 1)
    linha = bytes([bg >> 8, bg & 0xFF]) * W
    dc(1); cs(0)
    for _ in range(H):
        spi.write(linha)
    cs(1)

class Faixa:
    def __init__(self, texto, esc):
        self.esc = esc
        self.n = len(texto)
        self.P = self.n * 8 * esc + GAP      # periodo do loop
        self.h = 8 * esc
        self.buf = bytearray(self.P * self.h * 2)
        self.mv = memoryview(self.buf)
        self.fb = framebuf.FrameBuffer(self.buf, self.P, self.h, framebuf.RGB565)
        self.mono = framebuf.FrameBuffer(bytearray(self.n * 8), self.n * 8, 8,
                                         framebuf.MONO_HLSB)
        self.mono.text(texto, 0, 0, 1)
        self.off = 0                         # <<< aqui fica "= 0"

    def pintar(self, bg, fg):
        self.fb.fill(sw(bg))
        c = sw(fg); e = self.esc
        for y in range(8):
            for x in range(self.n * 8):
                if self.mono.pixel(x, y):
                    self.fb.fill_rect(x * e, y * e, e, e, c)

    def mostrar(self, y):
        P = self.P; off = self.off
        primeiro = min(W, P - off)
        janela(0, y, W - 1, y + self.h - 1)
        dc(1); cs(0)
        for r in range(self.h):
            base = r * P * 2
            spi.write(self.mv[base + off * 2: base + (off + primeiro) * 2])
            if primeiro < W:                       # volta ao inicio (Pac-Man)
                spi.write(self.mv[base: base + (W - primeiro) * 2])
        cs(1)
        self.off = (off - DIRECAO * PASSO) % P     # <<< a linha nova fica AQUI

class Botao:
    def __init__(self, pin):
        self.pin = pin; self.ant = 1; self.t = 0
    def clicou(self):
        v = self.pin.value(); agora = time.ticks_ms(); r = False
        if v == 0 and self.ant == 1 and time.ticks_diff(agora, self.t) > 200:
            r = True; self.t = agora
        self.ant = v
        return r

init()
titulo = Faixa(TITULO, ESC_T)
sub = Faixa(SUBTITULO, ESC_S)
gc.collect()

ir = 0; ic = 0; yt = ys = 0

def aplicar():
    global XOFF, YOFF, W, H, yt, ys
    madctl, XOFF, YOFF, W, H = ROTS[ir]
    cmd(0x36, bytes([madctl]))
    total = titulo.h + ESPACO + sub.h
    yt = (H - total) // 2
    ys = yt + titulo.h + ESPACO
    bg, fg = PARES[ic]
    titulo.pintar(bg, fg)
    sub.pintar(bg, fg)
    pintar_fundo(bg)

aplicar()
b_girar = Botao(BTN_GIRAR)
b_cor = Botao(BTN_COR)

while True:
    if b_girar.clicou():
        ir = (ir + 1) % 4
        aplicar()
    if b_cor.clicou():
        ic = (ic + 1) % 4
        aplicar()
    titulo.mostrar(yt)
    sub.mostrar(ys)