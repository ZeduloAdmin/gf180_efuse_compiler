set period $::env(CLOCK_PERIOD)
set delta 0.5
set max_preset_time 2
create_clock -name wb_clk -period $period [get_ports wb_clk_i]

set in_delay [expr $::env(CLOCK_PERIOD) * 0.70]
set out_delay [expr $::env(CLOCK_PERIOD) * 0.70]
set max_in_tran 1.0

set wb_inputs [get_ports [list wb_stb_i wb_cyc_i wb_adr_i* wb_dat_i* wb_sel_i* wb_we_i]]

set_input_delay -max -clock wb_clk $in_delay $wb_inputs 
set_output_delay -max -clock wb_clk $out_delay [get_ports [list wb_dat_o* wb_ack_o]] 

set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__buf_2 -pin Z -max -from_pin I -input_transition_rise $max_in_tran -input_transition_fall $max_in_tran $wb_inputs

set derate 0.05
set_timing_derate -early [expr 1-$derate]
set_timing_derate -late [expr 1+$derate]

## MAX transition/cap
set max_cap 0.5
set_load $max_cap [all_outputs] 
set_max_trans 1.5 [current_design]
set_max_cap $max_cap [current_design]
