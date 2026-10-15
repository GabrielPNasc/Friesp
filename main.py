from machine import Pin, SPI
import struct
import time


# ---------------- Apaga os LEDs da placa ----------------
def apagar_leds():
    # LED simples (GPIO13 na Feather ESP32-S3 TFT)
    try:
        Pin(13, Pin.OUT, value=0)
        print("GPIO13 -> LOW")
    except Exception as e:
        print("erro GPIO13:", e)

    # NeoPixel RGB: tenta os pinos mais comuns e manda preto
    try:
        import neopixel
    except Exception as e:
        print("sem modulo neopixel:", e)
        return

    for pino in (33, 48, 38, 47):
        try:
            np = neopixel.NeoPixel(Pin(pino, Pin.OUT), 1)
            np[0] = (0, 0, 0)
            np.write()
            print("NeoPixel GPIO%d -> preto" % pino)
        except Exception as e:
            print("erro NeoPixel GPIO%d: %s" % (pino, e))


class Tela:
    LARGURA = 240
    ALTURA = 135

    ROT = {
        1: (0x60, 40, 53),
        3: (0xA0, 40, 52)
    }

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

        self.rst(1)
        time.sleep_ms(10)
        self.rst(0)
        time.sleep_ms(20)
        self.rst(1)
        time.sleep_ms(150)

        self.cmd(0x01)
        time.sleep_ms(150)
        self.cmd(0x11)
        time.sleep_ms(120)
        self.cmd(0x3A, b'\x55')
        self.cmd(0x36, bytes([madctl]))
        self.cmd(0x21)
        self.cmd(0x13)
        time.sleep_ms(10)
        self.cmd(0x29)
        time.sleep_ms(100)

        self.fill(0x0000)
        self.bl(1)

    def cmd(self, c, dados=b''):
        self.cs(0)
        self.dc(0)
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
        self.cs(0)
        self.dc(1)
        self.spi.write(dados)
        self.cs(1)

    def fill(self, cor):
        linha = struct.pack('>H', cor) * self.LARGURA
        self.janela(0, 0, self.LARGURA - 1, self.ALTURA - 1)
        self.cs(0)
        self.dc(1)
        for _ in range(self.ALTURA):
            self.spi.write(linha)
        self.cs(1)


# ---------------- Cores RGB565 ----------------
PRETO = 0x0000
HALO = 0x0006      # brilho fraquinho em volta das formas
AZUL = 0x021F      # borda externa (azul profundo)
MEDIO = 0x04DF     # transicao
CIANO = 0x2FFF     # miolo brilhante
BRANCO = 0xAFFF    # dentes e cicatriz

# ---------------- Grade estilo matriz de LED ----------------
CEL = 3            # 80 * 3 = 240 | 45 * 3 = 135
COLS = 80
LINS = 45
LED_GAP = True     # True = 2px acesos + 1px preto (efeito LED)

# Poligonos em coordenadas da grade (col, lin), tirados da imagem
OLHO_ESQ = [(3.7, 8.6), (6.7, 10.9), (10.4, 13.0), (15.0, 15.3),
            (20.6, 17.7), (26.1, 19.8), (31.7, 22.0), (24.3, 22.9),
            (18.7, 22.1), (13.2, 20.9), (9.5, 18.8), (7.6, 16.1),
            (6.3, 12.9), (4.9, 10.2)]
OLHO_DIR = [(COLS - x, y) for x, y in OLHO_ESQ]

CICATRIZ = [(66.6, 1.0), (67.3, 9), (68.6, 14.5), (69.2, 17), (68.2, 21),
            (67.6, 29), (66.9, 21.5), (65.9, 17), (66.0, 12), (66.3, 7)]


def dentro(px, py, poly):
    ok = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                ok = not ok
        j = i
    return ok


def montar_mascara():
    """0=vazio, 1=corpo, 2=dente, 3=cicatriz"""
    m = [[0] * COLS for _ in range(LINS)]

    for gy in range(LINS):
        cy = gy + 0.5
        for gx in range(COLS):
            cx = gx + 0.5

            if dentro(cx, cy, OLHO_ESQ) or dentro(cx, cy, OLHO_DIR):
                m[gy][gx] = 1

            # Boca em crescente, pontas finas curvadas para cima
            u = (cx - 40) / 36.3
            if abs(u) <= 1:
                topo = 33.0 - 7.4 * u * u
                base = 43.6 - 16.0 * u * u
                if topo <= cy <= base:
                    esp = base - topo
                    if cy < topo + 2 or cy > base - 2 or esp < 7:
                        m[gy][gx] = 1                       # labios
                    else:
                        c = esp / 2 - 1
                        f = abs(gx % 8 - 4)                 # dente de cima
                        if cy - (topo + 2) < c * (1 - f / 4):
                            m[gy][gx] = 2
                        f2 = abs((gx + 4) % 8 - 4)          # dente de baixo
                        if (base - 2) - cy < c * (1 - f2 / 4):
                            m[gy][gx] = 2

            if dentro(cx, cy, CICATRIZ):
                m[gy][gx] = 3
    return m


def dist_vazio(m, gx, gy, raio=3):
    """Distancia (em celulas) ate a celula vazia mais proxima, ate 'raio'."""
    for r in range(1, raio):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                nx, ny = gx + dx, gy + dy
                if nx < 0 or ny < 0 or nx >= COLS or ny >= LINS or m[ny][nx] == 0:
                    return r
    return raio


def tem_corpo_perto(m, gx, gy):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = gx + dx, gy + dy
            if 0 <= nx < COLS and 0 <= ny < LINS and m[ny][nx] != 0:
                return True
    return False


def cor_celula(m, gx, gy):
    v = m[gy][gx]
    if v == 0:
        return HALO if tem_corpo_perto(m, gx, gy) else PRETO
    if v >= 2:
        return BRANCO
    d = dist_vazio(m, gx, gy)
    if d == 1:
        return AZUL
    if d == 2:
        return MEDIO
    return CIANO


def desenhar(tela):
    m = montar_mascara()
    y_ini = (tela.ALTURA - LINS * CEL) // 2
    preto = struct.pack('>H', PRETO)

    for gy in range(LINS):
        linha = bytearray()
        for gx in range(COLS):
            c = struct.pack('>H', cor_celula(m, gx, gy))
            if LED_GAP:
                linha += c * (CEL - 1) + preto
            else:
                linha += c * CEL

        if LED_GAP:
            bloco = bytes(linha) * (CEL - 1) + preto * (COLS * CEL)
        else:
            bloco = bytes(linha) * CEL

        y0 = y_ini + gy * CEL
        tela.bloco(0, y0, COLS * CEL - 1, y0 + CEL - 1, bloco)


apagar_leds()
tela = Tela(1)
tela.fill(PRETO)
desenhar(tela)
print("FriESP pronto!")