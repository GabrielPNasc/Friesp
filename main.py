"""
FriESP - rosto animado para ESP32-S3 (Feather ESP32-S3 TFT, ST7789 240x135)

- Animacoes aleatorias e engracadas enquanto esta parado
- Quente (>= TEMP_QUENTE) ou frio (<= TEMP_FRIO): toca a animacao de clima UMA vez
  e repete so depois de PERIODO_CLIMA_S segundos (nao fica em loop infinito)
- Sacudiu (acelerometro MPU6050): fica tonto
- Sem sensor? Veja as opcoes de teste na secao CONFIG
"""
from machine import Pin, SPI, I2C
import struct
import time
import math
import random

try:
    import esp32
except ImportError:
    esp32 = None

# ======================= CONFIG =======================
TEMP_QUENTE = 30.0        # >= isso: animacao de calor
TEMP_FRIO = 20.0          # <= isso: animacao de frio
PERIODO_CLIMA_S = 30      # segundos entre uma animacao de clima e a proxima
TEMP_OFFSET = 0.0         # corrige a leitura (temperatura do chip costuma ser alta)
TEMP_FORCADA = None       # TESTE: ex. 35 forca "quente", 10 forca "frio"

I2C_SDA = 3               # STEMMA QT da Feather ESP32-S3 TFT (confira no scan do REPL)
I2C_SCL = 4
BOTAO_SIMULA_SACUDIDA = True   # TESTE: apertar BOOT (GPIO0) = sacudir
LIMIAR_G = 0.7            # quanto a aceleracao tem que variar para contar como "batida"
IMPACTOS = 0.0001              # batidas dentro de JANELA_MS = sacudida
JANELA_MS = 1000
TONTO_MS = 3000           # tempo tonto depois da ultima sacudida
FPS = 20

# ======================= TELA =======================
class Tela:
    LARGURA = 240
    ALTURA = 135
    ROT = {1: (0x60, 40, 53), 3: (0xA0, 40, 52)}

    def __init__(self, rotacao=1):
        madctl, self.xoff, self.yoff = self.ROT[rotacao]
        Pin(21, Pin.OUT, value=1)          # alimenta TFT e I2C
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


# ======================= GRADE / CORES =======================
CEL = 3
COLS = 80
LINS = 45
DT = 1.0 / FPS

# indices de cor: 0 preto | 1 borda | 2 medio | 3 miolo | 4 branco/dente
#                 5 gota/floco | 6 lingua | 7 estrela
NORMAL = (0x0000, 0x021F, 0x04DF, 0x2FFF, 0xAFFF, 0x5FFF, 0xF810, 0xFFE0)
QUENTE = (0x0000, 0x9800, 0xF800, 0xFD20, 0xFFE0, 0x5FFF, 0xF810, 0xFFE0)
FRIO   = (0x0000, 0x0010, 0x041F, 0xAFFF, 0xFFFF, 0xFFFF, 0xF810, 0x9FFF)

ZERO2 = b'\x00\x00'
ZERO_LINHA = bytes(COLS * CEL * 2)

OLHO_ESQ = [(3.7, 8.6), (6.7, 10.9), (10.4, 13.0), (15.0, 15.3),
            (20.6, 17.7), (26.1, 19.8), (31.7, 22.0), (24.3, 22.9),
            (18.7, 22.1), (13.2, 20.9), (9.5, 18.8), (7.6, 16.1),
            (6.3, 12.9), (4.9, 10.2)]
CICATRIZ = [(66.6, 1.0), (67.3, 9), (68.6, 14.5), (69.2, 17), (68.2, 21),
            (67.6, 29), (66.9, 21.5), (65.9, 17), (66.0, 12), (66.3, 7)]
EIXO_Y = 15.5


class Quadro:
    """Grade de indices de cor (80x45)."""
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
    """Manda para a tela so as linhas da grade que mudaram."""
    def __init__(self, tela):
        self.tela = tela
        self.prev = [None] * LINS
        self.lut = []
        self.tema(NORMAL)

    def tema(self, cores):
        self.lut = [struct.pack('>H', c) * (CEL - 1) + ZERO2 for c in cores]
        self.prev = [None] * LINS      # forca redesenhar tudo

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


# ======================= DESENHO DO ROSTO =======================
def pontos_olho(espelho, dx, dy, ab, inc):
    ab = max(ab, 0.2)
    out = []
    for x, y in OLHO_ESQ:
        yy = EIXO_Y + (y - EIXO_Y) * ab + dy + inc * ((x - 3.7) / 28.0)
        xx = (COLS - x if espelho else x) + dx
        out.append((xx, yy))
    return out


def geom_boca(cx, s, ab, dy):
    u = (cx - 40) / 36.3
    u2 = u * u
    topo = 33.0 - 7.4 * s * u2 + dy
    esp = (10.6 - 8.6 * u2) * ab
    return topo, topo + esp


def boca(q, s=1.0, ab=1.0, dentes=True, fase=0, dx=0, dy=0, onda=0.0, fase_onda=0.0):
    for gx in range(COLS):
        cx = gx + 0.5 - dx
        u = (cx - 40) / 36.3
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
                c = 2 if (pt == 0 or pb == 0) else 3
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
    q.elipse(cx, base, 4.5, comp, 6)


def boca_o(q, rx, ry, dx=0, dy=0):
    q.elipse(40 + dx, 35 + dy, rx + 1, ry + 1, 2)
    q.elipse(40 + dx, 35 + dy, rx, ry, 3)
    q.elipse(40 + dx, 35 + dy, rx - 2, ry - 2, 0)


def rosto(q, dx=0, dy=0, ab_e=1.0, ab_d=1.0, inc=0.0, ox=0, oy=0,
          s=1.0, ab_b=1.0, dentes=True, fase=0, dy_b=0, onda=0.0, fase_onda=0.0,
          com_olhos=True, com_boca=True):
    q.limpar()
    if com_olhos:
        q.poligono(pontos_olho(False, dx + ox, dy + oy, ab_e, inc))
        q.poligono(pontos_olho(True, dx + ox, dy + oy, ab_d, inc))
    q.poligono([(x + dx, y + dy) for x, y in CICATRIZ], 4, 4, 4)
    if com_boca:
        boca(q, s, ab_b, dentes, fase, dx, dy + dy_b, onda, fase_onda)


def estrela(q, x, y):
    q.pixel(x, y, 4)
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q.pixel(x + ax, y + ay, 7)


def gota(q, x, y):
    q.pixel(x, y, 5)
    q.pixel(x - 1, y + 1, 5)
    q.pixel(x, y + 1, 5)
    q.pixel(x + 1, y + 1, 5)
    q.pixel(x, y + 2, 5)


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


# ======================= ANIMACOES (geradores: 1 yield = 1 quadro) =======================
class Estado:
    def __init__(self, tela):
        self.tela = tela
        self.q = Quadro()
        self.render = Renderizador(tela)
        self.tonto_ate = 0


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
        lingua(q, cx, 1.1, 0.9, -4, 6)
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


def anim_sono(S):
    q = S.q
    for i in range(56):
        rosto(q, dy=2, ab_e=0.2, ab_d=0.2, s=0.2, ab_b=0.35 + 0.1 * math.sin(i * 0.25),
              dentes=False)
        for k in range(3):
            letra_z(q, 54 + k * 5, 28 - ((i * 0.5 + k * 12) % 28))
        yield


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
            while True:                      # espiral de Arquimedes girando
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
    S.render.tema(QUENTE)
    for i in range(100):
        ab_olho = 0.55 + 0.05 * math.sin(i * 0.3)
        pant = 1.0 + 0.25 * math.sin(i * 0.9)
        rosto(q, ab_e=ab_olho, ab_d=ab_olho, inc=-1, s=0.9, ab_b=pant, dy_b=-3)
        lingua(q, 46, 0.9, pant, -3, 4 + 3 * (pant - 0.75))
        for k, x in enumerate((13, 67, 40)):
            gota(q, x, (i * 0.7 + k * 13) % 36)
        yield


def anim_frio(S):
    q = S.q
    S.render.tema(FRIO)
    flocos = [[random.randint(2, COLS - 3), random.randint(0, LINS), 6 + random.randint(0, 5)]
              for _ in range(9)]
    for i in range(100):
        dx = random.choice((-1, 0, 1))
        rosto(q, dx=dx, ab_e=0.85, ab_d=0.85, inc=1, s=-1.3,
              ab_b=0.75 + 0.35 * ((i // 2) % 2), dy_b=2)
        for f in flocos:
            f[1] += f[2] * DT
            if f[1] > LINS + 1:
                f[1] = -1
                f[0] = random.randint(2, COLS - 3)
            floco(q, f[0] + math.sin(i * 0.1 + f[2]), f[1])
        yield


IDLE = ((anim_piscar, 5), (anim_olhar, 3), (anim_piscadela, 2), (anim_risada, 2),
        (anim_lingua, 2), (anim_surpreso, 2), (anim_bravo, 1), (anim_brilho, 2),
        (anim_sono, 1))


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


# ======================= SENSORES =======================
class Sensor:
    """MPU6050 (movimento + temperatura) por I2C. Sem ele: temperatura do chip."""
    def __init__(self):
        self.i2c = None
        self.addr = None
        self.temp = None
        self.impactos = []
        self.acima = False
        self.botao = Pin(0, Pin.IN, Pin.PULL_UP) if BOTAO_SIMULA_SACUDIDA else None
        try:
            self.i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
            achados = self.i2c.scan()
            print("I2C encontrou:", [hex(a) for a in achados])
            for a in (0x68, 0x69):
                if a in achados:
                    self.addr = a
            if self.addr is not None:
                self.i2c.writeto_mem(self.addr, 0x6B, b'\x00')   # acorda o MPU6050
        except Exception as e:
            print("I2C indisponivel:", e)
        if self.addr is not None:
            print("MPU6050 ok (movimento + temperatura)")
        else:
            print("Sem sensor de movimento. Use o botao BOOT para simular a sacudida.")

    def ler(self):
        """Retorna (temperatura_C ou None, sacudiu)."""
        agora = time.ticks_ms()
        temp = None
        sac = False
        if self.addr is not None:
            try:
                d = self.i2c.readfrom_mem(self.addr, 0x3B, 8)
                ax, ay, az, t = struct.unpack('>hhhh', d)
                g = math.sqrt(ax * ax + ay * ay + az * az) / 16384.0
                temp = t / 340.0 + 36.53
                acima = abs(g - 1.0) > LIMIAR_G
                if acima and not self.acima:
                    self.impactos.append(agora)
                self.acima = acima
                self.impactos = [x for x in self.impactos
                                 if time.ticks_diff(agora, x) < JANELA_MS]
                if len(self.impactos) >= IMPACTOS:
                    sac = True
                    self.impactos = []
            except Exception:
                pass
        if temp is None and esp32 is not None:
            try:
                temp = esp32.mcu_temperature()
            except Exception:
                pass
        if self.botao is not None and self.botao.value() == 0:
            sac = True
        if temp is not None:
            temp += TEMP_OFFSET
            self.temp = temp if self.temp is None else self.temp * 0.95 + temp * 0.05
        if TEMP_FORCADA is not None:
            self.temp = TEMP_FORCADA
        return self.temp, sac


# ======================= PRINCIPAL =======================
def main():
    tela = Tela(1)
    S = Estado(tela)
    sensor = Sensor()
    q = S.q

    rosto(q)
    S.render.mostrar(q)

    agora = time.ticks_ms()
    ultimo_clima = time.ticks_add(agora, 3000 - PERIODO_CLIMA_S * 1000)   # 1a vez em ~3 s
    proximo = time.ticks_add(agora, random.randint(1500, 4000))
    ultima_idle = None
    anim = None
    nome = ""
    ult_print = agora
    periodo = 1000 // FPS

    while True:
        t0 = time.ticks_ms()
        temp, sac = sensor.ler()

        if sac:
            S.tonto_ate = time.ticks_add(t0, TONTO_MS)
            if nome != "tonto":
                anim = anim_tonto(S)
                nome = "tonto"

        if anim is None:
            quente = temp is not None and temp >= TEMP_QUENTE
            frio = temp is not None and temp <= TEMP_FRIO
            clima_vence = time.ticks_diff(t0, ultimo_clima) >= PERIODO_CLIMA_S * 1000
            if clima_vence and (quente or frio):
                anim = anim_quente(S) if quente else anim_frio(S)
                nome = "clima"
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
                print("temp: %.1f C" % temp)

        gasto = time.ticks_diff(time.ticks_ms(), t0)
        if gasto < periodo:
            time.sleep_ms(periodo - gasto)


if __name__ == "__main__":
    main()