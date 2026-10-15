from machine import Pin, SPI, SoftI2C
import struct
import time
import math
import random

try:
    import esp32
except ImportError:
    esp32 = None

TEMP_QUENTE = 30.0
TEMP_FRIO = 20.0
HISTERESE = 2.0
CLIMA_ESTAVEL_S = 5
PERIODO_CLIMA_S = 30
TEMP_OFFSET = 0.0
TEMP_FORCADA = None

I2C_SDA = 42
I2C_SCL = 41
BOTAO_SIMULA_SACUDIDA = True
LIMIAR_G = 0.7
LIMIAR_GIRO = 200.0
IMPACTOS = 1
JANELA_MS = 1000
TONTO_MS = 3000
PARADO_MS = 2000
MOV_G = 0.12
MOV_GIRO = 25.0
PUPILAS = True
TINGIR_CLIMA = False
FPS = 20


class Tela:
    LARGURA = 240
    ALTURA = 135
    ROT = {1: (0x60, 40, 53), 3: (0xA0, 40, 52)}

    def __init__(self, rotacao=1):
        madctl, self.xoff, self.yoff = self.ROT[rotacao]
        Pin(21, Pin.OUT, value=1)
        time.sleep_ms(50)
        self.spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0,
                       sck=Pin(36), mosi=Pin(35), miso=Pin(37))
        self.cs = Pin(7, Pin.OUT, value=1)
        self.dc = Pin(39, Pin.OUT, value=0)
        self.rst = Pin(40, Pin.OUT, value=1)
        self.bl = Pin(45, Pin.OUT, value=0)

        self.rst(1); time.sleep_ms(10)
        self.rst(0); time.sleep_ms(20)
        self.rst(1); time.sleep_ms(150)
        self.cmd(0x01); time.sleep_ms(150)
        self.cmd(0x11); time.sleep_ms(120)
        self.cmd(0x3A, b'\x55')
        self.cmd(0x36, bytes([madctl]))
        self.cmd(0x21)
        self.cmd(0x13); time.sleep_ms(10)
        self.cmd(0x29); time.sleep_ms(100)
        self.fill(0x0000)
        self.bl(1)

    def cmd(self, c, dados=b''):
        self.cs(0); self.dc(0)
        self.spi.write(bytes([c]))
        if dados:
            self.dc(1)
            self.spi.write(dados)
        self.cs(1)

    def janela(self, x0, y0, x1, y1):
        self.cmd(0x2A, struct.pack('>HH', x0 + self.xoff, x1 + self.xoff))
        self.cmd(0x2B, struct.pack('>HH', y0 + self.yoff, y1 + self.yoff))
        self.cmd(0x2C)

    def bloco(self, x0, y0, x1, y1, dados):
        self.janela(x0, y0, x1, y1)
        self.cs(0); self.dc(1)
        self.spi.write(dados)
        self.cs(1)

    def fill(self, cor):
        linha = struct.pack('>H', cor) * self.LARGURA
        self.janela(0, 0, self.LARGURA - 1, self.ALTURA - 1)
        self.cs(0); self.dc(1)
        for _ in range(self.ALTURA):
            self.spi.write(linha)
        self.cs(1)


CEL = 3
COLS = 80
LINS = 45
DT = 1.0 / FPS

NORMAL = (0x0000, 0x021F, 0x04DF, 0x2FFF, 0xAFFF, 0x5FFF, 0xF810, 0xFFE0, 0xFD20, 0xCFFF)
QUENTE = (0x0000, 0x9800, 0xF800, 0xFD20, 0xFFE0, 0x5FFF, 0xF810, 0xFFE0, 0xFD20, 0xCFFF)
FRIO   = (0x0000, 0x0010, 0x041F, 0xAFFF, 0xFFFF, 0xFFFF, 0xF810, 0x9FFF, 0xFD20, 0xCFFF)
FROST_T = 9.5
FROST = None

ZERO2 = b'\x00\x00'
ZERO_LINHA = bytes(COLS * CEL * 2)

EIXO_Y = 15.5
EYE_CX = 17.5
EYE_RX = 9.5
EYE_RY = 11.0
BOCA_CX = 40.0
BOCA_W = 10.0


class Quadro:
    def __init__(self):
        self.idx = [bytearray(COLS) for _ in range(LINS)]

    def limpar(self):
        z = bytes(COLS)
        for r in self.idx:
            r[:] = z

    def pixel(self, x, y, c):
        x = int(x + 0.5)
        y = int(y + 0.5)
        if 0 <= x < COLS and 0 <= y < LINS:
            self.idx[y][x] = c

    def poligono(self, pts, t1=1, t2=2, t3=3):
        n = len(pts)
        ymin = min([p[1] for p in pts])
        ymax = max([p[1] for p in pts])
        top = int(math.ceil(ymin - 0.5))
        bot = int(math.floor(ymax - 0.5))
        for gy in range(max(0, top), min(LINS - 1, bot) + 1):
            cy = gy + 0.5
            xs = []
            j = n - 1
            for i in range(n):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > cy) != (yj > cy):
                    xs.append(xi + (cy - yi) * (xj - xi) / (yj - yi))
                j = i
            xs.sort()
            if gy == top or gy == bot:
                vt = 1
            elif gy == top + 1 or gy == bot - 1:
                vt = 2
            else:
                vt = 3
            row = self.idx[gy]
            for k in range(0, len(xs) - 1, 2):
                ga = int(math.ceil(xs[k] - 0.5))
                gb = int(math.floor(xs[k + 1] - 0.5))
                for gx in range(max(ga, 0), min(gb, COLS - 1) + 1):
                    if gx == ga or gx == gb:
                        h = 1
                    elif gx == ga + 1 or gx == gb - 1:
                        h = 2
                    else:
                        h = 3
                    t = h if h < vt else vt
                    row[gx] = t1 if t == 1 else (t2 if t == 2 else t3)

    def elipse(self, cx, cy, rx, ry, cor):
        ya = int(math.ceil(cy - ry - 0.5))
        yb = int(math.floor(cy + ry - 0.5))
        for gy in range(max(0, ya), min(LINS - 1, yb) + 1):
            t = (gy + 0.5 - cy) / ry
            if t * t > 1:
                continue
            w = rx * math.sqrt(1 - t * t)
            ga = int(math.ceil(cx - w - 0.5))
            gb = int(math.floor(cx + w - 0.5))
            row = self.idx[gy]
            for gx in range(max(0, ga), min(COLS - 1, gb) + 1):
                row[gx] = cor


class Renderizador:
    def __init__(self, tela):
        self.tela = tela
        self.prev = [None] * LINS
        self.lut = []
        self.tema(NORMAL)

    def tema(self, cores):
        self.lut = [struct.pack('>H', c) * (CEL - 1) + ZERO2 for c in cores]
        self.prev = [None] * LINS

    def mostrar(self, q):
        lut = self.lut
        gy = 0
        while gy < LINS:
            if q.idx[gy] == self.prev[gy]:
                gy += 1
                continue
            ini = gy
            partes = []
            while gy < LINS and len(partes) < 9 and q.idx[gy] != self.prev[gy]:
                linha = b''.join([lut[i] for i in q.idx[gy]])
                partes.append(linha * (CEL - 1) + ZERO_LINHA)
                self.prev[gy] = bytes(q.idx[gy])
                gy += 1
            self.tela.bloco(0, ini * CEL, COLS * CEL - 1, gy * CEL - 1, b''.join(partes))


def pontos_olho(espelho, dx, dy, ab, inc, ca=0.0):
    ab = max(ab, 0.2)
    cx = (COLS - EYE_CX if espelho else EYE_CX) + dx
    cy = EIXO_Y + dy
    ry = EYE_RY * ab
    sinal = -1.0 if espelho else 1.0
    out = []
    for k in range(20):
        a = 6.2832 * k / 20
        px = EYE_RX * math.cos(a)
        py = ry * math.sin(a)
        if py < 0:
            if inc > 0:
                lid = -ry + inc * 1.6 * (sinal * px / EYE_RX + 1.0) / 2.0
                if lid > py:
                    py = lid
            if ca > 0:
                lid = -ry + ca * 2.0 * ry
                if lid > py:
                    py = lid
        elif inc < 0:
            lid = ry + inc * 1.5
            if lid < py:
                py = lid
        out.append((cx + px, cy + py))
    return out


def pupila(q, espelho, dx, dy, ab, ox, oy):
    if ab < 0.55:
        return
    h = min(ab, 1.0)
    cx = (COLS - EYE_CX if espelho else EYE_CX) + dx + ox * 1.4
    cy = EIXO_Y + dy + oy * 1.4
    q.elipse(cx, cy, 4.4, 4.4 * h, 0)
    q.pixel(cx - 2, cy - 2 * h, 4)
    q.pixel(cx - 1, cy - 2 * h, 4)
    q.pixel(cx - 2, cy - 1 * h, 4)
    q.pixel(cx - 1, cy - 1 * h, 4)


def geom_boca(cx, s, ab, dy):
    u = (cx - BOCA_CX) / BOCA_W
    u2 = u * u
    topo = 33.0 - 3.6 * s * u2 + dy
    esp = (2.4 * min(ab, 1.0) + 30.0 * max(ab - 1.0, 0.0)) * (1.0 - 0.5 * u2)
    return topo, topo + esp


def boca(q, s=1.0, ab=1.0, dentes=True, fase=0, dx=0, dy=0, onda=0.0, fase_onda=0.0):
    for gx in range(COLS):
        cx = gx + 0.5 - dx
        u = (cx - BOCA_CX) / BOCA_W
        if u > 1 or u < -1:
            continue
        topo, base = geom_boca(cx, s, ab, dy)
        if onda:
            o = onda * math.sin(gx * 0.45 + fase_onda)
            topo += o
            base += o
        ya = int(math.ceil(topo - 0.5))
        yb = int(math.floor(base - 0.5))
        if yb < ya:
            yb = ya
        n = yb - ya + 1
        ponta = abs(u) > 0.9
        for r in range(ya, yb + 1):
            if r < 0 or r >= LINS:
                continue
            pt = r - ya
            pb = yb - r
            if n <= 5 or pt < 2 or pb < 2:
                c = 2 if (n > 3 and (pt == 0 or pb == 0)) else 3
                if ponta and c > 1:
                    c -= 1
                q.idx[r][gx] = c
        if dentes and n >= 7:
            c = n / 2.0 - 1
            f = abs((gx + fase) % 8 - 4)
            for k in range(int(c * (1 - f / 4.0))):
                r = ya + 2 + k
                if 0 <= r < LINS and r <= yb - 2:
                    q.idx[r][gx] = 4
            f2 = abs((gx + fase + 4) % 8 - 4)
            for k in range(int(c * (1 - f2 / 4.0))):
                r = yb - 2 - k
                if 0 <= r < LINS and r >= ya + 2:
                    q.idx[r][gx] = 4


def lingua(q, cx, s=1.0, ab=1.0, dy=0, comp=6):
    topo, base = geom_boca(cx, s, ab, dy)
    q.elipse(cx, base, 3.5, comp, 6)


def boca_o(q, rx, ry, dx=0, dy=0):
    q.elipse(40 + dx, 35 + dy, rx + 1, ry + 1, 2)
    q.elipse(40 + dx, 35 + dy, rx, ry, 3)
    q.elipse(40 + dx, 35 + dy, rx - 2, ry - 2, 0)


def rosto(q, dx=0, dy=0, ab_e=1.0, ab_d=1.0, inc=0.0, ox=0, oy=0,
          s=1.0, ab_b=1.0, dentes=True, fase=0, dy_b=0, onda=0.0, fase_onda=0.0,
          com_olhos=True, com_boca=True, ca=0.0):
    q.limpar()
    if com_olhos:
        ex = dx if PUPILAS else dx + ox
        ey = dy if PUPILAS else dy + oy
        q.poligono(pontos_olho(False, ex, ey, ab_e, inc, ca))
        q.poligono(pontos_olho(True, ex, ey, ab_d, inc, ca))
        if PUPILAS:
            pupila(q, False, dx, dy, ab_e, ox, oy)
            pupila(q, True, dx, dy, ab_d, ox, oy)
    if com_boca:
        boca(q, s, ab_b, dentes, fase, dx, dy + dy_b, onda, fase_onda)


def estrela(q, x, y):
    q.pixel(x, y, 4)
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q.pixel(x + ax, y + ay, 7)


def gota(q, x, y):
    q.pixel(x, y, 5)
    for ax in (-1, 0, 1):
        q.pixel(x + ax, y + 1, 5)
        q.pixel(x + ax, y + 2, 5)
    q.pixel(x, y + 3, 5)


def floco(q, x, y):
    q.pixel(x, y, 5)
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q.pixel(x + ax, y + ay, 5)


Z_GLIFO = ("#####", "...#.", "..#..", ".#...", "#####")


def letra_z(q, x, y):
    for j, lin in enumerate(Z_GLIFO):
        for i, ch in enumerate(lin):
            if ch == "#":
                q.pixel(x + i, y + j, 4)


def sol(q, cx, cy, r, t):
    if r < 1.0:
        return
    q.elipse(cx, cy, r, r, 8)
    q.elipse(cx, cy, max(r - 1.5, 0.6), max(r - 1.5, 0.6), 7)
    esc = r / 4.0
    for k in range(8):
        ang = k * 0.7854 + t * 0.12
        comp = (3.0 + 2.0 * math.sin(t * 0.5 + k)) * esc
        d = r + 1.5
        while d < r + 1.5 + comp:
            q.pixel(cx + d * math.cos(ang), cy + d * math.sin(ang), 7)
            d += 1.0


def montar_frost():
    global FROST
    lista = []
    for y in range(LINS):
        ey = min(y, LINS - 1 - y)
        for x in range(COLS):
            ex = min(x, COLS - 1 - x)
            m = min(ex, ey) + 0.25 * max(ex, ey) + random.random() * 3.0
            if m < FROST_T:
                lista.append((m, x, y))
    lista.sort()
    FROST = lista


def seq(*gens):
    for g in gens:
        yield from g


class Estado:
    def __init__(self, tela):
        self.tela = tela
        self.q = Quadro()
        self.render = Renderizador(tela)
        self.tonto_ate = 0
        self.parado = False


def anim_piscar(S):
    q = S.q
    for _ in range(random.choice((1, 1, 2))):
        for a in (1.0, 0.6, 0.2, 0.2, 0.6, 1.0):
            rosto(q, ab_e=a, ab_d=a)
            yield
        for _ in range(3):
            rosto(q)
            yield


def anim_olhar(S):
    q = S.q
    for ox, oy, n in ((-3, 0, 12), (3, 0, 12), (0, -2, 8), (0, 0, 4)):
        for _ in range(n):
            rosto(q, ox=ox, oy=oy)
            yield


def anim_piscadela(S):
    q = S.q
    for i in range(22):
        rosto(q, ab_d=0.2 if 3 <= i <= 17 else 1.0, s=1.3 if 3 <= i <= 17 else 1.0)
        if 8 <= i <= 16 and (i // 2) % 2 == 0:
            estrela(q, 34, 38)
        yield


def anim_risada(S):
    q = S.q
    for i in range(44):
        dy = 1 if (i // 2) % 2 else -1
        rosto(q, dy=dy, ab_e=0.45, ab_d=0.45, inc=-1, s=1.2, ab_b=1.2, dy_b=-2)
        gota(q, 12, 24 + (i * 0.8) % 12)
        gota(q, 68, 24 + (i * 0.8 + 6) % 12)
        yield


def anim_lingua(S):
    q = S.q
    for i in range(44):
        cx = 40 + 8 * math.sin(i * 0.4)
        rosto(q, ab_e=0.8, ab_d=0.8, inc=2, s=1.1, ab_b=0.9, dy_b=-4)
        lingua(q, cx, 1.1, 0.9, -4, 4)
        yield


def anim_surpreso(S):
    q = S.q
    for i in range(26):
        k = min(i, 4) / 4.0
        a = 1.0 + 0.4 * k
        rosto(q, ab_e=a, ab_d=a, com_boca=False)
        boca_o(q, 4 + 3 * k, 4 + 4 * k, 0, -1)
        yield


def anim_bravo(S):
    q = S.q
    for i in range(32):
        dx = 1 if (i // 2) % 2 else -1
        rosto(q, dx=dx, ab_e=0.9, ab_d=0.9, inc=4, s=1.3, ab_b=0.8)
        yield


def anim_brilho(S):
    q = S.q
    px = random.choice((28, 36, 44, 52))
    for i in range(26):
        rosto(q)
        if (i // 3) % 2 == 0:
            estrela(q, px, 38)
        yield


def anim_acordar(S):
    q = S.q
    print("acordou")
    for a in (0.3, 0.6, 1.0, 1.25, 1.0):
        rosto(q, ab_e=a, ab_d=a)
        yield


def anim_dormir(S):
    q = S.q
    S.render.tema(NORMAL)
    print("dormindo")
    i = 0
    while S.parado:
        rosto(q, dy=2, ab_e=0.2, ab_d=0.2, s=0.2, ab_b=0.35 + 0.1 * math.sin(i * 0.25),
              dentes=False)
        for k in range(3):
            letra_z(q, 54 + k * 5, 28 - ((i * 0.5 + k * 12) % 28))
        i += 1
        yield
    yield from anim_acordar(S)


def anim_tonto(S):
    q = S.q
    S.render.tema(NORMAL)
    i = 0
    while time.ticks_diff(S.tonto_ate, time.ticks_ms()) > 0:
        dx = int(round(2 * math.sin(i * 0.35)))
        rosto(q, dx=dx, com_olhos=False, s=0.3, ab_b=0.6, dentes=False,
              onda=1.6, fase_onda=i * 0.5)
        for e in (0, 1):
            cx = 17.5 + e * 45
            sentido = 1 if e == 0 else -1
            a = 0.0
            while True:
                r = 0.5 * a
                if r > 7.0:
                    break
                ang = sentido * (a + i * 0.5)
                q.pixel(cx + r * math.cos(ang) + dx, EIXO_Y + r * math.sin(ang) * 0.85,
                        4 if r < 2 else 3)
                a += 0.8 / max(r, 1.5)
        for k in range(4):
            a = i * 0.25 + k * 1.57
            estrela(q, 40 + 24 * math.cos(a) + dx, 5 + 3 * math.sin(a))
        i += 1
        yield


def anim_quente(S):
    q = S.q
    S.render.tema(QUENTE if TINGIR_CLIMA else NORMAL)
    gotas = [[6, 12.0, 8], [40, 2.0, 6], [74, 14.0, 9]]
    for i in range(160):
        if i < 30:
            p = i / 30.0
        elif i < 130:
            p = 1.0
        else:
            p = 1.0 - (i - 130) / 30.0
        dx = 1.2 * p * math.sin(i * 0.11)
        dy = 3.0 * p + 0.6 * p * math.sin(i * 0.15)
        pant = 1.0 + p * (0.12 + 0.08 * math.sin(i * 0.9))
        ab = 1.0 - 0.1 * p
        s = 1.0 - 0.8 * p
        rosto(q, dx=dx, dy=dy, ab_e=ab, ab_d=ab, ca=0.45 * p, oy=1.5 * p,
              s=s, ab_b=pant, dentes=False, dy_b=-3.0 * p)
        if pant > 1.06:
            lingua(q, 40 + dx, s, pant, dy - 3.0 * p, 2.5 + 6.0 * (pant - 1.0))
        sol(q, 74, 5, 4.0 * p, i)
        if p > 0.2:
            for g in gotas:
                g[1] += g[2] * DT
                if g[1] > LINS - 3:
                    g[1] = 4.0 + random.random() * 6
                gota(q, g[0], g[1])
        yield


def anim_frio(S):
    q = S.q
    S.render.tema(FRIO if TINGIR_CLIMA else NORMAL)
    if FROST is None:
        montar_frost()
    n = len(FROST)
    k = 0
    flocos = [[random.randint(1, COLS - 2), random.randint(-LINS, 0), 6 + random.randint(0, 6),
               random.randint(0, 2), random.random() * 6.28] for _ in range(14)]
    for i in range(140):
        if i < 30:
            cresc = 0.6 * i / 30.0
            trem = i / 30.0
        elif i < 110:
            cresc = 0.6 + 0.4 * (i - 30) / 80.0
            trem = 1.0
        else:
            cresc = 1.0 - (i - 110) / 30.0
            trem = cresc
        lim = FROST_T * cresc
        while k < n and FROST[k][0] < lim:
            k += 1
        while k > 0 and FROST[k - 1][0] >= lim:
            k -= 1
        dx = random.choice((-1, 0, 1)) if trem > 0.3 else 0
        dy = random.choice((0, 0, 1)) if trem > 0.6 else 0
        ab_b = 1.0 if trem < 0.5 else (1.18 if i % 2 else 0.95)
        ab = 1.0 - 0.2 * trem
        rosto(q, dx=dx, dy=dy, ab_e=ab, ab_d=ab, inc=trem,
              s=1.0 - 2.3 * trem, ab_b=ab_b, dy_b=trem)
        for j in range(k):
            m, x, y = FROST[j]
            q.idx[y][x] = 4 if m > lim - 1.5 else 9
        for f in flocos:
            f[1] += f[2] * DT
            if f[1] > LINS + 1 and i < 110:
                f[1] = -2
                f[0] = random.randint(1, COLS - 2)
            fx = f[0] + 2.0 * math.sin(i * 0.12 + f[4])
            if f[3] == 0:
                floco(q, fx, f[1])
            else:
                q.pixel(fx, f[1], 4)
        yield


def anim_alivio(S):
    q = S.q
    S.render.tema(NORMAL)
    for i in range(40):
        rosto(q, dy=1 if (i // 5) % 2 else 0, ab_e=0.45, ab_d=0.45, inc=-1.2, s=1.5)
        if (i // 4) % 2 == 0:
            estrela(q, 9, 36)
            estrela(q, 71, 32)
        yield


IDLE = ((anim_piscar, 5), (anim_olhar, 3), (anim_piscadela, 2), (anim_risada, 2),
        (anim_lingua, 2), (anim_surpreso, 2), (anim_bravo, 1), (anim_brilho, 2))


def escolher(ultima):
    total = 0
    for f, p in IDLE:
        if f is not ultima:
            total += p
    r = random.randint(1, total)
    for f, p in IDLE:
        if f is ultima:
            continue
        r -= p
        if r <= 0:
            return f
    return anim_piscar


class Sensor:
    def __init__(self):
        self.i2c = None
        self.imu = None
        self.bmp = None
        self.cal = None
        self.temp = None
        self.prox_temp = time.ticks_ms()
        self.ult_mov = time.ticks_ms()
        self.impactos = []
        self.acima = False
        self.max_g = 0.0
        self.max_giro = 0.0
        self.botao = Pin(0, Pin.IN, Pin.PULL_UP) if BOTAO_SIMULA_SACUDIDA else None
        try:
            self.i2c = SoftI2C(scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
            achados = self.i2c.scan()
            print("I2C encontrou:", [hex(a) for a in achados])
            for a in (0x6B, 0x6A):
                if a in achados and self.i2c.readfrom_mem(a, 0x00, 1)[0] == 0x05:
                    self.imu = a
                    break
            for a in (0x77, 0x76):
                if a in achados and self.i2c.readfrom_mem(a, 0xD0, 1)[0] in (0x56, 0x57, 0x58, 0x60):
                    self.bmp = a
                    break
            if self.imu is not None:
                self.i2c.writeto_mem(self.imu, 0x02, b'\x40')
                self.i2c.writeto_mem(self.imu, 0x03, b'\x25')
                self.i2c.writeto_mem(self.imu, 0x04, b'\x55')
                self.i2c.writeto_mem(self.imu, 0x08, b'\x03')
            if self.bmp is not None:
                self.cal = struct.unpack('<Hhh', self.i2c.readfrom_mem(self.bmp, 0x88, 6))
                self.i2c.writeto_mem(self.bmp, 0xF5, b'\x00')
                self.i2c.writeto_mem(self.bmp, 0xF4, b'\x27')
            time.sleep_ms(50)
        except Exception as e:
            print("I2C indisponivel:", e)
            self.imu = None
            self.bmp = None
        if self.imu is not None:
            print("QMI8658C ok (giroscopio + acelerometro)")
        else:
            print("Sem sensor de movimento. Use o botao BOOT para simular a sacudida.")
        if self.bmp is not None:
            print("BMP280 ok (temperatura)")
        else:
            print("Sem BMP280: usando a temperatura do chip.")

    def parado(self, agora):
        return self.imu is not None and time.ticks_diff(agora, self.ult_mov) >= PARADO_MS

    def ler(self):
        agora = time.ticks_ms()
        temp = None
        sac = False
        if self.imu is not None:
            try:
                d = self.i2c.readfrom_mem(self.imu, 0x35, 12)
                ax, ay, az, gx, gy, gz = struct.unpack('<hhhhhh', d)
                g = math.sqrt(ax * ax + ay * ay + az * az) / 4096.0
                giro = math.sqrt(gx * gx + gy * gy + gz * gz) / 64.0
                desvio = abs(g - 1.0)
                if desvio > self.max_g:
                    self.max_g = desvio
                if giro > self.max_giro:
                    self.max_giro = giro
                if desvio > MOV_G or giro > MOV_GIRO:
                    self.ult_mov = agora
                acima = desvio > LIMIAR_G
                if acima and not self.acima:
                    self.impactos.append(agora)
                self.acima = acima
                self.impactos = [x for x in self.impactos
                                 if time.ticks_diff(agora, x) < JANELA_MS]
                if len(self.impactos) >= IMPACTOS or giro > LIMIAR_GIRO:
                    sac = True
                    self.impactos = []
            except Exception:
                self.ult_mov = agora
        if self.bmp is not None:
            if time.ticks_diff(agora, self.prox_temp) >= 0:
                self.prox_temp = time.ticks_add(agora, 1000)
                try:
                    d = self.i2c.readfrom_mem(self.bmp, 0xFA, 3)
                    adc = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
                    if adc != 0x80000:
                        t1, t2, t3 = self.cal
                        v1 = (adc / 16384.0 - t1 / 1024.0) * t2
                        v2 = (adc / 131072.0 - t1 / 8192.0) ** 2 * t3
                        temp = (v1 + v2) / 5120.0
                except Exception:
                    pass
        elif esp32 is not None:
            try:
                temp = esp32.mcu_temperature()
            except Exception:
                pass
        if self.botao is not None and self.botao.value() == 0:
            sac = True
            self.ult_mov = agora
        if temp is not None:
            temp += TEMP_OFFSET
            self.temp = temp if self.temp is None else self.temp * 0.7 + temp * 0.3
        if TEMP_FORCADA is not None:
            self.temp = TEMP_FORCADA
        return self.temp, sac


def main():
    tela = Tela(1)
    S = Estado(tela)
    sensor = Sensor()
    q = S.q

    rosto(q)
    S.render.mostrar(q)

    agora = time.ticks_ms()
    ultimo_clima = agora
    proximo = time.ticks_add(agora, random.randint(1500, 4000))
    ultima_idle = None
    anim = None
    nome = ""
    clima = None
    clima_cand = None
    clima_desde = agora
    alivio = False
    ult_print = agora
    periodo = 1000 // FPS

    while True:
        t0 = time.ticks_ms()
        temp, sac = sensor.ler()
        S.parado = sensor.parado(t0)

        alvo = clima
        if temp is not None:
            if clima == "quente":
                if temp < TEMP_QUENTE - HISTERESE:
                    alvo = None
            elif clima == "frio":
                if temp > TEMP_FRIO + HISTERESE:
                    alvo = None
            elif temp >= TEMP_QUENTE:
                alvo = "quente"
            elif temp <= TEMP_FRIO:
                alvo = "frio"
        if alvo != clima_cand:
            clima_cand = alvo
            clima_desde = t0
        if clima_cand != clima and time.ticks_diff(t0, clima_desde) >= CLIMA_ESTAVEL_S * 1000:
            anterior = clima
            clima = clima_cand
            if clima is None:
                alivio = anterior is not None
            else:
                alivio = False
                ultimo_clima = time.ticks_add(t0, -PERIODO_CLIMA_S * 1000)
            print("clima:", clima)

        if sac:
            S.tonto_ate = time.ticks_add(t0, TONTO_MS)
            if nome != "tonto":
                if nome == "clima":
                    ultimo_clima = t0
                anim = anim_tonto(S)
                nome = "tonto"

        clima_vence = clima is not None and time.ticks_diff(t0, ultimo_clima) >= PERIODO_CLIMA_S * 1000

        if nome != "tonto" and clima_vence and (anim is None or nome == "sono"):
            gen = anim_quente(S) if clima == "quente" else anim_frio(S)
            anim = seq(anim_acordar(S), gen) if nome == "sono" else gen
            nome = "clima"
        elif anim is None:
            if alivio and not S.parado:
                alivio = False
                anim = anim_alivio(S)
                nome = "alivio"
            elif S.parado:
                alivio = False
                anim = anim_dormir(S)
                nome = "sono"
            elif time.ticks_diff(t0, proximo) >= 0:
                f = escolher(ultima_idle)
                ultima_idle = f
                anim = f(S)
                nome = "idle"

        if anim is not None:
            try:
                next(anim)
            except StopIteration:
                anim = None
                if nome == "clima":
                    ultimo_clima = time.ticks_ms()
                nome = ""
                S.render.tema(NORMAL)
                rosto(q)
                proximo = time.ticks_add(time.ticks_ms(), random.randint(1500, 4500))
            S.render.mostrar(q)

        if time.ticks_diff(t0, ult_print) > 5000:
            ult_print = t0
            if temp is not None:
                print("temp: %.1f C | movimento max: %.2f g, %.0f graus/s" %
                      (temp, sensor.max_g, sensor.max_giro))
            sensor.max_g = 0.0
            sensor.max_giro = 0.0

        gasto = time.ticks_diff(time.ticks_ms(), t0)
        if gasto < periodo:
            time.sleep_ms(periodo - gasto)


if __name__ == "__main__":
    main()

