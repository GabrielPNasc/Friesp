
from machine import Pin, SPI
import struct
import time
import math


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

        self.spi = SPI(
            1,
            baudrate=40_000_000,
            polarity=0,
            phase=0,
            sck=Pin(36),
            mosi=Pin(35),
            miso=Pin(37)
        )

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
        self.cmd(
            0x2A,
            struct.pack(
                '>HH',
                x0 + self.xoff,
                x1 + self.xoff
            )
        )

        self.cmd(
            0x2B,
            struct.pack(
                '>HH',
                y0 + self.yoff,
                y1 + self.yoff
            )
        )

        self.cmd(0x2C)

    def rect(self, x, y, w, h, cor):
        if w <= 0 or h <= 0:
            return

        # Impede desenhos fora da tela
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.LARGURA, x + w)
        y1 = min(self.ALTURA, y + h)

        if x0 >= x1 or y0 >= y1:
            return

        w = x1 - x0
        h = y1 - y0

        self.janela(x0, y0, x1 - 1, y1 - 1)

        linha = struct.pack('>H', cor) * w

        self.cs(0)
        self.dc(1)

        for _ in range(h):
            self.spi.write(linha)

        self.cs(1)

    def fill(self, cor):
        self.rect(
            0, 0,
            self.LARGURA,
            self.ALTURA,
            cor
        )

    def elipse(self, cx, cy, rx, ry, cor):
        # Desenha uma elipse preenchida,
        # usando retangulos horizontais.
        for dy in range(-ry, ry + 1):
            fator = 1 - (dy * dy) / (ry * ry)

            if fator < 0:
                continue

            dx = int(rx * math.sqrt(fator))

            self.rect(
                cx - dx,
                cy + dy,
                2 * dx + 1,
                1,
                cor
            )


# Cores RGB565
PRETO = 0x0000
CIANO = 0x07FF

# Inicializa a tela
tela = Tela(1)

# Fundo
tela.fill(PRETO)

# Olho esquerdo
tela.elipse(66, 57, 24, 24, CIANO)
tela.elipse(66, 57, 10, 12, PRETO)

# Olho direito
tela.elipse(174, 57, 24, 24, CIANO)
tela.elipse(174, 57, 10, 12, PRETO)

# Sorriso
for y in range(88, 101):
    dx = int(math.sqrt((100 - y) * 48))

    tela.rect(120 - dx - 1, y, 3, 3, CIANO)
    tela.rect(120 + dx - 1, y, 3, 3, CIANO)

print("FriESP iniciado!")
