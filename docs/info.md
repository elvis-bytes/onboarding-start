<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements an SPI-controlled register block that configures a PWM peripheral.

A controller communicates with the design using a 16-bit SPI write transaction (MSB first).  
Each transaction consists of:
- 1 Read/Write bit (writes only are supported)
- 7-bit register address
- 8-bit data payload

To ensure reliable operation, the SPI interface uses edge detection and transaction state tracking.
SPI signals (COPI, SCLK, nCS) are synchronized into the system clock domain using two-flip-flop synchronizers. 
Previous-cycle copies of the synchronized clock and chip-select signals are retained, enabling rising and falling edges to be detected using combinational logic.
An internal transaction-active flag is asserted when chip-select goes low and cleared when it returns high. Data is only captured on the rising edge of SCLK while this flag is active.
A completion flag indicates when a full 16-bit SPI word has been received. 
Register updates are only committed once the transaction completes, ensuring partial or malformed transfers are ignored.

The design exposes configuration registers that:
- Enable or disable output pins
- Enable or disable PWM control per output
- Set a shared 8-bit PWM duty cycle

The PWM generator uses an internal counter to produce a ~3 kHz signal.  
Each PWM period is divided into 256 steps, and the output is held high while the counter value is less than the programmed duty cycle.

If an output is not enabled, or PWM is not enabled for that pin, the output remains low regardless of the duty cycle setting.

---

## How to test

The design is verified using cocotb-based simulation tests.

Tests include:
- Writing SPI transactions and confirming correct register updates
- Verifying invalid addresses and read transactions are ignored
- Measuring PWM frequency to ensure it is within specification
- Measuring PWM duty cycle at 0%, 25%, 50%, and 100%
- Confirming PWM Output Enable Takes Precedence over PWM Mode

---

## External hardware

No external hardware is required.  
All functionality is verified through simulation.