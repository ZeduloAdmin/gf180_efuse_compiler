#!/usr/bin/env python3

from klayout import db
import sys
import json
from pathlib import Path
from os import PathLike

from .gf180_klayout import *
from .cells.draw_mos import draw_nmos, draw_pmos
from .cells.mos import mos_ld, mos_grw

# Design constants, sizes are in nm
NFUSES_PER_BLOCK    = 16
EFUSE_XSTEP         = 1920
EFUSE_YOFF          = 590

NMOS_WDT            = 30500
NMOS_LEN            = 600
NMOS_XOFF           = -400
NMOS_YOFF           = 6340
NMOS_YOFFN          = -2225
NMOS_YSTEP          = 1840
NMOS_YSTEP_TAP      = 805
NMOS_NPLUS_PATCH    = 45
NMOS_M1_WDT         = 380
NMOS_M1_STEP        = 1010

PMOS_WDT            = 38250
PMOS_LEN            = 500
PMOS_FINGERS        = 4
PMOS_XOFF           = 970
PMOS_YOFF           = -16700
PMOS_M1_STEP        = 1020
PMOS_VDD_WDT        = 4250

BLOCK_XOFF          = -290
BLOCK_DG_PATCH      = 500

SENSAMP_XOFF        = -1060
SENSAMP_YOFF        = -7755
SENSE_BIT_OVERLAP   = 1350

BITWIRE_UP_YOFF     = 3785
BITWIRE_DOWN_YOFF   = 1525
BITWIRE_WDT         = 810

BITLINE_YOFF        = -745

BITSEL_XOFF         = -2155
BITSEL_STEP         = -(M2_MIN_WDT + VIA_DIST)

BLOCK_VSS_WDT       = 2860
BLOCK_VSS_OFF       = 230
CS_WIRE_MAX_OFF     = BLOCK_VSS_OFF - M2_DIST + M2_MIN_WDT - 50
SENSE_POWER_WDT     = 1000

CELL_RAIL_WDT       = 600

GATE_EXTEND         = 320

class ProgPmos(CellGf180mcu):
    """
    eFuse bitline programming PMOS transistor cell.
    """
    def __init__(self, layout):
        pmos_cell = draw_pmos(layout.layout, PMOS_LEN/1000, PMOS_WDT/1000, mos_ld, PMOS_FINGERS, mos_grw, "Bulk Tie", "5V", 0, 0)
        super().__init__(layout, pmos_cell)
        self.zero_origin()
        
        GATE_STEP = layout.to_dbu(1.020)
        pmos_m1_bbox = pmos_cell.bbox(self.l.metal1)
        pmos_poly_bbox = pmos_cell.bbox(self.l.poly2)
        
        for i in range(PMOS_FINGERS):
            self.create_box(self.l.poly2, pmos_poly_bbox.p1.x + i*GATE_STEP, pmos_poly_bbox.p1.y - GATE_EXTEND, pmos_poly_bbox.p1.x + PMOS_LEN + i*GATE_STEP, pmos_poly_bbox.p1.y)
        pmos_poly_bbox = pmos_cell.bbox(self.l.poly2)
            
        m1 = self.create_box(self.l.metal1, pmos_poly_bbox.p1.x, pmos_poly_bbox.p1.y, pmos_poly_bbox.p2.x, pmos_m1_bbox.p1.y - M1_DIST) 
        self.create_box(self.l.dualgate, pmos_poly_bbox.p1.x - DG_POLY_ENC - 280, pmos_poly_bbox.p1.y - DG_POLY_ENC, pmos_poly_bbox.p2.x + DG_POLY_ENC, pmos_poly_bbox.p1.y) 
        for i in range(PMOS_FINGERS):
            self.place_contact(m1.p1.x + CONTACT_POLY_OVERLAP + i*GATE_STEP, m1.p1.y + CONTACT_POLY_OVERLAP)
        self.create_text(self.l.metal1_label, m1.p2.x, m1.center().y, "COL_PROG_N")

class BitNmos(CellGf180mcu):
    """
    eFuse bits select NMOS transistor cell.
    """
    def __init__(self, l : LayoutGf180mcu, tie : bool):
        if tie:
            tie_str = "Bulk Tie"
        else:
            tie_str = "None"
            
        nmos_cell = draw_nmos(l.layout, NMOS_LEN/1000, NMOS_WDT/1000, mos_ld, 1, mos_grw, tie_str, "5V", 0, 0)
        super().__init__(l, nmos_cell)
        self.zero_origin()
        
        poly_bbox = self.bbox(l.poly2)
        
        # extend poly on gate, add M1 & create contacts
        p = self.create_box(l.poly2, poly_bbox.p1.x, poly_bbox.p1.y - GATE_EXTEND, poly_bbox.p2.x, poly_bbox.p1.y)
        self.place_contact(p.p1.x + CONTACT_POLY_OVERLAP, p.p1.y + CONTACT_POLY_OVERLAP)
        p = self.create_box(l.poly2, poly_bbox.p1.x, poly_bbox.p2.y, poly_bbox.p2.x, poly_bbox.p2.y + GATE_EXTEND)
        self.place_contact(p.p1.x + CONTACT_POLY_OVERLAP, p.p2.y - CONTACT_POLY_OVERLAP - CONTACT_SIZE)
        self.create_box(l.metal1, poly_bbox.center().x - M1_MIN_WDT//2, poly_bbox.p1.y - GATE_EXTEND, poly_bbox.center().x + M1_MIN_WDT//2, poly_bbox.p2.y + GATE_EXTEND)
        
        self.create_box(l.metal1, poly_bbox.p1.x, poly_bbox.p1.y - GATE_EXTEND*2, poly_bbox.p2.x, poly_bbox.p1.y - 20)
        self.create_box(l.metal1, poly_bbox.p1.x, poly_bbox.p2.y + 20, poly_bbox.p2.x, poly_bbox.p2.y + GATE_EXTEND*2)
        
        self.zero_origin()

class Efuse(CellGf180mcu):
    """
    Single eFuse cell.
    """
    def __init__(self, l : LayoutGf180mcu):
        super().__init__(l, parent = str(Path(__file__).parent / "cells/efuse_compact.gds"), name = "efuse_cell")
        self.zero_origin()

class EfuseSenseamp(CellGf180mcu):
    """
    eFuse bitline senseamp cell.
    """
    def __init__(self, l : LayoutGf180mcu):
        super().__init__(l, parent = str(Path(__file__).parent / "cells/efuse_senseamp.gds"), name = "efuse_senseamp")
        self.flatten()
        self.zero_origin()
        
class BitlineBlock(CellGf180mcu):
    """
    16 fuse basic eFuse bitline building block cell.
    """
    def __init__(self, l : LayoutGf180mcu, num_offset : int = 0):
        # create cell
        super().__init__(l, name = "efuse_bitline_block_"+str(num_offset))

        M1_M2_OVERLAP = l.to_dbu(1.1)
        TAP_STEP = 6    # each Nth nmos is with bulk tap
        
        # create fuses with bit select transistors
        efuse_cell = Efuse(l)
        nmos_cell = BitNmos(l, False)
        nmos_cell_tie = BitNmos(l, True)
        bitsel_boxes = []
        for i in range(NFUSES_PER_BLOCK):
            odd = i % 2 # even transistors go up, odd go down
            # create fuse with vias on anode
            fuse = self.cell_inst(efuse_cell, i*EFUSE_XSTEP, EFUSE_YOFF * odd, 1 + 2*odd)
            fuse_bbox = fuse.bbox()
            fuse_m1_bbox = fuse.bbox(l.metal1)
            anode = efuse_cell.find_boxes_with_text(l.metal1, l.metal1_label, "ANODE")
            assert(len(anode) == 1)
            self.place_via_area(anode[0].transformed(fuse.trans), 1, 2) 
            
            # create NMOS transistors
            if odd:
                y = NMOS_YOFFN-NMOS_YSTEP*(i//2)-NMOS_YSTEP_TAP*((i+1)//TAP_STEP)
            else:
                y = NMOS_YOFF+NMOS_YSTEP*(i//2)+NMOS_YSTEP_TAP*(i//TAP_STEP)
            if (i%TAP_STEP == TAP_STEP-2+odd):
                nmos = self.cell_inst(nmos_cell_tie, NMOS_XOFF, y, 3-2*odd)
            else:
                nmos = self.cell_inst(nmos_cell, NMOS_XOFF, y, 3-2*odd)
            nmos_m1_bbox = nmos.bbox(l.metal1)
            nmos_poly_bbox = nmos.bbox(l.poly2)
            nmos_dg_bbox = nmos.bbox(l.dualgate)
            if (i%TAP_STEP != TAP_STEP-2):
                # patch nplus gaps
                nplus_bbox = nmos.bbox(l.nplus)
                if odd:
                    y = nplus_bbox.p1.y
                    y2 = nplus_bbox.p1.y-NMOS_NPLUS_PATCH
                else:
                    y = nplus_bbox.p2.y
                    y2 = nplus_bbox.p2.y+NMOS_NPLUS_PATCH
                self.create_box(l.nplus, nplus_bbox.p1.x, y, nplus_bbox.p2.x, y2)
            # patch dualgate gaps
            self.create_box(l.dualgate, nmos_dg_bbox.p1.x - BLOCK_DG_PATCH, nmos_dg_bbox.p1.y, nmos_dg_bbox.p1.x, nmos_dg_bbox.p2.y)
            self.create_box(l.dualgate, nmos_dg_bbox.p2.x, nmos_dg_bbox.p1.y, nmos_dg_bbox.p2.x + BLOCK_DG_PATCH, nmos_dg_bbox.p2.y)
            
            # mark bit select gates & connect to M3
            x = nmos_m1_bbox.p2.x - VIA_STEP//2
            y = nmos_poly_bbox.center().y
            self.place_via_tower(db.Point(x, y), 1, 3, True)
            x2 = x + i * BITSEL_STEP
            if x != x2:
                wdt = M2_MIN_WDT // 2
                if i == 1:
                    wdt += 50 # to avoid min dist error
                self.create_box(l.metal3, x, y - wdt, x2, y + wdt)
            bitsel_boxes.append(self.place_via_tower(db.Point(x2 + M2_MIN_WDT // 2, y), 3, 4, True))
            
            # create fuse cathode - nmos connection
            if i < 2:
                # connect first fuse directly with M1
                if odd:
                    y = fuse_m1_bbox.p1.y
                    y2 = nmos_m1_bbox.p2.y
                    ly = y2 - NMOS_M1_STEP - NMOS_M1_WDT
                else:
                    y = fuse_m1_bbox.p2.y
                    y2 = nmos_m1_bbox.p1.y
                    ly = y2 + NMOS_M1_STEP + NMOS_M1_WDT
                m1_box = self.create_box(l.metal1, fuse_m1_bbox.p1.x, y, fuse_m1_bbox.p2.x, y2)
                self.create_text(l.metal1_label, nmos_m1_bbox.center().x, ly, "VSS")
            else:
                # connect the rest via M2
                if odd:
                    y = fuse_m1_bbox.p1.y
                    y2 = fuse_bbox.p1.y - M1_M2_OVERLAP//2
                    m2y = fuse_bbox.p1.y + M1_M2_OVERLAP//2
                    m2y2 = nmos_m1_bbox.p2.y - NMOS_M1_WDT
                else:
                    y = fuse_m1_bbox.p2.y
                    y2 = fuse_bbox.p2.y + M1_M2_OVERLAP//2
                    m2y = fuse_bbox.p2.y - M1_M2_OVERLAP//2
                    m2y2 = nmos_m1_bbox.p1.y + NMOS_M1_WDT
                m1_box = self.create_box(l.metal1, fuse_m1_bbox.p1.x, y, fuse_m1_bbox.p2.x, y2)
                m2_box = self.create_box(l.metal2, fuse_m1_bbox.p1.x, m2y, fuse_m1_bbox.p2.x, m2y2)
                # create fuse_M1 - M2 vias
                if odd:
                    y = fuse_bbox.p1.y - M1_M2_OVERLAP//2 + VIA_SIZE/2
                    my = m2_box.p1.y - NMOS_M1_STEP
                else:
                    y = fuse_bbox.p2.y - M1_M2_OVERLAP//2 + VIA_SIZE/2
                    my = m2_box.p2.y + NMOS_M1_STEP
                self.place_via_area(m1_box & m2_box, 1, 2)
                # create M2 - nmos_drain_M1 vias
                self.place_via_area(m2_box & nmos_m1_bbox, 1, 2)
                # mark nmos VSS
                self.create_text(l.metal1_label, nmos_m1_bbox.center().x, my, "VSS")
                if i%TAP_STEP == TAP_STEP-2+odd:
                    if odd:
                        off = -l.to_dbu(0.700)
                    else:
                        off = l.to_dbu(0.700)
                    self.create_text(l.metal1_label, nmos_m1_bbox.center().x, my+off, "VSS")
                
        # draw bit select vertical wires
        bbox = self.bbox()
        for i in range(NFUSES_PER_BLOCK):
            m4 = self.create_box(l.metal4, bitsel_boxes[i].p2.x - M2_MIN_WDT - METALVIA_OVERLAP, bbox.p1.y, bitsel_boxes[i].p2.x - METALVIA_OVERLAP, bbox.p2.y)
            self.create_text_p(l.metal4_label, m4.center(), "BIT_SEL[" + str(num_offset+i)+"]")

# Efuse bitline    
class EfuseBitline(CellGf180mcu):
    """
    eFuse bitline cell.
    """
    def __init__(self, l : LayoutGf180mcu, fuses : int = 16):
        # create cell
        super().__init__(l, name = "efuse_bitline")
        
        assert((fuses % NFUSES_PER_BLOCK) == 0 and fuses >= NFUSES_PER_BLOCK and fuses <= NFUSES_PER_BLOCK*4)
        
        # create basic 16 fuse blocks (up to 4)
        blocks = fuses // NFUSES_PER_BLOCK
        block_cells = []
        for b in range(blocks):
            block_cell = BitlineBlock(l, b * NFUSES_PER_BLOCK)
            block = self.cell_inst(block_cell, b * (block_cell.bbox(l.dualgate).width() + BLOCK_XOFF), 0, 0)
            block_cells.append(block)
                
        # create programming PMOS
        pmos_cell = ProgPmos(l)
        pmos = self.cell_inst(pmos_cell, block.bbox(l.nplus).p2.x + PMOS_XOFF, block.bbox(l.nplus).center().y - self.bbox().height()//2, 2)
        pmos_bbox = pmos.bbox()
        pmos_m1_bbox = pmos.bbox(l.metal1)
        pmos_dg_bbox = pmos.bbox(l.dualgate)
        for i in range(PMOS_FINGERS//2):
            self.create_text(l.metal1_label, pmos_bbox.p1.x + l.to_dbu(1.77) + PMOS_M1_STEP*i*2, pmos_m1_bbox.center().y, "VDD")
        self.create_text(l.metal1_label, pmos_bbox.p1.x + l.to_dbu(1.57) + PMOS_M1_STEP*PMOS_FINGERS//2*2, pmos_m1_bbox.center().y, "VDD")
        # patch dualgate
        block_dg_bbox = block.bbox(l.dualgate)
        self.create_box(l.dualgate, block_dg_bbox.p2.x, block_dg_bbox.p1.y, pmos_dg_bbox.p1.x, block_dg_bbox.p2.y)
        
        # create sensamp in stdcell line
        sensamp_cell = EfuseSenseamp(l)
        sensamp = self.cell_inst(sensamp_cell, self.bbox(l.metal1).p1.x + SENSAMP_XOFF - sensamp_cell.bbox().height(), SENSAMP_YOFF, 3)
        sensamp_bbox = sensamp.bbox()
        
        # create two metal bit wires connecting all fuses, sensamp & programming pmos
        bitwire_m2_up   = self.create_box(l.metal2, sensamp_bbox.p2.x - SENSE_BIT_OVERLAP, BITWIRE_UP_YOFF, pmos_bbox.p2.x, BITWIRE_UP_YOFF + BITWIRE_WDT)
        bitwire_m2_down = self.create_box(l.metal2, sensamp_bbox.p2.x - SENSE_BIT_OVERLAP, BITWIRE_DOWN_YOFF, pmos_bbox.p2.x, BITWIRE_DOWN_YOFF + BITWIRE_WDT)
        bitwire_m2_sense = self.create_box(l.metal2, bitwire_m2_up.p1.x, bitwire_m2_down.p1.y, bitwire_m2_up.p1.x + bitwire_m2_up.height(), bitwire_m2_up.p2.y)
        
        # generate vias on bitwires
        sense_bitwire_m1 = self.find_boxes_with_text(l.metal1, l.metal1_label, "BITWIRE")[0]
        self.place_via_area(bitwire_m2_sense & sense_bitwire_m1, 1, 2)
        for i in range(PMOS_FINGERS//2 + 1):
            self.place_via_tower(db.Point(pmos_m1_bbox.p1.x + NMOS_M1_WDT // 2 + PMOS_M1_STEP*i*2, bitwire_m2_up.p1.y), 1, 2, True) 
            self.place_via_tower(db.Point(pmos_m1_bbox.p1.x + NMOS_M1_WDT // 2 + PMOS_M1_STEP*i*2, bitwire_m2_down.p2.y), 1, 2, True)
            
        # draw PRESET & SENSE connection wires
        bbox = self.bbox()
        presets = self.find_boxes_with_text(l.metal2, l.metal2_label, "PRESET_N")
        assert(len(presets) == 1)
        self.create_box(l.metal2, presets[0].p1.x, bbox.p1.y, presets[0].p1.x + M2_MIN_WDT, bbox.p2.y)
        senses = self.find_boxes_with_text(l.metal2, l.metal2_label, "SENSE")
        assert(len(senses) == 1)
        self.create_box(l.metal2, senses[0].p1.x, bbox.p1.y, senses[0].p1.x + M2_MIN_WDT, bbox.p2.y)
        
        # draw power rails for standard cells (senseamp)
        x = sensamp.bbox(l.metal1).p2.x - CELL_RAIL_WDT
        self.create_box(l.metal1, x, bbox.p1.y, x + CELL_RAIL_WDT, bbox.p2.y)
        x = sensamp.bbox(l.metal1).p1.x
        self.create_box(l.metal1, x, bbox.p1.y, x + CELL_RAIL_WDT, bbox.p2.y)
            
        # draw VSS stripes on M4
        self.vss_m1 = self.find_boxes_with_text(l.metal1, l.metal1_label, "VSS")
        vss_m4 = []
        for block in block_cells:
            x = block.bbox(l.nplus).p1.x + BLOCK_VSS_OFF
            vss = self.create_box(l.metal4, x, bbox.p1.y, x + BLOCK_VSS_WDT, bbox.p2.y)
            vss_m4.append(vss)
            self.create_text_p(l.metal4_label, vss.center(), "VSS")
            
        for m4 in vss_m4:
            for m1 in self.vss_m1:
                self.place_via_area(m1 & m4, 1, 4)
                
        x = sensamp.bbox(l.metal1).p2.x + METALVIA_OVERLAP
        self.vss_sense = self.create_box(l.metal4, x - SENSE_POWER_WDT, bbox.p1.y, x, bbox.p2.y)
        self.create_text_p(l.metal4_label, self.vss_sense.center(), "VSS")
        self.pvia_inhibit = [bitwire_m2_up, bitwire_m2_down, bitwire_m2_sense]

        # draw VDD stripes on M4
        self.vdd_m4 = []
        self.vdd_m1 = self.find_boxes_with_text(l.metal1, l.metal1_label, "VDD")
        vdd_create_list = ((sensamp.bbox(l.metal1).p1.x - METALVIA_OVERLAP, SENSE_POWER_WDT), (pmos.bbox(l.metal1).p2.x - PMOS_VDD_WDT, PMOS_VDD_WDT))
        for x,w in vdd_create_list:
            vdd = self.create_box(l.metal4, x, bbox.p1.y, x + w, bbox.p2.y)
            self.create_text_p(l.metal4_label, vdd.center(), "VDD")
            self.vdd_m4.append(vdd)

class EfuseArray(CellGf180mcu):
    """
    Parametrizable eFuse array cell.
    """
    def __init__(self, l : LayoutGf180mcu, name : str = "efuse_array", nwords : int = 32, word_width : int = 2, nfuses : int = 32, buf_col_sel : bool = False):
        super().__init__(l, name = name)
        layout = l.layout
        assert(nfuses == nwords) # the only supported mode for now  
        
        # generate bitlines
        endcap_cell = Endcap(l)
        fillcap_cell = FillCap(l)
        filltie_cell = FillTie(l)
        if buf_col_sel:
            inv_cell = Inv1(l)
        self.add_cells = {}

        site_size = endcap_cell.wdt
        tap_dist = MAX_TAP_DIST - fillcap_cell.wdt - site_size # fillcap is the largest and senseamp has ties inside
        cap_dist = 10000 # arbitrary
        col_sel_invs = 0
        req_buffers = nwords if buf_col_sel else 0

        bitline_cell = EfuseBitline(l, nfuses)

        for i in range(word_width):
            bitline = self.cell_inst(bitline_cell, 0, i * (bitline_cell.bbox().height() + BITLINE_YOFF), 0)
            pr_bbox = bitline.bbox(l.pr_bndry)
            sense_y0 = pr_bbox.p1.y
            sense_ye = pr_bbox.p2.y
            cs_wire = 0
            MAX_CS_WIRES_PER_LINE = 6
            inhibit = []

            # fill stdcell line with buffering invertors, ties and caps
            rail_x = self.bbox(l.metal1).p1.x - 130
            rail_y = rail_y0 = last_tap = last_cap = bitline_cell.bbox(l.metal1).transformed(bitline.trans).p1.y
            rail_ye = self.bbox(l.metal1).p2.y
            
            while (rail_y + site_size < rail_ye):
                if (rail_y+site_size > sense_y0) and (rail_y < sense_ye):
                    rail_y = sense_ye - 430

                if (rail_y < sense_y0):
                    free = sense_y0 - rail_y
                else:
                    free = rail_ye - rail_y

                # select cell to put
                if (rail_y == rail_y0) or (rail_y + 2*site_size > rail_ye):
                    cell = endcap_cell
                elif (rail_y - last_tap > tap_dist) or (free < fillcap_cell.wdt):
                    cell = filltie_cell
                    last_tap = rail_y
                elif (col_sel_invs < req_buffers) and (cs_wire < MAX_CS_WIRES_PER_LINE) and (rail_y - last_cap < cap_dist):
                    cell = inv_cell
                    
                    # add inv buf to bit_sel line connection
                    inv_out = inv_cell.find_boxes_with_text(l.metal1, l.metal1_label, "ZN")
                    bit_sel = self.find_boxes_with_text(l.metal4, l.metal4_label, f"BIT_SEL[{col_sel_invs}]")
                    assert((len(inv_out) == 1) and (len(bit_sel) > 0))
                    bit_sel_m = db.Box()
                    for b in bit_sel:
                        bit_sel_m = bit_sel_m + b
                    inv_out_bb = inv_out[0].transformed(cell.trans_llc(rail_x, rail_y, 1)).bbox()

                    central_area = bitline_cell.bbox(l.efuse_mk).transformed(bitline.trans)
                    
                    wdt = M2_MIN_WDT
                    step = wdt + M2_DIST
                    step2 = step + 2*METALVIA_OVERLAP
                    upper = (central_area.p1.y < rail_y)
                    if upper:
                        off = CS_WIRE_MAX_OFF - step*5 + step*cs_wire
                    else:
                        off = CS_WIRE_MAX_OFF - step*cs_wire
                    via = self.place_via_tower(inv_out_bb.center() + db.Point(200, 30), 1, 3, True)
                    w0 = self.create_box(l.metal3, via.p1.x, via.p1.y, central_area.p1.x + off, via.p1.y + wdt)
                    w1 = self.create_box(l.metal3, w0.p2.x - wdt, w0.p1.y, w0.p2.x, central_area.p1.y + step2*cs_wire)
                    if upper:
                        sp = w1.p1
                    else:
                        sp = w1.p2
                    w2 = self.create_box(l.metal3, sp.x, sp.y - wdt, bit_sel[0].p2.x, sp.y)
                    self.place_via_tower((w2 & bit_sel_m).center(), 3, 4, True)
                    inhibit.append(w0.enlarged(M2_DIST*2))

                    col_sel_invs += 1
                    cs_wire += 1
                else:
                    cell = fillcap_cell
                    last_cap = rail_y
                
                max_y = rail_y + cell.wdt
                
                self.cell_inst(cell, rail_x, rail_y, 1)
                if cell.name not in self.add_cells:
                    self.add_cells[cell.name] = 1
                else:
                    self.add_cells[cell.name] += 1
                rail_y = max_y

            # create power vias
            for p in bitline_cell.pvia_inhibit:
                inhibit.append(p.transformed(bitline.trans))
            for m4 in bitline_cell.vdd_m4:
                for m1 in bitline_cell.vdd_m1:
                    m1t = m1.transformed(bitline.trans)
                    m4t = m4.transformed(bitline.trans)
                    self.place_via_area_step(m1t & m4t, 1, 4, VIA_STEP, 3000, inhibit, False, True)
            vss_sense = bitline_cell.vss_sense.transformed(bitline.trans)
            for m1 in bitline_cell.vss_m1:
                m1 = m1.transformed(bitline.trans)
                self.place_via_area_step(m1 & vss_sense, 1, 4, VIA_STEP, 3000, inhibit, False)
            
            # create output access vias
            out = bitline_cell.find_boxes_with_text(l.metal1, l.metal1_label, "OUT")
            assert(len(out) == 1)
            out = self.place_via_tower(out[0].transformed(bitline.trans).center() + db.Point(100, -100), 1, 3, True)
            self.create_box_p(l.metal3, out.p1, out.p2 + db.Point(500, 500))
            self.create_text_p(l.metal3_label, out.center(), f"OUT[{i}]")


            # move labels to upper level adding postfixes
            label_layers = [l.metal1_label, l.metal2_label, l.metal3_label, l.metal4_label]
            it = db.RecursiveShapeIterator(layout, self.cell, label_layers, bitline.bbox(l.metal1_label))
            it.shape_flags = db.Shapes.STexts
            for t in it.each():
                shape = t.shape()
                s = shape.text.string
                box = t.shape().bbox().transformed(t.trans())
                labels_to_replace = ["COL_PROG_N"]
                labels_to_keep = ["BIT_SEL", "PRESET_N", "SENSE"]
                labels_to_keep_m4 = ["VSS", "VDD"]
                if s in labels_to_replace:
                    self.create_text(it.layer(), box.p1.x, box.p1.y, s+"["+str(i)+"]")
                for lab in labels_to_keep:
                    if lab == s[:len(lab)]:
                        self.create_text(it.layer(), box.p1.x, box.p1.y, s)
                if (it.layer() == l.metal4_label) and (s in labels_to_keep_m4):
                    self.create_text(it.layer(), box.p1.x, box.p1.y, s)

        if (col_sel_invs != req_buffers):
            raise RuntimeError("Failed to fit all bit select inverting buffers. Please increase word_width or disable buffering.")
        
        # remove all labels not on top
        it = db.RecursiveShapeIterator(layout, self.cell, label_layers)
        it.shape_flags = db.Shapes.STexts
        it.min_depth = 1
        for t in it.each():
            shape = t.shape()
            shape.delete()  

        # mark whole array with PR_BNDRY
        self.dup_box(l.pr_bndry, self.bbox())

        self.zero_origin()
        

def create_efuse_array(layout : PathLike | str = "efuse_array.gds", cellname : str = "efuse_array", 
    nwords : int = 32, word_width : int = 2, flat : bool = False, add_cells : PathLike | str = ""):
    """
    Create eFuse array cell with defined parameters and write it to GDS or add it to an existing layout.
    
        layout      : could be either a string/PathLike object (a name of GDS file to write) or a klayout.db.Layout object
        cellname    : name for the array cell
        nwords      : total number of words in array
        word_width  : number of bits per word
        flat        : if True the cell will be flattened
    """
    
    gdsname = ""
    if isinstance(layout, PathLike) or (type(layout) is str):
        gdsname = str(layout)
        layout = db.Layout()
    elif type(layout) is not db.Layout:
        raise TypeError("layout argument should be either a pathlike or a klayout.db.Layout object!")
    l = LayoutGf180mcu(layout)
        
    nfuses = nwords # the only supported mode for now  
    array = EfuseArray(l, cellname, nwords, word_width, nfuses)
    
    if flat:
        array.flatten()
    
    if gdsname:
        l.layout.write(gdsname)

    if add_cells:
        with open(add_cells, "w") as f:
            json.dump(array.add_cells, f)
    
# Main
if __name__ == '__main__':
    # Parse arguments
    if len(sys.argv) < 2:
        word_width = 1
        nwords = 16
    elif len(sys.argv) == 3:
        nwords = int(sys.argv[1])
        word_width = int(sys.argv[2])
    else:
        print("Usage:", sys.argv[0], "number_of_words word_width")
        sys.exit(1)
    
    name = f"efuse_array_{nwords}x{word_width}"
    create_efuse_array(name + ".gds", name, nwords, word_width)
    
