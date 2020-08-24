import csv
import os
import math


metadata = {
    'protocolName': 'Station C abm GenomeCoV19 Detection Kit',
    'author': 'Chaz <protocols@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.4'
}


NUM_SAMPLES = 8  # start with 8 samples; max is 93
SAMPLE_VOL = 5
PREPARE_MASTERMIX = True
ADD_CONTROLS = True
TIP_TRACK = False


def run(protocol):

    source_plate = protocol.load_labware(
        'opentrons_96_aluminumblock_nest_wellplate_100ul', '1',
        'chilled elution plate on block from Station B')
    tips20 = [
        protocol.load_labware('opentrons_96_filtertiprack_20ul', slot)
        for slot in ['3', '6', '8', '9', '10', '11']
    ]
    tips300 = [protocol.load_labware('opentrons_96_filtertiprack_200ul', '2')]
    tempdeck = protocol.load_module('Temperature Module Gen2', '4')
    pcr_tubes = protocol.load_labware(
        'opentrons_96_aluminumblock_generic_pcr_strip_200ul', '7', '96 Well Al Block with MM and Controls')
    pcr_plate = tempdeck.load_labware(
        'opentrons_96_aluminumblock_nest_wellplate_100ul', 'qPCR plate')
    tempdeck.set_temperature(4)
    tube_block = protocol.load_labware(
        'opentrons_24_aluminumblock_nest_2ml_screwcap', '5',
        '2ml screw tube aluminum block for mastermix + controls')

    primers = tube_block['A6']
    mm = tube_block['B6']
    em = tube_block['C6']
    water = tube_block['D6']
    reaction_mix = tube_block['D2']
    pos_ctrl = tube_block['A1']
    neg_ctrl = tube_block['D1']
    mm_tubes = pcr_tubes['A1']
    ctrl_tubes = pcr_tubes['A12']

    num_cols = math.ceil(NUM_SAMPLES/8)
    mm_num = math.ceil((NUM_SAMPLES+3)/8) if ADD_CONTROLS else num_cols

    samples = source_plate.rows()[0][:num_cols]
    mm_cols = pcr_plate.rows()[0][:mm_num]

    # pipette
    m20 = protocol.load_instrument('p20_multi_gen2', 'right', tip_racks=tips20)
    p300 = protocol.load_instrument('p300_single_gen2', 'left', tip_racks=tips300)

    # Tip tracking between runs
    if not protocol.is_simulating():
        file_path = '/data/csv/tiptracking.csv'
        file_dir = os.path.dirname(file_path)
        # check for file directory
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)
        # check for file; if not there, create initial tip count tracking
        if not os.path.isfile(file_path):
            with open(file_path, 'w') as outfile:
                outfile.write("0, 0\n")

    tip_count_list = []
    if protocol.is_simulating() or not TIP_TRACK:
        tip_count_list = [0, 0]
    else:
        with open(file_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            tip_count_list = next(csv_reader)

    t20count = int(tip_count_list[0])
    t20max = len(tips20)*12
    t300count = int(tip_count_list[1])
    t300max = len(tips300)*96

    tip_tracker = {m20: [t20count, t20max], p300: [t300count, t300max]}

    def pick_up(pip):
        nonlocal tip_tracker
        if tip_tracker[pip][0] == tip_tracker[pip][1]:
            protocol.pause("please replace tips.")
            pip.reset_tipracks()
            tip_tracker[pip][0] = 0
        pip.pick_up_tip()
        tip_tracker[pip][0] += 1

    # prepare mastermix (optional)

    if PREPARE_MASTERMIX:
        samp_overage = mm_num*8*1.1
        primer_vol = round(2*samp_overage, 2)
        mm_vol = round(10*samp_overage, 2)
        em_vol = round(0.4*samp_overage, 2)
        water_vol = round(2.6*samp_overage, 2)

        protocol.comment('Preparing mastermix...')

        src_tubes = [water, primers, mm, em]
        vol_list = [water_vol, primer_vol, mm_vol, em_vol]
        mix_vol = 0

        for src, vol in zip(src_tubes, vol_list):
            pick_up(p300)
            p300.transfer(vol, src, reaction_mix, new_tip='never')
            mix_vol += vol
            if src != water:
                if round(mix_vol*.9) > 180:
                    m_vol = 180
                else:
                    m_vol = round(mix_vol*.9)
                p300.mix(10, m_vol, reaction_mix)
            p300.blow_out()
            p300.drop_tip()

        protocol.comment('Distributing mastermix...')
        pick_up(p300)
        t_vol = round(sum(vol_list)/8)
        for well in pcr_tubes.columns()[0]:
            p300.transfer(t_vol, reaction_mix, well, new_tip='never')
            p300.blow_out()
        p300.drop_tip()

    # Add controls to PCR strip
    if ADD_CONTROLS:
        ctrl_wells = ['F12', 'G12', 'H12']
        ctrl_srcs = [water, pos_ctrl, neg_ctrl]

        for src, dest in zip(ctrl_srcs, ctrl_wells):
            pick_up(p300)
            p300.aspirate(20, src)
            p300.dispense(20, pcr_tubes[dest])
            p300.blow_out()
            p300.drop_tip()

    # Distribute master mix
    pick_up(m20)
    for col in mm_cols:
        m20.transfer(15, mm_tubes, col, new_tip='never')
        m20.blow_out()
    m20.drop_tip()

    # Add samples to PCR plate
    protocol.comment('Adding samples to PCR plate...')
    for samp, col in zip(samples, mm_cols):
        pick_up(m20)
        m20.transfer(5, samp, col, new_tip='never')
        m20.mix(5, 15, col)
        m20.blow_out()
        m20.drop_tip()

    if ADD_CONTROLS:
        protocol.comment('Adding controls to PCR plate...')
        pick_up(m20)
        m20.transfer(5, ctrl_tubes, mm_cols[-1], new_tip='never')
        m20.mix(5, 15, mm_cols[-1])
        m20.blow_out()
        m20.drop_tip()

    protocol.comment('Protocol complete!')
