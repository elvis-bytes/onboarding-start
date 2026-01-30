module spi_peripheral (
    input  wire       clk,       // clock
    input  wire       rst_n,     // reset_n - low to reset
    input  wire       copi,      // Controller Out Peripheral In
    input  wire       sclk,      // Serial Clock
    input  wire       ncs,       // Not Chip Select (active low)

    output reg [7:0]  en_reg_out_7_0, 
    output reg [7:0]  en_reg_out_15_8, 
    output reg [7:0]  en_reg_pwm_7_0, 
    output reg [7:0]  en_reg_pwm_15_8,
    output reg [7:0]  pwm_duty_cycle 
);

// 2-FF synchronizers for async SPI pins into clk domain
reg copi_sync1, copi_sync2;
reg sclk_sync1, sclk_sync2;
reg ncs_sync1, ncs_sync2;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        copi_sync1 <= 1'b0;
        copi_sync2 <= 1'b0;
        sclk_sync1 <= 1'b0;
        sclk_sync2 <= 1'b0;
        ncs_sync1 <= 1'b1;  // idle high for nCS
        ncs_sync2 <= 1'b1;
    end else begin
        copi_sync1 <= copi;
        copi_sync2 <= copi_sync1;

        sclk_sync1 <= sclk;
        sclk_sync2 <= sclk_sync1;

        ncs_sync1 <= ncs;
        ncs_sync2 <= ncs_sync1;
    end
end

// Delayed copies for edge detection
reg sclk_prev;
reg ncs_prev;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sclk_prev <= 1'b0;
        ncs_prev <= 1'b1;
    end else begin
        sclk_prev <= sclk_sync2;
        ncs_prev <= ncs_sync2;
    end
end

wire sclk_rise = (sclk_sync2 == 1'b1) && (sclk_prev == 1'b0);
wire ncs_fall = (ncs_sync2 == 1'b0) && (ncs_prev == 1'b1);
wire ncs_rise = (ncs_sync2 == 1'b1) && (ncs_prev == 1'b0);

// Active flag to indicate if SPI transaction is ongoing
reg active;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        active <= 1'b0;
    end else begin
        if (ncs_fall) active <= 1'b1;
        if (ncs_rise) active <= 1'b0;
    end
end


// Transaction Logic - Bit counter and shift register
reg [15:0] shift_reg;
reg [4:0] bit_count; // 0-16 bits - to represent num 16
reg got_16;

// Capture bits
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        shift_reg <= 16'h0000;
        bit_count <= 6'd0;
        got_16    <= 1'b0;
    end else begin
        // Start of transaction: clear capture state
        if (ncs_fall) begin
            shift_reg <= 16'h0000;
            bit_count <= 6'd0;
            got_16    <= 1'b0;
        end

        // Capture bits on SCLK rising edge while active/selected
        if (active && sclk_rise && !got_16) begin    
            // First received bit ends up in MSB
            shift_reg <= {shift_reg[14:0], copi_sync2};
            bit_count <= bit_count + 6'd1;

            if (bit_count == 6'd16) begin
                got_16 <= 1'b1;
            end
        end
    end
end

// Process/Decode received data
wire rw = shift_reg[15];          // Read/Write bit
wire [6:0] addr = shift_reg[14:8]; // 7-bit address
wire [7:0] data = shift_reg[7:0];   // 8-bit data

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        en_reg_out_7_0   <= 8'h00;
        en_reg_out_15_8  <= 8'h00;
        en_reg_pwm_7_0   <= 8'h00;
        en_reg_pwm_15_8  <= 8'h00;
        pwm_duty_cycle   <= 8'h00;
    end else begin
        // End of transaction: Commit, but only valid data
        if (ncs_rise && got_16 && (rw == 1'b1)) begin
            case (addr)
                7'h00: en_reg_out_7_0   <= data;
                7'h01: en_reg_out_15_8  <= data;
                7'h02: en_reg_pwm_7_0   <= data;
                7'h03: en_reg_pwm_15_8  <= data;
                7'h04: pwm_duty_cycle   <= data;
                default: begin
                    // invalid address: ignore
                end
            endcase
        end
    end
end

endmodule