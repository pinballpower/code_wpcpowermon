# Hardware description

## GPIOs

|Raspberry Pi Pico GPIO|Name|Protocols|Use case example|
|---|---|---|---|
|0-15|WPC|Interface to WPC data bus|-|
|16,17|J1|UART, I2C|serial interface (RS232, RS485)|
|18,19|IO7+8|SPI TX, CLK|external shift registers|
|20,21|IO5+6|UART, I2C|serial interface (RS232, RS485)|
|22,26|IO3+4|-|bit-banging or PIO-implemented protocols|
|27,28|IO1+2|-|bit-banging or PIO-implemented protocols|

This table shows the pre-defined functionality on the I/Os on the WPC Powermon board.
Using PIO programs, you can easily add more functionality to these GPIOs. But also bit-banging can be used easily.
