#!/usr/bin/env python3

import matplotlib.pyplot as plt
import sys
import csv

if len(sys.argv) < 2:
    print("Usage: ", sys.argv[0], "xyce_output")
    sys.exit(1)

hide = len(sys.argv) > 2

fname = sys.argv[1]

f = open(fname, 'r')
index = f.readline()

# Read index line
labels = index.split(",")
num_vals = len(labels)

# Read simulation data
dat = [ [] for _ in range(num_vals) ]
reader = csv.reader(f)
for row in reader:
    for i,v in enumerate(row):
        dat[i].append(float(v))

# Plot
fig, ax = plt.subplots()
graphs = []
graphsd = {}

for i in range(1, num_vals):
    graphs.append(ax.plot(dat[0], dat[i], label = labels[i]))

# Make interactive
legend = ax.legend(loc = "upper right")
llines = legend.get_lines()
for i in range(len(llines)):
    llines[i].set_picker(True)
    llines[i].set_pickradius(8)
    graphsd[llines[i]] = graphs[i]
    if hide:
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
