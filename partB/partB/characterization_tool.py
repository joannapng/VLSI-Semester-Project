import json
import shutil
import subprocess
import re
import os
from multiprocessing import Pool
import time
import sys

comb_skeleton="./combinational_skeleton.spice"
dff_skeleton="./dff_skeleton.spice"
dffrs_skeleton="./dffrs_skeleton.spice"
lib_template="./template.lib"
output_lib="./mylibrary.lib"

Vdd = "2.5V"
vdd = 2.5
td = "5ns"

slew_derate_from_library = 1
slew_lower_threshold_pct_fall = 30.0
slew_upper_threshold_pct_fall = 70.0
slew_lower_threshold_pct_rise = 30.0
slew_upper_threshold_pct_rise = 70.0
input_threshold_pct_fall = 50.0
input_threshold_pct_rise = 50.0
output_threshold_pct_fall = 50.0
output_threshold_pct_rise = 50.0

Timing_template_6_7 = {"total_output_net_capacitance" : [0.0017, 0.0062, 0.0232, 0.0865, 0.3221, 1.2], 
                       "input_net_transition" : [0.0042, 0.0307, 0.0768, 0.192, 0.48, 1.2, 3]}

Constraint_5_5 = {"related_pin_transition": [0.0042, 0.0307, 0.0768, 0.48, 3], 
                    "constrained_pin_transition": [0.0042, 0.0307, 0.0768, 0.48, 3]}


start_time = time.time()

with open('config.json') as cfg:
    cells = json.load(cfg)

def calc_area(path):
    area = 0

    file = open(path, "r")

    data = file.read()
    regex1 = re.compile("ad=[0-9]+")
    regex2 = re.compile("as=[0-9]+")

    drain_areas = regex1.findall(data)
    source_areas = regex2.findall(data)

    for drain in drain_areas:
        area += float(drain[3:])
    
    for source in source_areas:
        area += float(source[3:])
    
    return(area)

n = len(sys.argv) 

if n != 2:
    print("Wrong number of arguments. Usage: python characterization_tool.py \"lib\" or \"v\"\n")
    quit()

if sys.argv[1] != "lib" and sys.argv[1] != "v":
    print("Second argument must be \"lib\" or \"v\"\n")
    quit()

if sys.argv[1] == "lib":
    for cell in cells:
        type = cells[cell]["type"]
        for pin in cells[cell]["pins"]:
            direction = cells[cell]["pins"][pin]["direction"]
            try:
                # test if the pin has a timing arcs
                timings = cells[cell]["pins"][pin]["timings"]
            except:
                continue
            
            for timing in cells[cell]["pins"][pin]["timings"]:  
                
                related_pin = cells[cell]["pins"][pin]["timings"][timing]["related_pin"]  
                # check if there is a when field
                try:
                    when = cells[cell]["pins"][pin]["timings"][timing]["when"]
                except:
                    when = ""
                
                # check if there is a timing_sense field
                try:
                    timing_sense = cells[cell]["pins"][pin]["timings"][timing]["timing_sense"]
                except:
                    timing_sense = ""

                # check if there is a timing_type field
                try:
                    timing_type = cells[cell]["pins"][pin]["timings"][timing]["timing_type"]
                except:
                    timing_type = ""

                for measurement in cells[cell]["pins"][pin]["timings"][timing]["measurements"]:
                

                    # set the name of the output file
                    if timing_sense == "":
                        if when == "":
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_type + "_" + measurement + ".mt")
                        else:
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_type + "_" + measurement + "_" + when + ".mt")
                    else:
                        if when == "":
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + ".mt")
                        else:
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + "_" + when + ".mt")
                    
                    # delete the old output file if it exists
                    
                    if os.path.exists(results_name):
                        os.remove(results_name)
                    
                    # create new new spice deck based on the skeleton
                    cell_file = "cell.spice"
                    
                    if cell == "DFF":
                        shutil.copyfile(dff_skeleton, cell_file)
                    elif cell == "DFFRS":
                        shutil.copyfile(dffrs_skeleton, cell_file)
                    else:
                        shutil.copyfile(comb_skeleton, cell_file)

                    # replace PATH and CELL
                    path = cells[cell]["path"]
                    f = open(cell_file, "r")
                    filedata = f.read()

                    newdata = filedata.replace("PATH", path)
                    newdata = newdata.replace("CELL", cell)

                    # set the initial voltages (and output capacitances)

                    if type == "combinational":
                        if measurement=="cell_rise" or measurement=="rise_transition":
                            newdata=newdata.replace("INIT_OUT", "0")
                        elif measurement=="cell_fall" or measurement=="fall_transition":
                            newdata = newdata.replace("INIT_OUT", Vdd)  
                    else:
                        # if the pin is Q or Qbar
                        if direction == "output":
                            if measurement=="cell_rise" or measurement=="rise_transition":
                                if pin == "Q":
                                    # substitute the larger string first
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                                else:
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)
                            elif measurement=="cell_fall" or measurement=="fall_transition":
                                if pin == "Q":
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)
                                else:
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                        # if the direction is input, then the timing has a timing_type
                        else:
                            [constraint, clk_edge] = timing_type.split('_')

                            if constraint == "setup":
                                if measurement=="rise_constraint":
                                    # substitute the larger string first
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                                elif measurement=="fall_constraint":
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)  
                                
                                # select the largest output capacitance
                                total_output_net_capacitance = Timing_template_6_7["total_output_net_capacitance"][-1]
                            elif constraint == "hold":
                                if measurement=="rise_constraint":
                                    # substitute the larger string first
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)
                                elif measurement=="fall_constraint":
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                                
                                # select the smallest output capacitance
                                total_output_net_capacitance = Timing_template_6_7["total_output_net_capacitance"][0]
                            elif constraint == "recovery":
                                if pin=="S":
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)
                                elif pin=="R":
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                                total_output_net_capacitance = Timing_template_6_7["total_output_net_capacitance"][-1]
                            else:
                                if pin=="S":
                                    newdata = newdata.replace("R_INIT_OUT", Vdd)
                                    newdata = newdata.replace("INIT_OUT", "0")
                                elif pin=="R":
                                    newdata = newdata.replace("R_INIT_OUT", "0")
                                    newdata = newdata.replace("INIT_OUT", Vdd)
                                total_output_net_capacitance = Timing_template_6_7["total_output_net_capacitance"][0]
                            newdata = newdata.replace("OUTPUT_CAPACITANCE", str(total_output_net_capacitance))
                            newdata = newdata.replace("tran 1n 5u", "tran 10n 2u")
                        # write the initial values (and output capacitance) in the cell.spice file    
                    f = open(cell_file, "w")
                    f.write(newdata)
                    f.close()
                    
                    # timing arcs, not constraint arcs
                    if direction == "output":
                        old_output_net_capacitance = "OUTPUT_CAPACITANCE"

                        for total_output_net_capacitance in Timing_template_6_7["total_output_net_capacitance"]:

                            # replace the old value of output net capacitance with the new value
                            f = open(cell_file, "r")
                            filedata = f.read()

                            newdata = filedata.replace(str(old_output_net_capacitance), str(total_output_net_capacitance))
                            f = open(cell_file, "w")
                            f.write(newdata)
                            f.close()
                            
                            old_output_net_capacitance = total_output_net_capacitance

                            # Create the input file
                            for input_net_transition in Timing_template_6_7["input_net_transition"]:
                                    inputs_file = open("inputs.spice", "w")

                                    if when != "":
                                        # set the side pins with the appropriate values depending on the "when" field
                                        conditions = when.split()

                                        # t is used only in the DFFRS case
                                        t = 0
                                        for cond in conditions:
                                            if cond!= "&" and cond!="|":
                                                if cond[0]=="!":
                                                    if cond[1:] == "CLK":
                                                        t = 1.25
                                                    else:
                                                        if t != 3.75:
                                                            inputs_file.write("V{0} {0} 0 DC 0\n".format(cond[1:]))
                                                        else:
                                                            if cell != "DFFRS" or (cell == "DFFRS" and cond != "!D"):
                                                                inputs_file.write("V{0} {0} 0 DC 0\n".format(cond[1:]))
                                                            else:
                                                                if measurement == "cell_fall" or measurement == "fall_transition":
                                                                    if pin == "Q":
                                                                        inputs_file.write("VD D 0 pwl (0 {0} 3u {0} 3.001u 0)\n".format(Vdd))
                                                                    else:
                                                                        inputs_file.write("VD D 0 DC 0\n")    
                                                                else:
                                                                    if pin == "Q":
                                                                        inputs_file.write("VD D 0 DC 0\n")
                                                                    else: 
                                                                        inputs_file.write("VD D 0 pwl (0 {0} 3u {0} 3.001u 0)\n".format(Vdd))
                                                else:
                                                    if cond == "CLK":
                                                        t = 3.75
                                                    else:
                                                        if t != 3.75:
                                                            inputs_file.write("V{0} {0} 0 DC {1}\n".format(cond, Vdd))
                                                        else:
                                                            if cell != "DFFRS" or (cell == "DFFRS" and cond != "D"):
                                                                inputs_file.write("V{0} {0} 0 DC {1}\n".format(cond, Vdd))
                                                            else:
                                                                if measurement == "cell_rise" or measurement == "rise_transition":
                                                                    if pin == "Q":
                                                                        inputs_file.write("VD D 0 pwl (0 0 3u 0 3.001u {0})\n".format(Vdd))
                                                                    else: 
                                                                        inputs_file.write("VD D 0 DC {0}\n".format(Vdd))
                                                                else:
                                                                    if pin == "Q":
                                                                        inputs_file.write("VD D 0 DC {0}\n".format(Vdd))
                                                                    else: 
                                                                        inputs_file.write("VD D 0 pwl (0 0 3u 0 3.001u {0})\n".format(Vdd))
                                    # find the 0-100% input net transition
                                    input_net_transition = input_net_transition * 100.0 / (slew_upper_threshold_pct_rise - slew_lower_threshold_pct_fall)

                                    # if the cell is sequential we must set the clock
                                    if type == "sequential":
                                        param_str = ".param clk_period=5u half_period=2.5u tr={0}ns tf={1}ns td=2.5u\n".format(str(input_net_transition), str(input_net_transition)) 
                                        inputs_file.write(param_str)

                                        clk_str = "Vclk CLK 0 pulse (0 {vdd} {td} {tr} {tf} {half_period} {clk_period})\n"
                                        not_clk_str = "Vnot_clk NOT_CLK 0 pulse (0 {vdd} 0 {tr} {tf} {half_period} {clk_period})\n"
                                
                                        inputs_file.write(clk_str)
                                        inputs_file.write(not_clk_str)

                                        # if the related_pin is clock, then we must set D to the appropriate value
                                        if related_pin == "CLK":
                                            if measurement == "cell_rise" or measurement == "rise_transition":
                                                if pin=="Q":
                                                    d_value = Vdd
                                                elif pin=="Qbar":
                                                    d_value = "0"
                                            elif measurement == "cell_fall" or measurement == "fall_transition":
                                                if pin=="Q":
                                                    d_value = "0"
                                                elif pin=="Qbar":
                                                    d_value = Vdd
                                            
                                            if d_value==Vdd:
                                                d_str = "VD D 0 pwl (0 0 0.1n 0 0.3n {0})\n".format(Vdd)
                                            else:
                                                d_str = "VD D 0 pwl (0 {0} 0.1n {0} 0.3n 0)\n".format(Vdd)
                                            inputs_file.write(d_str)

                                            inputs_file.write("VS S 0 DC 0\n")
                                            inputs_file.write("VR R 0 DC 0\n")
                                        elif related_pin == "R" or related_pin == "S":
                                            if measurement == "cell_rise" or measurement == "rise_transition":
                                                if timing_sense == "positive_unate":
                                                    inputs_file.write("V{0} {0} 0 pwl (0 0 {1}u 0 {2}u {3})\n".format(related_pin, str(t), str(t + input_net_transition/1000.0), Vdd))
                                                else:
                                                    inputs_file.write("V{0} {0} 0 pwl (0 {1} {2}u {1} {3}u 0)\n".format(related_pin, Vdd, str(t), str(t + input_net_transition/1000.0), Vdd))
                                            elif measurement == "cell_fall" or measurement == "fall_transition":
                                                if timing_sense == "negative_unate":
                                                    inputs_file.write("V{0} {0} 0 pwl (0 0 {1}u 0 {2}u {3})\n".format(related_pin, str(t), str(t + input_net_transition/1000.0), Vdd))
                                                else:
                                                    inputs_file.write("V{0} {0} 0 pwl (0 {1} {2}u {1} {3}u 0)\n".format(related_pin, Vdd, str(t), str(t + input_net_transition/1000.0), Vdd))     

                                    else:
                                        # if the cell is combinational just set the related pin input
                                        if measurement=="cell_rise" or measurement=="rise_transition":
                                            if timing_sense == "positive_unate":
                                                init_value = "0"
                                                final_value = Vdd
                                            elif timing_sense == "negative_unate":
                                                init_value = Vdd
                                                final_value = "0"
                                        elif measurement=="cell_fall" or measurement=="fall_transition":
                                            if timing_sense == "negative_unate":
                                                init_value = "0"
                                                final_value = Vdd
                                            elif timing_sense == "positive_unate":
                                                init_value = Vdd
                                                final_value = "0"

                                        inputs_file.write(str("V" + related_pin + " " + related_pin + " 0 pwl (" + \
                                                    "0 " + init_value + " " + str(td) + " " + init_value + " {" + str(td) + " + " + str(input_net_transition) + "ns} " \
                                                    + str(final_value) + ")\n"))
                                    inputs_file.close()

                                    # write the measurements file

                                    meas_file = open("meas.spice", "w")

                                    if type == "combinational":
                                        if measurement=="cell_rise" and timing_sense=="positive_unate":
                                            # input and output both rise
                                            trig_val = input_threshold_pct_rise/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                    related_pin, trig_val, pin, targ_val))
                                        elif measurement=="cell_rise" and timing_sense=="negative_unate":
                                            # output rises when inputs falls
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                    related_pin, trig_val, pin, targ_val))
                                        elif measurement=="cell_fall" and timing_sense=="positive_unate":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_fall/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                    related_pin, trig_val, pin, targ_val))
                                        elif measurement=="cell_fall" and timing_sense=="negative_unate":
                                            trig_val = input_threshold_pct_rise/100.0 * vdd
                                            targ_val = output_threshold_pct_fall/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                    related_pin, trig_val, pin, targ_val))
                                        elif measurement=="rise_transition":
                                            trig_val = slew_lower_threshold_pct_rise/100.0*vdd
                                            targ_val = slew_upper_threshold_pct_rise/100.0*vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                    pin, trig_val, pin, targ_val))
                                        elif measurement=="fall_transition":
                                            trig_val = slew_upper_threshold_pct_fall/100.0*vdd
                                            targ_val = slew_lower_threshold_pct_fall/100.0*vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                    pin, trig_val, pin, targ_val))
                                    else:
                                        if related_pin == "CLK":
                                            if measurement=="cell_rise":
                                                if timing_type=="rising_edge":
                                                    trig_val = input_threshold_pct_rise/100.0 * vdd
                                                    targ_val = output_threshold_pct_rise/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                                elif timing_type == "falling_edge":
                                                    trig_val = input_threshold_pct_fall/100.0 * vdd
                                                    targ_val = output_threshold_pct_rise/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                            elif measurement == "cell_fall":
                                                if timing_type=="rising_edge":
                                                    trig_val = input_threshold_pct_rise/100.0 * vdd
                                                    targ_val = output_threshold_pct_fall/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                                elif timing_type == "falling_edge":
                                                    trig_val = input_threshold_pct_fall/100.0 * vdd
                                                    targ_val = output_threshold_pct_fall/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                            elif measurement == "rise_transition":
                                                trig_val = slew_lower_threshold_pct_rise/100.0*vdd
                                                targ_val = slew_upper_threshold_pct_rise/100.0*vdd
                                                meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        pin, trig_val, pin, targ_val))
                                            elif measurement == "fall_transition":
                                                trig_val = slew_upper_threshold_pct_fall/100.0*vdd
                                                targ_val = slew_lower_threshold_pct_fall/100.0*vdd
                                                meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        pin, trig_val, pin, targ_val))
                                        else:
                                            if measurement=="cell_rise":
                                                if timing_sense=="positive_unate":
                                                    trig_val = input_threshold_pct_rise/100.0 * vdd
                                                    targ_val = output_threshold_pct_rise/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                                elif timing_sense == "negative_unate":
                                                    trig_val = input_threshold_pct_fall/100.0 * vdd
                                                    targ_val = output_threshold_pct_rise/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                            elif measurement == "cell_fall":
                                                if timing_sense=="negative_unate":
                                                    trig_val = input_threshold_pct_rise/100.0 * vdd
                                                    targ_val = output_threshold_pct_fall/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                                elif timing_sense == "positive_unate":
                                                    trig_val = input_threshold_pct_fall/100.0 * vdd
                                                    targ_val = output_threshold_pct_fall/100.0 * vdd
                                                    meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        related_pin, trig_val, pin, targ_val))
                                            elif measurement == "rise_transition":
                                                trig_val = slew_lower_threshold_pct_rise/100.0*vdd
                                                targ_val = slew_upper_threshold_pct_rise/100.0*vdd
                                                meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1".format(measurement, \
                                                        pin, trig_val, pin, targ_val))
                                            elif measurement == "fall_transition":
                                                trig_val = slew_upper_threshold_pct_fall/100.0*vdd
                                                targ_val = slew_lower_threshold_pct_fall/100.0*vdd
                                                meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1".format(measurement, \
                                                        pin, trig_val, pin, targ_val))
                                    
                                    meas_file.close()

                                    #if results_name == "DFFRS_Qbar_R_positive_unate_cell_rise_!CLK & !D & !S.mt":
                                    #    exit()
                                    # ngspice command
                                    cmd = "ngspice cell.spice -b"

                                    # write the output to a temporary file
                                    temp_results = open("temp_results.txt", "w")

                                    try:
                                        process = subprocess.run(cmd.split(), stdout=temp_results)
                                    except:
                                        print("error")
                                        results = open(results_name, "a+")
                                        results.write("0.0\n")
                                        results.close()
                                        continue

                                    temp_results = open("temp_results.txt", "r")
                                    filedata = temp_results.read()
                                    
                                    # the measurement we ant is before the targ keyword
                                    regex = re.compile("{}.*=.*targ".format(measurement))
                                        
                                    res = regex.search(filedata)    

                                    if res is None:
                                        results = open(results_name, "a+")
                                        results.write("0.0\n")
                                        results.close() 
                                        continue                  

                                    # append the results to the file that corresponds to the correct timing arc         
                                    results = open(results_name, "a+")
                                    results.write(((res.group()).split())[2] + "\n")
                                    results.close()
                    # if direction is input, we know it is a sequential cell
                    elif direction == "input":
                        for related_pin_transition in Constraint_5_5["related_pin_transition"]:
                                related_pin_transition = related_pin_transition * 100.0 / (slew_upper_threshold_pct_rise - slew_lower_threshold_pct_rise)
                                for constrained_pin_transition in Constraint_5_5["constrained_pin_transition"]:
                                    constrained_pin_transition = constrained_pin_transition * 100.0 / (slew_upper_threshold_pct_rise - slew_lower_threshold_pct_rise)    

                                    inputs_file = open("inputs.spice", "w")

                                    param_str = ".param clk_period=1u half_period=0.5u tr={0}ns tf={1}ns td=0.5u\n".format(str(related_pin_transition), str(related_pin_transition)) 
                                    inputs_file.write(param_str)

                                    # CLK input
                                    clk_str = "Vclk CLK 0 pulse (0 {vdd} {td} {tr} {tf} {half_period} {clk_period})\n"
                                    not_clk_str = "Vnot_clk NOT_CLK 0 pulse (0 {vdd} 0 {tr} {tf} {half_period} {clk_period})\n"
                            
                                    inputs_file.write(clk_str)
                                    inputs_file.write(not_clk_str) 

                                    # Set side inputs
                                    if when != "":
                                        inputs_str = ""
                                        conditions = when.split()

                                        for cond in conditions:
                                            if cond!="&" and cond!="|":
                                                if cond[0] == "!":
                                                    inputs_str += "V{0} {0} 0 DC 0\n".format(str(cond[1]))
                                                else:
                                                    inputs_str += "V{0} {0} 0 DC {1}\n".format(str(cond[0]), Vdd)
                                        inputs_file.write(inputs_str)       
                                
                                    # Set D to the appropriate value
                                    if constraint == "setup":
                                        if measurement=="rise_constraint":
                                            d_value = Vdd
                                        elif measurement == "fall_constraint":
                                            d_value = "0"

                                        if d_value==Vdd:
                                            d_str = "VD D 0 pwl (0 0 0.1n 0 {0}n {1})".format(str(0.1+constrained_pin_transition), Vdd)
                                        else:
                                            d_str = "VD D 0 pwl (0 {0} 0.1n {0} {1}n 0)".format(Vdd, str(0.1+constrained_pin_transition))    
                                        inputs_file.write(d_str)
                                    elif constraint == "hold":
                                        if measurement=="rise_constraint":
                                            d_value = "0"
                                        elif measurement == "fall_constraint":
                                            d_value = Vdd

                                        if d_value==Vdd:
                                            d_str = "VD D 0 pwl (0 0 0.1n 0 {0}n {1})".format(str(0.1+constrained_pin_transition), Vdd)
                                        else:
                                            d_str = "VD D 0 pwl (0 {0} 0.1n {0} {1}n 0)".format(Vdd, str(0.1+constrained_pin_transition))
                                        inputs_file.write(d_str)  
                                    elif constraint == "recovery":  
                                        if pin == "S":
                                            d_str = "VD D 0 pwl (0 2.5V 0.1n 2.5V {0}n 0)\n".format(str(0.1 + constrained_pin_transition))
                                        elif pin == "R":
                                            d_str = "VD D 0 pwl (0 0 0.1n 0 {0}n 2.5V)\n".format(str(0.1 + constrained_pin_transition))
                                        
                                        inputs_file.write(d_str)

                                        deassert_str = ".param deassert=0\n"

                                        if measurement=="fall_constraint":
                                            deassert_str += "V{0} {0} 0 DC 0\n".format(pin)
                                        elif measurement=="rise constraint":
                                            deassert_str +=  "V{0} {0} 0 DC {1}\n".format(pin, Vdd)

                                        inputs_file.write(deassert_str)
                                    else:
                                        if pin == "S":
                                            d_str = "VD D 0 pwl (0 2.5V 0.1n 2.5V {0}n 0)\n".format(str(0.1 + constrained_pin_transition))
                                        elif pin == "R":
                                            d_str = "VD D 0 pwl (0 0 0.1n 0 {0}n 2.5V)\n".format(str(0.1 + constrained_pin_transition))
                                        
                                        inputs_file.write(d_str)

                                        deassert_str = ".param deassert=0\n"

                                        if measurement=="fall_constraint":
                                            deassert_str += "V{0} {0} 0 DC 0\n".format(pin)
                                        elif measurement=="rise constraint":
                                            deassert_str +=  "V{0} {0} 0 DC {1}\n".format(pin, Vdd)

                                        inputs_file.write(deassert_str)

                                    inputs_file.close()
                                    meas_file = open("meas.spice", "w")

                                    if constraint == "setup":
                                        if measurement=="rise_constraint" and clk_edge == "rising":
                                            trig_val = input_threshold_pct_rise/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))
                                            meas_file.write(".measure tran setup param='half_period-start'")
                                        elif measurement=="rise_constraint" and clk_edge == "falling":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} rise=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))
                                            meas_file.write(".measure tran setup param='clk_period-start'")
                                        elif measurement=="fall_constraint" and clk_edge == "rising":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} fall=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val)) 
                                            meas_file.write(".measure tran setup param='half_period-start'")
                                        elif measurement=="fall_constraint" and clk_edge == "falling":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_fall/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))     
                                            meas_file.write(".measure tran setup param='clk_period-start'")

                                        meas_file.close()

                                        # first find the propagation delay clk->q without setup violation
                                        cmd = "ngspice cell.spice -b"
                                        results = open("results.txt", "w")
                                        
                                        try:
                                            process = subprocess.run(cmd.split(), stdout = results, check=True)
                                        except:
                                            continue
                                    
                                        results.close()
                                        results = open("results.txt", "r")
                                        filedata = results.read()
                                        regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                        c2q = regex.search(filedata)
                                        c2q = ((c2q.group()).split())[2]
                                        
                                        c2q = float(c2q)
                                        cur_c2q = float(c2q)

                                        if clk_edge == "rising":
                                            start = 0.5
                                        else:
                                            start = 0.5

                                        prev_start = start
                                        dt = 0.001

                                        # find the starting point for setup
                                        while True:
                                            f = open("inputs.spice", "r")
                                            filedata = f.read()

                                            new_d_str = ".param start={0}us\n".format(str(start))

                                            if d_value == "0":
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += Vdd
                                                new_d_str += " " + str(start) + "us" + " " + Vdd
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us 0)"
                                            elif d_value == Vdd:
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += "0"
                                                new_d_str += " " + str(start) + "us" + " " + "0"
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us " + Vdd + ")"

                                            newdata = filedata.replace(d_str, new_d_str)
                                            d_str = new_d_str
                                            
                                            f = open("inputs.spice", "w")
                                            f.write(newdata)
                                            print(start)
                                            
                                            f.close()

                                            results = open("results.txt", "w")
                                            try:
                                                process = subprocess.run(cmd.split(), stdout = results, check=True)
                                            except subprocess.CalledProcessError:
                                                print("error")

                                            results.close()
                                            results = open("results.txt", "r")
                                            filedata = results.read()
                                            regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                            prev_c2q = float(cur_c2q)

                                            cur_c2q = regex.search(filedata)
                                            cur_c2q = ((cur_c2q.group()).split())[2]
                                            cur_c2q = float(cur_c2q)

                                            if cur_c2q >= 1.05*c2q:
                                                start -= dt
                                            else:
                                                break

                                            if start <= 0:
                                                break
                                    
                                        if start <= 0:
                                            setup = 0.0
                                            results = open(results_name, "a+")
                                            results.write(str(setup) + "\n")
                                            results.close()
                                            continue

                                        # divide the resolution dt by an additional 100
                                        dt = 0.000001
                                        setup = 0
                                        prev_setup = setup
                                        cur_c2q = float(c2q)

                                        while (cur_c2q < 1.05*float(c2q)):
                                            f = open("inputs.spice", "r")
                                            filedata = f.read()

                                            new_d_str = ".param start={0}us\n".format(start)

                                            if d_value == "0":
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += Vdd
                                                new_d_str += " " + str(start) + "us" + " " + Vdd
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us 0)"
                                            elif d_value == Vdd:
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += "0"
                                                new_d_str += " " + str(start) + "us" + " " + "0"
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us " + Vdd + ")"
                                            
                                            newdata = filedata.replace(d_str, new_d_str)
                                            d_str = new_d_str
                                            prev_start = start
                                            start += dt
                                            
                                            f = open("inputs.spice", "w")
                                            f.write(newdata)

                                            f.close()

                                            results = open("results.txt", "w")

                                            try:
                                                process = subprocess.run(cmd.split(), stdout = results, check=True)
                                            except subprocess.CalledProcessError:
                                                print("error")

                                            results.close()
                                            results = open("results.txt", "r")
                                            filedata = results.read()
                                            regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                            prev_c2q = float(cur_c2q)

                                            cur_c2q = regex.search(filedata)
                                            cur_c2q = ((cur_c2q.group()).split())[2]   

                                            print("\n\n" + str(c2q) + " " + str(cur_c2q)) 

                                            cur_c2q = float(cur_c2q)
                                        
                                            regex = re.compile(r'(setup.*=.*[0-9e-].*)')
                                            prev_setup = float(setup)

                                            setup = regex.search(filedata)
                                            setup = ((setup.group()).split())[2]
                                            print(setup)
                                            setup = float(setup)
                                            if setup < 0:
                                                setup = 0
                                                break
                                            if start >= 0.5:
                                                setup = 0
                                                break

                                        results = open(results_name, "a+")
                                        results.write(str(1.3*setup) + "\n")
                                        results.close()
                                    elif constraint == "hold":
                                        if measurement=="rise_constraint" and clk_edge == "rising":
                                            trig_val = input_threshold_pct_rise/100.0 * vdd
                                            targ_val = output_threshold_pct_fall/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} fall=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))
                                            meas_file.write(".measure tran hold param='start-half_period'")
                                        elif measurement=="rise_constraint" and clk_edge == "falling":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_fall/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} fall=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))
                                            meas_file.write(".measure tran hold param='start-clk_period'")
                                        elif measurement=="fall_constraint" and clk_edge == "rising":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} rise = 1 targ V({3}) val={4} rise=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val)) 
                                            meas_file.write(".measure tran hold param='start-half_period'")
                                        elif measurement=="fall_constraint" and clk_edge == "falling":
                                            trig_val = input_threshold_pct_fall/100.0 * vdd
                                            targ_val = output_threshold_pct_rise/100.0 * vdd
                                            meas_file.write(".measure tran {0} trig V({1}) val={2} fall = 1 targ V({3}) val={4} rise=1\n".format\
                                                ("c2q_delay", "CLK", trig_val, "Q", targ_val))     
                                            meas_file.write(".measure tran hold param='start-clk_period'")

                                        meas_file.close()  

                                        # first find the propagation delay clk->q without hold violation
                                        cmd = "ngspice cell.spice -b"
                                        results = open("results.txt", "w")
                                        
                                        try:
                                            process = subprocess.run(cmd.split(), stdout = results, check=True)
                                        except:
                                            continue  

                                        results.close()
                                        results = open("results.txt", "r")
                                        filedata = results.read()
                                        regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                        c2q = regex.search(filedata)
                                        c2q = ((c2q.group()).split())[2]
                                        
                                        c2q = float(c2q)
                                        cur_c2q = float(c2q)    

                                        if clk_edge == "rising":
                                            start = 0.5
                                        else:
                                            start = 1

                                        prev_start = start
                                        dt = 0.001

                                        # time.sleep(4)
                                        while True:
                                            f = open("inputs.spice", "r")
                                            filedata = f.read()

                                            new_d_str = ".param start = {0}us\n".format(str(start))

                                            if d_value == Vdd:
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += Vdd
                                                new_d_str += " " + str(start) + "us" + " " + Vdd
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us 0)"
                                            elif d_value == "0":
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += "0"
                                                new_d_str += " " + str(start) + "us" + " " + "0"
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us " + Vdd + ")"
                                                

                                            newdata = filedata.replace(d_str, new_d_str)
                                            d_str = new_d_str

                                            f = open("inputs.spice", "w")
                                            f.write(newdata)
                                            f.close()

                                            results = open("results.txt", "w")

                                            try:
                                                process = subprocess.run(cmd.split(), stdout = results, check=True)
                                            except subprocess.CalledProcessError:
                                                print("error")

                                            results.close()
                                            results = open("results.txt", "r")
                                            filedata = results.read()
                                            regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                            prev_c2q = float(cur_c2q)

                                            try: 
                                                cur_c2q = regex.search(filedata)
                                                cur_c2q = ((cur_c2q.group()).split())[2]
                                                cur_c2q = float(cur_c2q)
                                            except:
                                                start += dt
                                                cur_c2q = 1.05*c2q
                                                continue
                                            
                                            if cur_c2q >= 1.05*c2q:
                                                start += dt         
                                            else:
                                                break

                                            if start >= 1:
                                                break

                                        if start == 0.5 or start >= 1 :
                                            hold = 0.0
                                            results = open(results_name, "a+")
                                            results.write(str(1.3*hold) + "\n")
                                            results.close() 
                                            continue 

                                        # time.sleep(4)
                                        
                                        # find the appropriate resolution
                                        dt = 0.000001

                                        hold = 0
                                        prev_hold = hold
                                        cur_c2q = float(c2q)

                                        while (cur_c2q < 1.05*float(c2q)):
                                            f = open("inputs.spice", "r")
                                            filedata = f.read()

                                            new_d_str = ".param start = {0}us\n".format(str(start))

                                            if d_value == Vdd:
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += Vdd
                                                new_d_str += " " + str(start) + "us" + " " + Vdd
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us 0)"
                                            elif d_value == "0":
                                                new_d_str += "VD D 0 pwl (0 "
                                                new_d_str += "0"
                                                new_d_str += " " + str(start) + "us" + " " + "0"
                                                new_d_str += " " + str(start+constrained_pin_transition/1000.0) + "us " + Vdd + ")"
                                                

                                            newdata = filedata.replace(d_str, new_d_str)
                                            d_str = new_d_str
                                            prev_start = start
                                            start -= dt
                                            
                                            f = open("inputs.spice", "w")
                                            f.write(newdata)

                                            f.close()

                                            results = open("results.txt", "w")

                                            try:
                                                process = subprocess.run(cmd.split(), stdout = results, check=True)
                                            except subprocess.CalledProcessError:
                                                print("error")

                                            results.close()
                                            results = open("results.txt", "r")
                                            filedata = results.read()
                                            regex = re.compile(r'(c2q_delay.*=.*targ)')
                                        
                                            prev_c2q = float(cur_c2q)

                                            cur_c2q = regex.search(filedata)
                                            cur_c2q = ((cur_c2q.group()).split())[2]   

                                            print("\n\n" + str(c2q) + " " + str(cur_c2q)) 

                                            cur_c2q = float(cur_c2q)

                                            regex = re.compile(r'(hold.*=.*[0-9e-].*)')
                                            prev_hold = float(hold)
                                            
                                            hold = regex.search(filedata)
                                            hold = ((hold.group()).split())[2]

                                            print(hold)
                                            hold = float(hold)

                                            if start < 0.5:
                                                hold = 0
                                                break

                                            if hold < 0 or start > 0.5*10**(-6):
                                                hold = 0
                                                break
                                        
                                        results = open(results_name, "a+")
                                        results.write(str(1.3*hold) + "\n")
                                        results.close()
                                    elif constraint=="recovery":
                                        meas_file = open("meas.spice", "w")

                                        if pin == "S":
                                            if clk_edge == "rising":
                                                deassert = 0.5
                                                meas_file.write(".measure tran value min V(Q) from=0.5u to=1.5u\n")
                                                meas_file.write(".measure tran recovery param='half_period-deassert'")
                                            elif clk_edge == "falling":
                                                deassert = 1
                                                meas_file.write(".measure tran value min V(Q) from=1u to=2u\n")
                                                meas_file.write(".measure tran recovery param='clk_period-deassert'")
                                        elif pin == "R":
                                            if clk_edge == "rising":
                                                deassert = 0.5
                                                trig_val = input_threshold_pct_rise/100.0 * vdd
                                                targ_val = output_threshold_pct_rise/100.0 * vdd
                                                meas_file.write(".measure tran value max V(Q) from=0.5u to=1.5u\n")
                                                meas_file.write(".measure tran recovery param='half_period-deassert'")
                                            elif clk_edge == "falling":
                                                deassert = 1
                                                trig_val = input_threshold_pct_fall/100.0 * vdd
                                                targ_val = output_threshold_pct_rise/100.0 * vdd
                                                meas_file.write(".measure tran value max V(Q) from=1u to=2u\n")
                                                meas_file.write(".measure tran recovery param='clk_period-deassert'")

                                        meas_file.close()

                                        cmd = "ngspice cell.spice -b"
                                        results = open("results.txt", "w")

                                        if pin == "S":
                                            min = 0
                                            prev_deassert = deassert 
                                            recovery = 0
                                            prev_recovery = recovery

                                            dt = 0.001

                                            while True:
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VS S 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VS S 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str 

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)
                                                f.close()

                                
                                                results = open("results.txt", "w")

                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    continue

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                min = regex.search(filedata) 
                                                min = ((min.group()).split())[2]

                                                if float(min) > 0.1*vdd:
                                                    deassert -= dt
                                                else:
                                                    break  
                                            
                                                if deassert <= 0:
                                                    break

                                            if deassert <= 0:
                                                recovery = 0.0
                                                results = open(results_name, "a+")
                                                results.write(str(recovery) + "\n")
                                                results.close() 
                                            prev_deassert = deassert

                                            min = 0
                                            recovery = 0
                                            prev_recovery = recovery
                                            dt = 0.00001

                                            while float(min) < 0.1*vdd:
                                                    
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VS S 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VS S 0 pwl ( 0 2.5V 0.1n 2.5V {0}u 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str

                                                prev_deassert = deassert 
                                                deassert += dt

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)

                                                f.close()
                                                results = open("results.txt", "w")

                                                cmd = "ngspice cell.spice -b"
                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    print("error")

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                min = regex.search(filedata) 
                                                min = ((min.group()).split())[2]

                                                regex = re.compile(r'(recovery.*=.*[0-9e-].*)')
                                                prev_recovery = float(recovery)

                                                recovery = regex.search(filedata)
                                                recovery = ((recovery.group()).split())[2]
                                                print(min)
                                                print(recovery)
                                                print(deassert)
                                                recovery = float(recovery)  

                                                if deassert >= 0.5:
                                                    recovery = 0.0
                                                    break 
                                                if recovery < 0:
                                                    recovery = 0.0
                                                    break         
                                        elif pin == "R":
                                            max = 0
                                            prev_deassert = deassert 
                                            recovery = 0
                                            prev_recovery = recovery

                                            dt = 0.001

                                            while True:
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VR R 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VR R 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str 

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)
                                                f.close()

                                                results = open("results.txt", "w")

                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    continue

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                max = regex.search(filedata) 
                                                max = ((max.group()).split())[2]

                                                if float(max) > 0.9*vdd:
                                                    deassert -= dt
                                                else:
                                                    break  
                                                if deassert <= 0:
                                                    break

                                            if deassert <= 0:
                                                results = open(results_name, "a+")
                                                results.write(str(recovery) + "\n")
                                                results.close()
                                                continue
                                            prev_deassert = deassert

                                            max = 0
                                            recovery = 0
                                            prev_recovery = recovery
                                            dt = 0.00001

                                            while float(max) < 0.9*vdd:
                                                    
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VR R 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VR R 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str

                                                prev_deassert = deassert 
                                                deassert += dt

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)

                                                f.close()
                                                results = open("results.txt", "w")

                                                cmd = "ngspice cell.spice -b"
                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    print("error")

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                max = regex.search(filedata) 
                                                max = ((max.group()).split())[2]

                                                regex = re.compile(r'(recovery.*=.*[0-9e-].*)')
                                                prev_recovery = float(recovery)

                                                recovery = regex.search(filedata)
                                                recovery = ((recovery.group()).split())[2]
                                                
                                                recovery = float(recovery)   
                                                if recovery < 0:
                                                    recovery = 0.0
                                                    break     
                                                if deassert >= 0.5:
                                                    recovery = 0.0
                                                    break         
                                        results = open(results_name, "a+")
                                        results.write(str(1.3*recovery) + "\n")
                                        results.close()
                                    else:
                                        meas_file = open("meas.spice", "w")

                                        if pin == "S":
                                            if clk_edge == "rising":
                                                deassert = 0.51
                                                meas_file.write(".measure tran value min V(Q) from=0.5u to=1.5u\n")
                                                meas_file.write(".measure tran removal param='deassert-half_period'")
                                            elif clk_edge == "falling":
                                                deassert = 1.01
                                                meas_file.write(".measure tran value min V(Q) from=1u to=2u\n")
                                                meas_file.write(".measure tran removal param='deassert-clk_period'")
                                        elif pin == "R":
                                            if clk_edge == "rising":
                                                deassert = 0.51
                                                meas_file.write(".measure tran value max V(Q) from=0.5u to=1.5u\n")
                                                meas_file.write(".measure tran removal param='deassert-half_period'")
                                            elif clk_edge == "falling":
                                                deassert = 1.01
                                                meas_file.write(".measure tran value max V(Q) from=1u to=2u\n")
                                                meas_file.write(".measure tran removal param='deassert-clk_period'")

                                        meas_file.close()

                                        cmd = "ngspice cell.spice -b"
                                        results = open("results.txt", "w")

                                        if pin == "S":
                                            min = vdd
                                            prev_deassert = deassert 
                                            removal = 0
                                            prev_removal = removal

                                            dt = 0.01

                                            while True:
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VS S 0 pwl ( 0 0 0.1n 0 {0}u 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VS S 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str 

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)
                                                f.close()

                                
                                                results = open("results.txt", "w")

                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    continue

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                min = regex.search(filedata) 
                                                min = ((min.group()).split())[2]

                                                if float(min) < 0.9*vdd:
                                                    deassert += dt
                                                else:
                                                    break  
                                            
                                                if deassert >= 1:
                                                    break

                                            if deassert >= 1:
                                                removal = 0.0
                                                results = open(results_name, "a+")
                                                results.write(str(removal) + "\n")
                                                results.close() 
                                                continue
                                            prev_deassert = deassert

                                            min = vdd
                                            removal = 0
                                            prev_removal = removal
                                            dt = 0.00001

                                            while float(min) > 0.9*vdd:
                                                    
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VS S 0 pwl ( 0 0 0.1n 0 {0}u 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VS S 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str

                                                prev_deassert = deassert 
                                                deassert -= dt

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)

                                                f.close()
                                                results = open("results.txt", "w")

                                                cmd = "ngspice cell.spice -b"
                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    print("error")

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                min = regex.search(filedata) 
                                                min = ((min.group()).split())[2]

                                                regex = re.compile(r'(removal.*=.*[0-9e-].*)')
                                                prev_removal = float(removal)

                                                removal = regex.search(filedata)
                                                removal = ((removal.group()).split())[2]
                                                print(min)
                                                print(removal)
                                                print(deassert)
                                                removal = float(removal)   
                                                if removal < 0:
                                                    removal = 0.0
                                                    break         
                                        elif pin == "R":
                                            max = 0
                                            prev_deassert = deassert 
                                            removal = 0
                                            prev_removal = removal

                                            dt = 0.01

                                            while True:
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VR R 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VR R 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str 

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)
                                                f.close()

                                                results = open("results.txt", "w")

                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    continue

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                max = regex.search(filedata) 
                                                max = ((max.group()).split())[2]

                                                if float(max) > 0.1*vdd:
                                                    deassert += dt
                                                else:
                                                    break  

                                                if deassert >= 1:
                                                    break

                                            if deassert >= 1:
                                                removal = 0.0
                                                results = open(results_name, "a+")
                                                results.write(str(removal) + "\n")
                                                results.close() 
                                                continue
                                            prev_deassert = deassert

                                            max = 0
                                            removal = 0
                                            prev_removal = removal
                                            dt = 0.00001

                                            while float(max) < 0.1*vdd:
                                                    
                                                f = open("inputs.spice", "r")
                                                filedata = f.read()

                                                new_str = ".param deassert={0}us\n".format(deassert)

                                                if measurement == "fall_constraint":
                                                    new_str += "VR R 0 pwl ( 0 0 0.1n 0 {0}n 2.5V {1}n 2.5V {2}n 0)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))
                                                elif measurement == "rise_constraint":
                                                    new_str += "VR R 0 pwl ( 0 2.5V 0.1n 2.5V {0}n 0 {1}n 0 {2}n 2.5V)\n".format(str(0.1+constrained_pin_transition), str(deassert*1000.0), str(deassert*1000.0+constrained_pin_transition))

                                                newdata = filedata.replace(deassert_str, new_str)
                                                deassert_str = new_str

                                                prev_deassert = deassert 
                                                deassert -= dt

                                                f = open("inputs.spice", "w")
                                                f.write(newdata)

                                                f.close()
                                                results = open("results.txt", "w")

                                                cmd = "ngspice cell.spice -b"
                                                try:
                                                    process = subprocess.run(cmd.split(), stdout = results, check=True)
                                                except subprocess.CalledProcessError:
                                                    print("error")

                                                results.close()
                                                results = open("results.txt", "r")
                                                filedata = results.read()

                                                regex = re.compile(r'(value.*=.*[0-9e-].*)')  
                                                max = regex.search(filedata) 
                                                max = ((max.group()).split())[2]

                                                regex = re.compile(r'(removal.*=.*[0-9e-].*)')
                                                prev_removal = float(removal)

                                                removal= regex.search(filedata)
                                                removal = ((removal.group()).split())[2]
                                                
                                                removal = float(removal)   
                                                if removal < 0:
                                                    removal = 0.0
                                                    break              
                                                if deassert <= 0.5:
                                                    removal = 0.0
                                                    break

                                        results = open(results_name, "a+")
                                        results.write(str(1.3*removal) + "\n")
                                        results.close() 
            
    Timing_template_6_7 = {"total_output_net_capacitance" : [0.0017, 0.0062, 0.0232, 0.0865, 0.3221, 1.2], 
                        "input_net_transition" : [0.0042, 0.0307, 0.0768, 0.192, 0.48, 1.2, 3]}

    Constraint_5_5 = {"related_pin_transition": [0.0042, 0.0307, 0.0768, 0.48, 3], 
                        "constrained_pin_transition": [0.0042, 0.0307, 0.0768, 0.48, 3]}

    Timing_template_6_7_index_1 = "index_1 (\""

    for total_output_net_capacitance in Timing_template_6_7["total_output_net_capacitance"]:
        Timing_template_6_7_index_1 += "{0}, ".format(total_output_net_capacitance)

    Timing_template_6_7_index_1 = Timing_template_6_7_index_1[:-2] 
    Timing_template_6_7_index_1 += "\");"

    Timing_template_6_7_index_2 = "index_2 (\""

    for input_net_transition in Timing_template_6_7["input_net_transition"]:
        Timing_template_6_7_index_2 += "{0}, ".format(input_net_transition)

    Timing_template_6_7_index_2 = Timing_template_6_7_index_2[:-2] 
    Timing_template_6_7_index_2 += "\");"

    Constraint_5_5_index_1 = "index_1 (\""

    for related_pin_transition in Constraint_5_5["related_pin_transition"]:
        Constraint_5_5_index_1 += "{0}, ".format(related_pin_transition)

    Constraint_5_5_index_1 = Constraint_5_5_index_1[:-2] 
    Constraint_5_5_index_1 += "\");"

    Constraint_5_5_index_2 = "index_2 (\""

    for constrained_pin_transition in Constraint_5_5["constrained_pin_transition"]:
        Constraint_5_5_index_2 += "{0}, ".format(constrained_pin_transition)

    Constraint_5_5_index_2 = Constraint_5_5_index_2[:-2] 
    Constraint_5_5_index_2 += "\");"

    shutil.copyfile(lib_template, output_lib)

    string = ""
    for cell in cells:
        string += "\tcell(\"{0}\")".format(cell) + " {\n"

        type = cells[cell]["type"]
        path = cells[cell]["path"]
        string += "\t\tarea : {0};\n".format(calc_area(path))

        try:
            ff = cells[cell]["ff"]
            string += "\t\tff (\"IQ\", \"IQN\") {\n"
            string += "\t\t\tnext_state : \"{0}\";\n".format(cells[cell]["ff"]["next_state"])
            string += "\t\t\tclocked_on : \"{0}\";\n".format(cells[cell]["ff"]["clocked_on"])

            try: 
                preset = cells[cell]["ff"]["preset"]
                string += "\t\t\tpreset : \"{0}\";\n".format(cells[cell]["ff"]["preset"])
            except:
                pass

            try: 
                clear = cells[cell]["ff"]["clear"]
                string += "\t\t\tclear : \"{0}\";\n".format(cells[cell]["ff"]["clear"])
                string += "\t\t\tclear_preset_var1 : L;\n"
                string += "\t\t\tclear_preset_var2: L;\n"
            except:
                pass
            
            string += "\t\t}\n"
        except:
            pass

        for pin in cells[cell]["pins"]:
            direction = cells[cell]["pins"][pin]["direction"]
            string += "\t\tpin(\"{0}\")".format(pin) + " {\n"
            string += "\t\t\tdirection : {0};\n".format(direction)

            try:
                function = cells[cell]["pins"][pin]["function"]
                string += "\t\t\tfunction : \"{0}\";\n".format(function)
            except:
                pass 
            
            try:
                timing = cells[cell]["pins"][pin]["timings"]
            except:
                string += "\t\t}\n"
                continue

            for timing in cells[cell]["pins"][pin]["timings"]:
                related_pin = cells[cell]["pins"][pin]["timings"][timing]["related_pin"]

                try: 
                    when = cells[cell]["pins"][pin]["timings"][timing]["when"]
                except:
                    when = ""

                try:
                    timing_sense = cells[cell]["pins"][pin]["timings"][timing]["timing_sense"]
                except:
                    timing_sense = ""

                try:
                    timing_type = cells[cell]["pins"][pin]["timings"][timing]["timing_type"]
                except:
                    timing_type = ""

                

                string += "\t\t\ttiming() {\n"
                related_pin = cells[cell]["pins"][pin]["timings"][timing]["related_pin"]
                string += "\t\t\t\trelated_pin : \"{0}\";\n".format(related_pin)
        
                try: 
                    when = cells[cell]["pins"][pin]["timings"][timing]["when"]
                    string += "\t\t\t\twhen : \"{0}\";\n".format(when)
                except:
                    when = ""
                
                try:
                    timing_sense = cells[cell]["pins"][pin]["timings"][timing]["timing_sense"]
                    string += "\t\t\t\ttiming_sense : \"{0}\";\n".format(timing_sense)
                except:
                    timing_sense = ""

                try:
                    timing_type = cells[cell]["pins"][pin]["timings"][timing]["timing_type"]
                    string += "\t\t\t\ttiming_type : \"{0}\";\n".format(timing_type)
                except:
                    timing_type = ""

                for measurement in cells[cell]["pins"][pin]["timings"][timing]["measurements"]:
                    if timing_sense == "":
                        if when == "":
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_type + "_" + measurement + ".mt")
                        else:
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_type + "_" + measurement + "_" + when + ".mt")
                    else:
                        if when == "":
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + ".mt")
                        else:
                            results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + "_" + when + ".mt")

                    if measurement == "cell_fall" or measurement == "cell_rise" or measurement == "rise_transition" or measurement == "fall_transition":
                        string+= "\t\t\t\t{0}(Timing_template_6_7) ".format(measurement) + "{\n"
                        string += "\t\t\t\t\t" + Timing_template_6_7_index_1 + "\n"
                        string += "\t\t\t\t\t" + Timing_template_6_7_index_2 + "\n"
                        template = Timing_template_6_7
                    else:
                        string+= "\t\t\t\t{0}(Constraint_5_5) ".format(measurement) + "{\n"
                        string += "\t\t\t\t\t" + Constraint_5_5_index_1 + "\n"
                        string += "\t\t\t\t\t" + Constraint_5_5_index_2 + "\n"
                        template = Constraint_5_5                        
                        
                    if timing_sense == "":
                        timing_sense = timing_type

                    if when == "":
                        results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + ".mt")
                    else: 
                        results_name = str(cell + "_" + pin + "_" + related_pin + "_" + timing_sense + "_" + measurement + "_" + when + ".mt")

                    
                    try:
                        results = open(results_name, "r")
                        results = results.read()
                        results = results.split()

                        string += "\t\t\t\t\t\tvalues ("
                        index = 0

                        if template == Timing_template_6_7:
                            for total_output_net_capacitance in Timing_template_6_7["total_output_net_capacitance"]:
                                string += "\""
                                for input_net_transition in Timing_template_6_7["input_net_transition"]:
                                    string += "{0}, ".format(10e9*float(results[index]))
                                    index += 1
                                string = string[:-2]
                                string += "\", "
                                string += "\\" + "\n\t\t\t\t\t\t  "
                            string = string[:-12]
                            string += ");\n"
                        else:
                            for related_pin_transition in Constraint_5_5["related_pin_transition"]:
                                string += "\""
                                for constrained_pin_transition in Constraint_5_5["constrained_pin_transition"]:
                                    string += "{0}, ".format(10e9*float(results[index]))
                                    index += 1
                                string = string[:-2]
                                string += "\", "
                                string += "\\" + "\n\t\t\t\t\t\t  "
                            string = string[:-12]
                            string += ");\n"
                    except:
                        string += "\t\t\t\t}\n\n"
                        continue

                    string += "\t\t\t\t}\n\n"
                string += "\t\t\t}\n"

            string += "\t\t}\n"
        string += "\t}\n"
    string += "}"
    #print(string)
    library = open(output_lib, "a+")

    library.write(string)
else:
    for cell in cells:
        verilog_lib_name = cell + ".v"

        f = open(verilog_lib_name, "w")

        string = ""
        string += "primitive {0}_(".format(cell)
        
        type = cells[cell]["type"]
    
        inputs = []
        outputs = []
        output_functions = {}

        for pin in cells[cell]["pins"]:
            direction = cells[cell]["pins"][pin]["direction"]
            if direction == "input":
                inputs.append(pin)
            else:
                outputs.append(pin)
                function = cells[cell]["pins"][pin]["function"]
                output_functions[pin] = function
        
        for output in outputs:
            string += "{0}, ".format(output)
            if type == "combinational":
                break
        
        for input in inputs:
            string += "{0}, ".format(input)
        
        string = string[:-2]
        string += ");\n"

        for output in outputs:
            if type == "combinational":
                string += "output {0};\n".format(output)
            else:
                string += "output reg {0};\n".format(output)
                break

        for input in inputs:
            string += "input {0};\n".format(input)
        
        if type == "combinational":
            function = function.replace("!", "~")

            string += "\ttable\n"
            for A in range(len(inputs)):
                for B in range(len(inputs)):
                    out = bin(eval(function))[-1]
                    string += "\t\t{0}\t{1}\t:\t{2};\n".format(A, B, out)
            string += "\tendtable\n"
            string += "endprimitive\n\n"
        elif cell == "DFF":
            string += "\ttable\n"
            next_state  = cells[cell]["ff"]["next_state"]
            clocked_on = cells[cell]["ff"]["clocked_on"]

            if clocked_on == "CLK":
                clocks = ["01", "0?"]
                ignores = {"edge":"?0", "no_change":"?"}
            else:
                clocks = {"10", "1?"}
                ignores = {"edge":"?1", "no_change":"?"}

            for clock in clocks:
                for d in range(2):
                    q = d if (output_functions["Q"] == "IQ") else bin(eval("~d"))[-1]

                    if clock.__contains__("?"):
                        string += "\t\t({0})\t{1}\t:\t{2}\t:\t{3};\n".format(clock, d, d, q)
                    else:
                        string += "\t\t({0})\t{1}\t:\t{2}\t:\t{3};\n".format(clock, d, "?", q)
                    
            for clock in ignores:
                if clock == "edge":
                    string += "\t\t({0})\t?\t:\t?\t:\t-;\n".format(ignores[clock])
                else:
                    string += "\t\t{0}\t(??)\t:\t?\t:\t-;\n".format(ignores[clock])
            
            string += "\tendtable\n"
            string += "endprimitive\n\n"
        else:
            string += "\ttable\n"
            next_state  = cells[cell]["ff"]["next_state"]
            clocked_on = cells[cell]["ff"]["clocked_on"]
            clear = cells[cell]["ff"]["clear"]
            preset = cells[cell]["ff"]["preset"]

            if clear.__contains__("!"):
                clear = 0
            else:
                clear = 1
            
            if preset.__contains__("!"):
                preset = 0
            else:
                preset = 1

            if clocked_on == "CLK":
                clocks = ["01", "0?"]
                ignores = {"edge":"?0", "no_change":"?"}
            else:
                clocks = {"10", "1?"}
                ignores = {"edge":"?1", "no_change":"?"}

            for clock in clocks:
                for d in range(2):
                    q = d if (output_functions["Q"] == "IQ") else bin(eval("~d"))[-1]
                    if clock.__contains__("?"):
                        string += "\t\t({0})\t{1}\t{4}\t{5}\t:\t{2}\t:\t{3};\n".format(clock, d, q, q, bin(eval("~preset"))[-1], bin(eval("~clear"))[-1])
                    else:
                        string += "\t\t({0})\t{1}\t{4}\t{5}\t:\t{2}\t:\t{3};\n".format(clock, d, "?", q, bin(eval("~preset"))[-1], bin(eval("~clear"))[-1])
            
            for clock in ignores:
                if clock == "edge":
                    string += "\t\t({0})\t?\t{1}\t{2}\t:\t?\t:\t-;\n".format(ignores[clock], bin(eval("~preset"))[-1], bin(eval("~clear"))[-1])
                else:
                    string += "\t\t{0}\t(??)\t{1}\t{2}\t:\t?\t:\t-;\n".format(ignores[clock], bin(eval("~preset"))[-1], bin(eval("~clear"))[-1])

            string += "\t\t?\t?\t{0}\t{1}\t:\t?\t:\t1;\n".format(preset, bin(eval("~clear"))[-1])
            string += "\t\t?\t?\t{0}\t{1}\t:\t?\t:\t0;\n".format(bin(eval("~preset"))[-1], clear)
            
            string += "\tendtable\n"
            string += "endprimitive\n\n"

    
        string += "module {0}(".format(cell)
        
        for output in outputs:
            string += "{0}, ".format(output)
        
        for input in inputs:
            string += "{0}, ".format(input)
        
        string = string[:-2]
        string += ");\n"

        for output in outputs:
            string += "output {0};\n".format(output)

        for input in inputs:
            string += "input {0};\n".format(input)
    
        string += "\n{0}_ {0}(".format(cell)
        
        for output in outputs:
            string += output + ", "
        
        for input in inputs:
            string += input + ", "
        string = string[:-2]
        string += ");\n"

        if type == "sequential":
            string += "not not_(Qbar, Q);\n"
        
        string += "specify\n"
        for input in inputs:
            for output in outputs:
                string += "\t({0} => {1}) = (1.0, 1.0);\n".format(input, output)

        string += "endspecify\n"
        string += "endmodule\n"
        f.write(string)



end_time = time.time()

print("\n\n\nTotal Execution Time: {0}s".format(str(end_time - start_time)))
