# FriESP

Um pequeno personagem eletrônico com rosto animado, movido por um ESP32 e MicroPython.

> **Plataforma:** ESP32 (LilyGO TTGO T-Display) · **Linguagem:** MicroPython · **Display:** ST7789 · **Status:** em desenvolvimento

O FriESP transforma uma placa ESP32 com display em um personagem que reage ao que acontece ao redor. A proposta é que ele pisque, mude de expressão conforme a temperatura do ambiente e fique tonto quando for movido ou girado, tudo desenhado diretamente no display TFT, sem depender de computador ou de conexão com a internet.

O código é escrito em MicroPython e organizado em módulos independentes: driver do display, desenho do rosto, leitura de sensores e lógica de comportamento. Essa separação permite trocar o sensor ou o display sem reescrever o restante da aplicação.

> **Estado atual:** o driver do display, a rolagem de texto, a rotação de tela e os temas de cor já funcionam em hardware real. O rosto animado e a integração dos sensores estão em desenvolvimento.

Leia em inglês: [README.en.md](README.en.md)

---

## O que ele faz

As funcionalidades abaixo combinam o que já está validado na placa e o que está planejado.

| Funcionalidade | Descrição | Situação |
|---|---|---|
| Inicialização do display | Driver ST7789 de baixo nível, com orientação e inversão de cor configuráveis | Concluído |
| Banner rolante | Rolagem contínua em estilo Pac-Man, com título e subtítulo | Concluído |
| Rotação da tela | Quatro orientações (paisagem, retrato e ambas invertidas), alternadas por botão | Concluído |
| Temas de cor | Quatro pares de fundo e fonte, alternados por botão | Concluído |
| Rosto animado | Olhos, boca e expressões básicas | Em andamento |
| Piscar e movimentos | Animações faciais dinâmicas em repouso | Planejado |
| Reações à temperatura | Expressões de calor e de frio | Planejado |
| Detecção de movimento | Simulação de tontura em movimentos e rotações | Planejado |
| Expressões automáticas | Motor de comportamento que combina todas as entradas | Planejado |

---

## Como funciona

A aplicação roda em um laço principal dividido em quatro etapas:

1. **Entrada.** Lê os botões e, futuramente, os sensores de temperatura e de movimento.
2. **Comportamento.** Converte as leituras em um estado de expressão (neutro, calor, frio, tonto).
3. **Renderização.** Desenha o rosto correspondente ao estado, atualizando apenas as regiões da tela que mudaram.
4. **Display.** Envia os pixels ao ST7789 por SPI.

Como o barramento SPI é emulado por software, a renderização evita redesenhar a tela inteira a cada quadro.

---

## Hardware

### Placa de desenvolvimento

| Componente | Especificação |
|---|---|
| Placa | LilyGO TTGO T-Display |
| Microcontrolador | ESP32 (dual-core Xtensa LX6, Wi-Fi e Bluetooth) |
| Display | TFT IPS de 1,14", 240 x 135 pixels, controlador ST7789, RGB565 |
| Botões | 2 integrados (GPIO 0 e GPIO 35) |
| Conexão | USB-C |

### Sensores opcionais

A T-Display não possui sensores de movimento nem de temperatura. Para as funções reativas, são necessários módulos externos conectados por I2C:

| Função | Módulo sugerido | Interface |
|---|---|---|
| Acelerômetro e giroscópio | MPU6050 ou MPU9250 | I2C |
| Temperatura (e pressão) | BMP280, BME280 ou similar | I2C |

A escolha dos sensores está sujeita à verificação de hardware. O código é projetado para que o driver de cada sensor possa ser substituído sem alterar o restante da aplicação.

### Nota de portabilidade

O projeto tinha originalmente como alvo o ESP32-S3. A variante S3 da T-Display usa um barramento paralelo de 8 bits para o display, em vez de SPI, o que muda os pinos e a inicialização. O código atual é voltado ao **ESP32 clássico**, com barramento SPI.

---

## Pinagem

### Display (ST7789, SPI)

| Sinal | GPIO |
|---|---|
| SCK (clock) | 18 |
| MOSI (dados) | 19 |
| CS (seleção de chip) | 5 |
| DC (dados/comando) | 16 |
| RST (reset) | 23 |
| BL (luz de fundo) | 4 |

### Botões

| Botão | GPIO | Função |
|---|---|---|
| BOOT | 0 | Trocar o tema de cor |
| Direito | 35 | Girar a tela |

O GPIO 35 é somente entrada e depende do pull-up externo da placa. O GPIO 0 usa o pull-up interno.

> **Atenção:** não segure o botão BOOT ao ligar a placa. Isso ativa o modo de gravação de firmware e o programa não é executado.

---

## Software e tecnologias

| Item | Detalhe |
|---|---|
| Linguagem | MicroPython |
| Firmware | MicroPython para ESP32 (build `ESP32_GENERIC` recomendado) |
| Driver do display | Rotinas ST7789 próprias, usando `machine.SoftSPI` |
| Gráficos | `framebuf` (buffers de quadro RGB565) |
| Ambiente de desenvolvimento | Thonny IDE |

---

## Instalação

### 1. Gravar o firmware

1. Baixe o build **ESP32_GENERIC** em [micropython.org/download](https://micropython.org/download/ESP32_GENERIC/).
2. No Thonny, abra **Ferramentas > Opções > Interpretador** e selecione **MicroPython (ESP32)**.
3. Clique em **Instalar ou atualizar o MicroPython** e siga as instruções.

### 2. Enviar o projeto

1. Clone ou baixe este repositório.
2. No Thonny, abra **Exibir > Arquivos**.
3. Copie os arquivos do projeto para a raiz da memória do dispositivo.

### 3. Executar automaticamente ao ligar

O MicroPython executa o arquivo `main.py` na inicialização. Salve o ponto de entrada no dispositivo exatamente com esse nome, na pasta raiz.

Para verificar erros de inicialização, abra o Shell do Thonny e pressione `Ctrl+D`, que reinicia a placa e executa o `main.py`.

---

## Estrutura do projeto

O código está organizado em módulos para facilitar a manutenção. A estrutura planejada é:

```text
FriESP/
├── main.py        Ponto de entrada: laço principal e controle de estados
├── config.py      Pinos, cores e parâmetros ajustáveis
├── display.py     Driver ST7789: inicialização, janelas e rotação
├── face.py        Renderização do rosto: olhos, boca, expressões e piscar
├── sensors.py     Abstração dos sensores de temperatura e movimento
├── behavior.py    Lógica que converte dados dos sensores em expressões
└── README.md
```

O protótipo atual (driver do display, banner rolante e botões de rotação e cor) está em um único script e será dividido nesses módulos conforme o desenvolvimento avança.

---

## Notas técnicas sobre o display

| Assunto | Detalhe |
|---|---|
| SPI por hardware e SoftSPI | Nos testes iniciais, o display permaneceu em branco (luz de fundo acesa, sem imagem) com SPI por hardware no firmware instalado. A troca para `SoftSPI` resolveu o problema. Ele é mais lento, por isso a renderização atualiza apenas as regiões que mudam. |
| Inversão de cor | O painel exige o comando de inversão (`0x21`) para exibir as cores corretamente. |
| Ordem dos bytes | O `framebuf` armazena RGB565 em little-endian, enquanto o display espera big-endian. Os bytes das cores são trocados antes de desenhar. |
| Memória | Buffers de quadro grandes podem causar `MemoryError` em um ESP32 sem PSRAM. Mantenha escalas de texto moderadas. |
| Rotação automática | A T-Display não possui sensor de movimento, então a rotação é manual, por botão. Ela será possível após integrar um acelerômetro externo. |

A RAM do ST7789 é de 240 x 320, enquanto o painel físico é de 135 x 240. Por isso, um deslocamento (offset) é aplicado à janela de endereçamento em cada orientação:

| Orientação | MADCTL | Offset X | Offset Y |
|---|---|---|---|
| Paisagem | `0x60` | 40 | 53 |
| Retrato | `0xC0` | 53 | 40 |
| Paisagem (invertida) | `0xA0` | 40 | 52 |
| Retrato (invertido) | `0x00` | 52 | 40 |

---

## Roteiro

- [x] Teste inicial do display
- [x] Driver do display com suporte a orientação e cores
- [x] Banner rolante com título e subtítulo
- [x] Rotação e temas de cor controlados por botões
- [ ] Desenho facial básico
- [ ] Animações faciais (piscar e movimentos em repouso)
- [ ] Integração do sensor de temperatura
- [ ] Detecção de movimento e rotação
- [ ] Troca automática de expressões
- [ ] Refatoração do código em módulos

---

## Objetivos

O projeto busca explorar:

- programação de sistemas embarcados com MicroPython;
- controle de display em baixo nível e renderização gráfica em hardware limitado;
- integração de sensores via I2C;
- comportamento interativo baseado em estados em um microcontrolador.

O desenvolvimento é incremental e validado em hardware físico, com o auxílio de ferramentas de IA durante a implementação e a depuração.

---

## Autor

**Gabriel Nascimento**, Desenvolvedor, Cibersegurança.

## Agradecimentos

- Projeto e comunidade [MicroPython](https://micropython.org/).
- LilyGO, pela documentação do hardware TTGO T-Display.
- Ferramentas de desenvolvimento assistido por IA, usadas no apoio à geração de código e à depuração.
