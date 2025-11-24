# Functions returning input/output pin of std cell connected to macro pin
proc cell_pin_from_macro {macro_pin} {
    return [get_pins -of_objects [get_nets -of_object $macro_pin] -filter {direction!=output}]
}
proc cell_pin_to_macro {macro_pin} {
    return [get_pins -of_objects [get_nets -of_object $macro_pin] -filter {direction!=input}]
}

# Functions to set delays on macro pins. Ugly, but no other way to do it in OpenROAD as
# most of macro pins are not timing endpoints.
proc set_input_delay_from_macro {pins clock min_delay max_delay} {
    foreach pin $pins {
        set_input_delay -clock $clock -max $max_delay [cell_pin_from_macro $pin]
        set_input_delay -clock $clock -min $min_delay [cell_pin_from_macro $pin]
    }
}
proc set_output_delay_to_macro {pins clock min_delay max_delay} {
    foreach pin $pins {
        set_output_delay -clock $clock -max $max_delay [cell_pin_to_macro $pin]
        set_output_delay -clock $clock -min $min_delay [cell_pin_to_macro $pin]
    }
}

set period $::env(CLOCK_PERIOD)
set delta 0.5
set max_preset_time 2
create_clock -name wb_clk -period $period [get_ports wb_clk_i]

#set_output_delay_to_macro [get_pins efuse_array/PRESET_N] wb_clk 0 [expr $period - $max_preset_time + $delta]
#set_output_delay_to_macro [get_pins efuse_array/SENSE] wb_clk [expr -$max_preset_time - $delta] 0
