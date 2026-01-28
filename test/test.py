# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb.triggers import ClockCycles, with_timeout
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

async def wait_rise_on_bit(dut, vec, bit_idx, timeout_cycles=100_000):
    prev = (int(vec.value) >> bit_idx) & 1
    for _ in range(timeout_cycles):
        await ClockCycles(dut.clk, 1)
        cur = (int(vec.value) >> bit_idx) & 1
        if prev == 0 and cur == 1:
            return
        prev = cur
    raise AssertionError(f"Timeout waiting for rising edge on bit {bit_idx}")

async def wait_fall_on_bit(dut, vec, bit_idx, timeout_cycles=100_000):
    prev = (int(vec.value) >> bit_idx) & 1
    for _ in range(timeout_cycles):
        await ClockCycles(dut.clk, 1)
        cur = (int(vec.value) >> bit_idx) & 1
        if prev == 1 and cur == 0:
            return
        prev = cur
    raise AssertionError(f"Timeout waiting for falling edge on bit {bit_idx}")

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

async def spi_write(dut, addr, data):
    await send_spi_transaction(dut, 1, addr, data)

async def reset_dut(dut):
    # 10 MHz clock
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0) # NCS high(idle), COPI low, SCLK low
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

async def configure_pwm_pin0(dut, duty):
    """
    Configure uo_out[0] to be PWM driven:
      - en_reg_out_7_0 bit0 = 1  (addr 0x00, data 0x01)
      - en_reg_pwm_7_0 bit0 = 1  (addr 0x02, data 0x01)
      - pwm_duty_cycle = duty    (addr 0x04)
    """
    await spi_write(dut, 0x00, 0x01)   # enable output bit0
    await spi_write(dut, 0x02, 0x01)   # enable PWM on bit0
    await spi_write(dut, 0x04, duty)   # duty cycle

async def measure_pwm_period_ns(dut, vec, bit_idx, timeout_cycles=100_000):
    """
    Measure period as time between two rising edges.
    Returns period in ns (float).
    """
    await wait_rise_on_bit(dut, vec, bit_idx, timeout_cycles)
    t1 = cocotb.utils.get_sim_time(units="ns")
    await wait_rise_on_bit(dut, vec, bit_idx, timeout_cycles)
    t2 = cocotb.utils.get_sim_time(units="ns")
    return float(t2 - t1)

async def measure_pwm_high_and_period_ns(dut, vec, bit_idx, timeout_cycles=100_000):
    """
    Measure high time and period:
      rising -> falling = high
      rising -> next rising = period
    Returns (high_ns, period_ns).
    """
    await wait_rise_on_bit(dut, vec, bit_idx, timeout_cycles)
    t_r1 = cocotb.utils.get_sim_time(units="ns")

    await wait_fall_on_bit(dut, vec, bit_idx, timeout_cycles)
    t_f = cocotb.utils.get_sim_time(units="ns")

    await wait_rise_on_bit(dut, vec, bit_idx, timeout_cycles)
    t_r2 = cocotb.utils.get_sim_time(units="ns")

    return float(t_f - t_r1), float(t_r2 - t_r1)

async def assert_stays_constant(sig, expected, cycles, dut):
    """
    Sample a signal for N clk cycles and ensure it never changes from expected.
    """
    for _ in range(cycles):
        assert int(sig.value) == expected, f"Expected constant {expected}, got {sig.value}"
        await ClockCycles(dut.clk, 1)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # Write your test here
    dut._log.info("Start PWM Frequency test")
    await reset_dut(dut)

    # Configure pin0 to PWM with ~50% duty so it toggles
    await configure_pwm_pin0(dut, 0x80)

    # Measure period and compute frequency
    period_ns = await measure_pwm_period_ns(dut, dut.uo_out, 0)
    frequency_hz = 1e9 / period_ns

    dut._log.info(f"Measured PWM frequency: {frequency_hz:.2f} Hz (period: {period_ns:.2f} ns)")

    # Spec: 3 kHz ± 1% => [2970 Hz, 3030 Hz]
    assert 2970.0 <= frequency_hz <= 3030.0, f"PWM frequency {frequency_hz} Hz out of spec range"

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):
    # Write your test here
    dut._log.info("Start PWM Duty Cycle test")
    await reset_dut(dut)

    pwm_sig = dut.uo_out[0]

    # Enable output and PWM on pin0 once
    await spi_write(dut, 0x00, 0x01)   # enable output bit0
    await spi_write(dut, 0x02, 0x01)   # enable PWM on bit0

    # Case A: 0% duty => always low
    await spi_write(dut, 0x04, 0x00)   
    # Don't wait for edges (won't toggle). Sample for a while.
    await assert_stays_constant(pwm_sig, expected=0, cycles=5000, dut=dut)

    # Case B: 100% duty => always high
    await spi_write(dut, 0x04, 0xFF)
    await assert_stays_constant(pwm_sig, expected=1, cycles=5000, dut=dut)

    # Case C: 50% duty - Spec: ±1% 
    await spi_write(dut, 0x04, 0x80)
    high_ns, period_ns = await measure_pwm_high_and_period_ns(dut, dut.uo_out, 0)
    duty_cycle = (high_ns / period_ns) * 100.0
    dut._log.info(f"Measured PWM duty cycle: {duty_cycle:.2f}% (high: {high_ns:.2f} ns, period: {period_ns:.2f} ns)")
    assert 49.0 <= duty_cycle <= 51.0, f"PWM duty cycle {duty_cycle}% out of spec range for 0x80"

    # Case D: 25% duty - Spec: ±1%
    await spi_write(dut, 0x04, 0x40)
    high_ns, period_ns = await measure_pwm_high_and_period_ns(dut, dut.uo_out, 0)
    duty_cycle = (high_ns / period_ns) * 100.0
    dut._log.info(f"Measured PWM duty cycle: {duty_cycle:.2f}% (high: {high_ns:.2f} ns, period: {period_ns:.2f} ns)")
    assert 24.0 <= duty_cycle <= 26.0, f"PWM duty cycle {duty_cycle}% out of spec range for 0x40"

    dut._log.info("PWM Duty Cycle test completed successfully")
