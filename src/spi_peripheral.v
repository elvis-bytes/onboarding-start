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


reg active;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        active <= 1'b0;
    end else begin
        if (ncs_fall) active <= 1'b1;
        if (ncs_rise) active <= 1'b0;
    end
end

endmodule