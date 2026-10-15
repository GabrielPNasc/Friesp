from machine import Pin, SPI
import struct
import time


class Tela:
    LARGURA = 240
    ALTURA = 135
    # rotacao: (MADCTL, deslocamento x, deslocamento y). 1 e 3 sao paisagem.
    ROT = {1: (0x60, 40, 53), 3: (0xA0, 40, 52)}

    def __init__(self, rotacao=1):
        madctl, self.xoff, self.yoff = self.ROT[rotacao]

        # GPIO 21 alimenta a tela nesta placa
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

    def rect(self, x, y, w, h, cor):
        self.janela(x, y, x + w - 1, y + h - 1)
        linha = struct.pack('>H', cor) * w
        self.cs(0)
        self.dc(1)
        for _ in range(h):
            self.spi.write(linha)
        self.cs(1)

    def fill(self, cor):
        self.rect(0, 0, self.LARGURA, self.ALTURA, cor)


tela = Tela(1)

for nome, cor in (("vermelho", 0xF800), ("verde", 0x07E0),
                  ("azul", 0x001F), ("branco", 0xFFFF), ("preto", 0x0000)):
    print(nome)
    tela.fill(cor)
    time.sleep(1)

BRANCO = 0xFFFF
tela.rect(0, 0, 240, 3, BRANCO)
tela.rect(0, 132, 240, 3, BRANCO)
tela.rect(0, 0, 3, 135, BRANCO)
tela.rect(237, 0, 3, 135, BRANCO)
print("pronto")