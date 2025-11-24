#!/usr/bin/env python3

import matplotlib.pyplot as plt
import csv
import argparse

parser = argparse.ArgumentParser(description = "Xyce simulation result csv file plotter")
parser.add_argument("csv_file", type = str,      help = "CSV file to plot.")
parser.add_argument("--hide", action="store_true" , help = "Start with all lines hidden.")
parser.add_argument("--skip", type=str, nargs="+", help = "Columns containing these strings will not be plotted.")
args = parser.parse_args()
if not args.skip:
    args.skip = []

f = open(args.csv_file, 'r')
index = f.readline()

# Read index line
labels = index.split(",")
num_vals = len(labels)

skip_list = []
for i,l in enumerate(labels):
    if any(s in l for s in args.skip):
        skip_list.append(i)
for i in reversed(skip_list):
    labels.pop(i)

num_vals2 = len(labels)

# Read simulation data
dat = [ [] for _ in range(num_vals) ]
reader = csv.reader(f)
for row in reader:
    for i,v in enumerate(row):
        if i not in skip_list:
            dat[i].append(float(v))

for i in reversed(skip_list):
    dat.pop(i)

# Plot
fig, ax = plt.subplots()
graphs = []
graphsd = {}

for i in range(1, num_vals2):
    graphs.append(ax.plot(dat[0], dat[i], label = labels[i]))

# Make interactive
legend = ax.legend(loc = "upper right", ncol = (len(labels) // 40 + 1))
llines = legend.get_lines()
for i in range(len(llines)):
    llines[i].set_picker(True)
    llines[i].set_pickradius(8)
    graphsd[llines[i]] = graphs[i]
    if args.hide:
        llines[i].set_visible(False)
        graphsd[llines[i]][0].set_visible(False)

def on_pick(event):
    legend = event.artist
    isVisible = legend.get_visible()
    
    graphsd[legend][0].set_visible(not isVisible)
    legend.set_visible(not isVisible)

    fig.canvas.draw()

plt.connect('pick_event', on_pick)
plt.show()
