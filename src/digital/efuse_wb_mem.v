/*
 * eFuse array digital wrapper with Wishbone slave interface.
 *
 * Wishbone address is per efuse word and write mask is not supported.
 * In case if EFUSE_WORD_WIDTH is less than WB_DAT_WIDTH
 */

`ifndef EFUSE_WBMEM_NAME
`define EFUSE_WBMEM_NAME efuse_wb_mem
`endif

`ifndef EFUSE_ARRAY_NAME
`define EFUSE_ARRAY_NAME efuse_array
`endif

module `EFUSE_WBMEM_NAME #(
    parameter EFUSE_NWORDS      = 16,
    parameter EFUSE_WORD_WIDTH  = 1,
    parameter WB_ADR_WIDTH      = 8,
    parameter WB_DAT_WIDTH      = 8
) (
    input                       wb_clk_i,
    input                       wb_rst_i, 
    input                       wb_stb_i, 
    input                       wb_cyc_i, 
    input  [WB_ADR_WIDTH-1:0]   wb_adr_i,       // Address is per efuse word
    input  [WB_DAT_WIDTH-1:0]   wb_dat_i, 
    input                       wb_we_i,
    output [WB_DAT_WIDTH-1:0]   wb_dat_o,
    output                      wb_ack_o,

    input                       write_disable_i // Active-high write-disable signal. Recommended to be supplied with active-high POR reset
);

    reg [WB_DAT_WIDTH-1:0] dat_o;
    reg ack_o;
    reg [2:0] state;
    reg [9:0] counter;

    wire [EFUSE_NWORDS-1:0] bit_sel;
    wire [EFUSE_WORD_WIDTH-1:0] col_prog_n;
    wire preset_n;
    wire sense;
    wire sense_del;
    wire [EFUSE_WORD_WIDTH-1:0] efuse_out;

    reg [EFUSE_NWORDS-1:0] bit_sel_reg;
    reg [EFUSE_WORD_WIDTH-1:0] col_prog_n_reg;
    reg preset_n_reg;
    reg sense_reg;

    assign wb_ack_o = ack_o;
    assign wb_dat_o = dat_o;

    `EFUSE_ARRAY_NAME #(
        .NWORDS(EFUSE_NWORDS),
        .WORD_WIDTH(EFUSE_WORD_WIDTH)
    ) efuse_array (
        .BIT_SEL    (bit_sel),
        .COL_PROG_N (col_prog_n),
        .PRESET_N   (preset_n),
        .SENSE      (sense),
        .OUT        (efuse_out)
    );

    localparam ADR_WDT          = $clog2(EFUSE_NWORDS);
    localparam WRITE_CNT        = 1000;

    localparam STATE_IDLE       = 0;
    localparam STATE_PRESET     = 1;
    localparam STATE_READ       = 2;
    localparam STATE_WRITE      = 3;

    // Manually generate buffers
    genvar i;
    generate
        for (i = 0; i < EFUSE_WORD_WIDTH; i = i + 1) begin
            // ensure write signals are held in 1 state during write disable, for example on power up
            (* keep, dont_touch  *)
            gf180mcu_fd_sc_mcu7t5v0__or2_4 prog_or_keep_cell (
                .A1(col_prog_n_reg[i]),
                .A2(write_disable_i),
                .Z(col_prog_n[i])
            );
        end

        for (i = 0; i < EFUSE_NWORDS; i = i + 1) begin
            (* keep, dont_touch  *)
            gf180mcu_fd_sc_mcu7t5v0__buf_2 bitsel_buf_keep_cell (
                .I(bit_sel_reg[i]),
                .Z(bit_sel[i])
            );
        end

        (* keep, dont_touch  *)
        gf180mcu_fd_sc_mcu7t5v0__dlyc_2 sense_dly_keep_cell (
            .I(sense_reg),
            .Z(sense_del)
        );
        (* keep, dont_touch  *)
        gf180mcu_fd_sc_mcu7t5v0__buf_8 sense_buf_keep_cell (
            .I(sense_del),
            .Z(sense)
        );
        (* keep, dont_touch  *)
        gf180mcu_fd_sc_mcu7t5v0__buf_8 preset_buf_keep_cell (
            .I(preset_n_reg),
            .Z(preset_n)
        );
    endgenerate

    always @(posedge wb_clk_i or posedge wb_rst_i) begin
        if (wb_rst_i) begin
            ack_o   <= 1'b0;
            dat_o   <= {WB_DAT_WIDTH{1'b0}};
            state   <= STATE_IDLE;

            preset_n_reg    <= 1'b1;
            sense_reg       <= 1'b0;
            col_prog_n_reg  <= {EFUSE_WORD_WIDTH{1'b1}};
            bit_sel_reg     <= {EFUSE_NWORDS{1'b0}};
        end else begin
            case(state)
                STATE_IDLE: begin
                    ack_o       <= 1'b0;
                    bit_sel_reg <= {EFUSE_NWORDS{1'b0}};

                    if (wb_stb_i & wb_cyc_i & ~ack_o) begin
                        if (wb_we_i) begin
                            state           <= STATE_WRITE;
                            bit_sel_reg     <= 2**(wb_adr_i[ADR_WDT-1:0]);
                            counter         <= WRITE_CNT;
                        end else begin
                            state           <= STATE_PRESET;
                            preset_n_reg    <= 1'b0;
                            sense_reg       <= 1'b1;
                        end
                    end
                end

                STATE_PRESET : begin
                    preset_n_reg    <= 1'b1;
                    bit_sel_reg     <= 2**(wb_adr_i[ADR_WDT-1:0]);
                    state           <= STATE_READ;
                end

                STATE_READ : begin
                    sense_reg   <= 1'b0;
                    state       <= STATE_IDLE;
                    ack_o       <= 1'b1;
                    dat_o       <= efuse_out;
                end

                STATE_WRITE : begin
                    if (counter === 0) begin
                        state           <= STATE_IDLE;
                        col_prog_n_reg  <= {EFUSE_WORD_WIDTH{1'b1}};
                        ack_o           <= 1'b1;
                    end else begin
                        col_prog_n_reg  <= ~wb_dat_i[EFUSE_WORD_WIDTH-1:0];
                        counter <= counter - 1;
                    end
                end

            endcase
        end 
    end
  
endmodule