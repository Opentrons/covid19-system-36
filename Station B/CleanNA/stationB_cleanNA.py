from opentrons import types
import math


metadata = {
    'protocolName': 'Clean NA Extraction (200µl sample input)',
    'author': 'Chaz <chaz@opentrons.com>',
    'apiLevel': '2.4'
}

NUM_SAMPLES = 8
# start with 8 samples, slowly increase to 48, then 94 (max is 94)
ELUTION_VOL = 50
STARTING_VOL = 200


# Start protocol
def run(ctx):
    # load labware and pipettes
    num_cols = math.ceil(NUM_SAMPLES/8)
    tips300 = [ctx.load_labware('opentrons_96_tiprack_300ul', slot, '200µl filtertiprack')
               for slot in ['5', '9', '7', '10']]

    all_tips = [tr['A'+str(i)] for tr in tips300 for i in range(1, 13)]
    [tips1, tips2, tips3, tips4] = [
        all_tips[i:i+num_cols] for i in range(0, num_cols*4, num_cols)
        ]

    single_tips = ctx.load_labware('opentrons_96_tiprack_300ul', '6')

    m300 = ctx.load_instrument(
        'p300_multi_gen2', 'left')

    magdeck = ctx.load_module('magdeck', '4')
    magdeck.disengage()
    magheight = 13.7
    magplate = magdeck.load_labware('nest_96_wellplate_2ml_deep')
    tempdeck = ctx.load_module('Temperature Module Gen2', '1')
    flatplate = tempdeck.load_labware(
                'opentrons_96_aluminumblock_nest_wellplate_100ul',)
    waste = ctx.load_labware('nest_1_reservoir_195ml', '11',
                             'Liquid Waste').wells()[0].top()
    """
    Second waste container for runs of 96 samples
    waste2 = ctx.load_labware('nest_1_reservoir_195ml', '8',
                             'Liquid Waste').wells()[0].top()"""
    res2 = ctx.load_labware(
        'nest_12_reservoir_15ml', '3', 'reagent reservoir 2')
    res1 = ctx.load_labware(
        'nest_12_reservoir_15ml', '2', 'reagent reservoir 1')
    lmm = [well for well in res1.wells()[:2] for _ in range(6)][:num_cols]
    iso_beads = [well for well in res1.wells()[3:6] for _ in range(4)][:num_cols]
    wb = [well for well in res1.wells()[7:10] for _ in range(4)][:num_cols]
    etoh1 = [well for well in res2.wells()[:3] for _ in range(4)][:num_cols]
    etoh2 = [well for well in res2.wells()[3:6] for _ in range(4)][:num_cols]
    water = res2.wells()[-1]

    magsamps = magplate.rows()[0][:num_cols]
    elution_samps = flatplate.rows()[0][:num_cols]

    magdeck.disengage()  # just in case
    tempdeck.set_temperature(4)

    m300.flow_rate.aspirate = 50
    m300.flow_rate.dispense = 150
    m300.flow_rate.blow_out = 300

    x_offset = [1, -1] * 6

    def init_well_mix(reps, loc, vol):
        loc1 = loc.bottom().move(types.Point(x=1, y=0, z=0.6))
        loc2 = loc.bottom().move(types.Point(x=1, y=0, z=5.5))
        loc3 = loc.bottom().move(types.Point(x=-1, y=0, z=0.6))
        loc4 = loc.bottom().move(types.Point(x=-1, y=0, z=5.5))
        m300.aspirate(20, loc1)
        for _ in range(reps-1):
            m300.aspirate(vol, loc1)
            m300.dispense(vol, loc4)
            m300.aspirate(vol, loc3)
            m300.dispense(vol, loc2)
        m300.dispense(20, loc2)

    def well_mix(reps, loc, vol, side):
        opp_side = side * -1
        loc1 = loc.bottom().move(types.Point(x=side, y=0, z=0.6))
        loc2 = loc.bottom().move(types.Point(x=opp_side, y=0, z=4))
        m300.aspirate(20, loc2)
        mvol = vol-20
        for _ in range(reps-1):
            m300.aspirate(mvol, loc2)
            m300.dispense(mvol, loc1)
        m300.dispense(20, loc2)

    # transfer 240ul of lysis mastermix
    ctx.comment('Adding lysis mastermix mixture to samples:')
    m300.pick_up_tip(single_tips['A1'])
    for well, reagent in zip(magsamps, lmm):
        m300.mix(3, 200, reagent)
        m300.aspirate(120, reagent)
        m300.dispense(120, well.top(-5))
        m300.aspirate(10, well.top(-5))
        m300.aspirate(120, reagent)
        m300.dispense(130, well.top(-5))
        m300.blow_out(well.top(-3))
    m300.drop_tip()

    # transfer 290ul of iso + beads
    ctx.comment('Adding iso + beads to samples:')
    m300.pick_up_tip(single_tips['A2'])
    for well, reagent in zip(magsamps, iso_beads):
        m300.mix(3, 200, reagent)
        m300.aspirate(145, reagent)
        m300.dispense(145, well.top(-5))
        m300.aspirate(10, well.top(-5))
        m300.aspirate(145, reagent)
        m300.dispense(155, well.top(-5))
        m300.blow_out(well.top(-3))
    m300.drop_tip()

    # mix samples
    ctx.comment('Mixing samples:')
    for well, tip in zip(magsamps, tips1):
        m300.pick_up_tip(tip)
        init_well_mix(5, well, 160)
        m300.blow_out()
        init_well_mix(5, well, 160)
        m300.aspirate(20, well.top(-5))
        m300.drop_tip(tip)

    ctx.delay(minutes=5)
    ctx.comment('Incubating for 5 minutes')

    magdeck.engage(height=magheight)
    ctx.comment('Incubating on magdeck for 3 minutes')
    ctx.delay(minutes=3)

    def supernatant_removal(vol, src, dest, side):
        s = side * -1
        m300.flow_rate.aspirate = 20
        tvol = vol
        asp_ctr = 0
        while tvol > 180:
            m300.aspirate(
                180, src.bottom().move(types.Point(x=s, y=0, z=0.5)))
            m300.dispense(180, dest)
            m300.aspirate(10, dest)
            tvol -= 180
            asp_ctr += 1
        m300.aspirate(
            tvol, src.bottom().move(types.Point(x=s, y=0, z=0.5)))
        dvol = 10*asp_ctr + tvol
        m300.dispense(dvol, dest)
        m300.flow_rate.aspirate = 50

    # Remove supernatant
    ctx.comment('Removing supernatant:')
    removal_vol = STARTING_VOL + 240 + 290 + 40

    for well, tip, side in zip(magsamps, tips1, x_offset):
        m300.pick_up_tip(tip)
        supernatant_removal(removal_vol, well, waste, side)
        m300.drop_tip()

    magdeck.disengage()

    def wash_step(src, mtimes, stip, msg, trash_tips=False):
        ctx.comment(f'Wash Step {msg} - Adding reagent to samples:')
        m300.pick_up_tip(single_tips[stip])
        for s, well in zip(src, magsamps):
            m300.aspirate(175, s)
            m300.dispense(175, well.top(-4))
            m300.aspirate(10, well.top(-4))
            m300.aspirate(175, s)
            m300.dispense(185, well.top(-4))
            m300.blow_out(well.top(-2))
        m300.drop_tip()

        for well, tip, x in zip(magsamps, tips2, x_offset):
            m300.pick_up_tip(tip)
            well_mix(mtimes, well, 180, x)
            m300.blow_out()
            m300.drop_tip(tip)

        magdeck.engage(height=magheight)
        ctx.comment('Incubating on MagDeck for 3 minutes.')
        ctx.delay(minutes=3)

        ctx.comment(f'Removing supernatant from Wash {msg}:')
        svol = 450
        for well, tip, x in zip(magsamps, tips2, x_offset):
            m300.pick_up_tip(tip)
            supernatant_removal(svol, well, waste, x)
            if trash_tips:
                m300.drop_tip()
            else:
                m300.drop_tip(tip)
        magdeck.disengage()

    wash_step(wb, 20, 'A3', '1 Wash Buffer')

    wash_step(etoh1, 15, 'A4', '2 Ethanol Wash 1')

    wash_step(etoh1, 15, 'A5', '3 Ethanol Wash 2', trash_tips=True)

    ctx.comment('Allowing beads to air dry for 15 minutes.')
    ctx.delay(minutes=15)

    # Add water for elution
    ctx.comment('Adding NF-water to wells for elution:')
    t_vol = ELUTION_VOL + 20
    m_vol = ELUTION_VOL - 10
    for well, tip, x in zip(magsamps, tips3, x_offset):
        m300.pick_up_tip(tip)
        m300.aspirate(20, water.top())
        m300.aspirate(ELUTION_VOL, water)
        for _ in range(15):
            m300.dispense(
                m_vol, well.bottom().move(types.Point(x=x, y=0, z=2)))
            m300.aspirate(
                m_vol, well.bottom().move(types.Point(x=x, y=0, z=0.5)))
        m300.dispense(t_vol, well)
        m300.blow_out()
        m300.drop_tip()

    ctx.comment('Incubating at room temp for 10 minutes.')
    ctx.delay(minutes=10)

    # Step 21 - Transfer elutes to clean plate
    magdeck.engage(height=magheight)
    ctx.comment('Incubating on MagDeck for 2 minutes.')
    ctx.delay(minutes=2)

    ctx.comment('Transferring elution to final plate:')
    m300.flow_rate.aspirate = 10
    for src, dest, tip, x in zip(magsamps, elution_samps, tips4, x_offset):
        s = x * -1
        m300.pick_up_tip(tip)
        m300.aspirate(ELUTION_VOL, src.bottom().move(types.Point(x=s, y=0, z=0.6)))
        m300.dispense(ELUTION_VOL, dest)
        m300.drop_tip()

    magdeck.disengage()

    ctx.comment('Congratulations! The protocol is complete')
