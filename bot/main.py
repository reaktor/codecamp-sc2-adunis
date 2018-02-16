import json
import random
from pathlib import Path

import sc2
from sc2.constants import *



class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    def __init__(self):
        self.warpgate_started = False
        self.only_gassless_units = True

    @property
    def nexus_count(self):
        return self.units(NEXUS).amount

    @property
    def production_building_count(self):
        return self.units(GATEWAY).amount + self.units(WARPGATE).amount

    @property
    def staging_point(self):
        return self.units(NEXUS).first.position.towards(self.game_info.map_center, 11)

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"Name: {self.NAME}")
        if self.nexus_count > 0:
            if self.units(PROBE).amount < 16 * self.nexus_count:
                await self.build_probes()
            if self.supply_left <= 2 * self.production_building_count and not self.already_pending(PYLON):
                await self.build_pylons()
            if self.nexus_count < 2:
                await self.build_expansion()
            if not self.warpgate_started:
                await self.build_warpgate_tech()
            await self.warpgates()
            await self.build_economy()
            await self.build_army()
            await self.distribute_workers()
            await self.attack()

            if not self.units(FORGE).exists:
                await self.build_forge()
            else:
                await self.build_cannons()
        else:
            await self.chat_send('gg no re')
    async def build_warpgate_tech(self):
        ccore_reqs = self.units(PYLON).ready.exists and self.units(GATEWAY).ready.exists and not self.already_pending(CYBERNETICSCORE)
        if ccore_reqs and self.can_afford(CYBERNETICSCORE):
            nexus = self.units(NEXUS).first
            await self.build(CYBERNETICSCORE, nexus, max_distance=20)

        ccore = self.units(CYBERNETICSCORE).ready
        if ccore.exists and self.can_afford(RESEARCH_WARPGATE) and not self.warpgate_started:
            c = ccore.first
            await self.do(c(RESEARCH_WARPGATE))
            self.warpgate_started = True


    async def warpgates(self):
        for gateway in self.units(GATEWAY).ready:
            abilities = await self.get_available_abilities(gateway)
            if AbilityId.MORPH_WARPGATE in abilities and self.can_afford(AbilityId.MORPH_WARPGATE):
                await self.do(gateway(MORPH_WARPGATE))

    async def build_forge(self):
        if not self.units(FORGE).exists and self.can_afford(FORGE):
            pylons = self.units(PYLON).ready
            nexus = random.choice(self.units(NEXUS))
            if pylons and nexus and self.minerals > 1000:
                await self.build(FORGE, near=pylons.closest_to(nexus))

    async def build_cannons(self):
        enemy = self.enemy_start_locations[0]
        forward_pylon = self.units(PYLON).closest_to(enemy)
        if self.minerals > 500:
            await self.build(PHOTONCANNON, near=forward_pylon)

    async def build_probes(self):
        for nexus in self.units(NEXUS).ready.noqueue:
            if self.can_afford(PROBE):
                await self.do(nexus.train(PROBE))

    async def build_pylons(self):
        nexus = self.units(NEXUS).first
        if self.can_afford(PYLON):
            await self.build(UnitTypeId.PYLON, nexus.position.towards(self.game_info.map_center, 10))

    async def build_gateway(self):
        nexus = self.units(NEXUS).first
        if self.can_afford(GATEWAY):
            await self.build(GATEWAY, nexus, max_distance=50)

    async def build_dark_shrine(self):
        nexus = self.units(NEXUS).first
        if self.can_afford(DARKSHRINE):
            await self.build(DARKSHRINE, nexus, max_distance=50)
            self.only_gassless_units = False
        else:
            self.only_gassless_units = True

    async def build_twilight_council(self):
        nexus = self.units(NEXUS).first
        if self.can_afford(TWILIGHTCOUNCIL):
            await self.build(TWILIGHTCOUNCIL, nexus, max_distance=50)
            self.only_gassless_units = False
        else:
            self.only_gassless_units = True


    async def build_economy(self):
        if self.units(ASSIMILATOR).amount < 2 and not self.already_pending(ASSIMILATOR) and self.can_afford(ASSIMILATOR):
            nexus = self.units(NEXUS).first
            await self.build_assimilator(nexus)
        if self.units(GATEWAY).amount + self.units(WARPGATE).amount < 8 and not self.already_pending(GATEWAY):
            await self.build_gateway()
        if not self.units(TWILIGHTCOUNCIL).exists and not self.already_pending(TWILIGHTCOUNCIL):
            await self.build_twilight_council()
        if not self.units(DARKSHRINE).exists and not self.already_pending(DARKSHRINE):
            await self.build_dark_shrine()

    async def build_assimilator(self, nexus):
        vgs = self.state.vespene_geyser.closer_than(20.0, nexus)
        for vg in vgs:
            if not self.can_afford(ASSIMILATOR):
                break

            worker = self.select_build_worker(vg.position)
            if worker is None:
                break

            if not self.units(ASSIMILATOR).closer_than(1.0, vg).exists:
                await self.do(worker.build(ASSIMILATOR, vg))

    async def build_army(self):
        if self.units(NEXUS).amount < 2:
            pass

        for gateway in self.units(GATEWAY).ready.noqueue:
            if self.can_afford(ZEALOT):
                await self.do(gateway.train(ZEALOT))

        for warpgate in self.units(WARPGATE).ready.noqueue:
            if not self.units(PYLON).ready.exists:
                pass

            output = self.units(PYLON).ready.first
            preferred = await self.select_unit_to_warp(warpgate)

            if preferred:
                placement = await self.find_warp_pylon(preferred["ability"])
                if placement is None:
                    break
                await self.do(warpgate.warp_in(preferred["unit"], placement))

        for b in self.units(GATEWAY) | self.units(WARPGATE):
            units_at_base = self.units(ZEALOT).idle.closer_than(10, b) | self.units(STALKER).idle.closer_than(10, b) | self.units(DARKTEMPLAR).idle.closer_than(10, b)
            for unit in units_at_base:
                await self.do(unit.move(self.staging_point))


    async def select_unit_to_warp(self, warpgate):
        prios = [
            { "unit": DARKTEMPLAR, "ability": WARPGATETRAIN_DARKTEMPLAR },
            { "unit": STALKER, "ability": WARPGATETRAIN_STALKER },
            { "unit": ZEALOT, "ability": WARPGATETRAIN_ZEALOT }
        ] if not self.only_gassless_units else [
            { "unit": ZEALOT, "ability": WARPGATETRAIN_ZEALOT }
        ]

        abilities = await self.get_available_abilities(warpgate)
        preferred = [x for x in prios if (x["ability"] in abilities)]
        if len(preferred) > 0:
            return preferred[0]

    async def find_warp_pylon(self, ability):
        for pylon in self.units(PYLON).ready:
            placement = await self.find_placement(AbilityId.WARPGATETRAIN_ZEALOT, pylon.position.to2, placement_step=1)
            if placement is None:
                continue
            else:
                return placement

    async def build_expansion(self):
        if self.can_afford(NEXUS) and not self.already_pending(NEXUS):
            location = await self.get_next_expansion()
            await self.build(NEXUS, near=location)

    async def attack(self):
        for unit in self.units(DARKTEMPLAR):
            await self.do(unit.attack(self.enemy_start_locations[0]))

        if self.units(ZEALOT).amount > 30:
            for unit in self.units(ZEALOT) | self.units(STALKER) | self.units(DARKTEMPLAR):
                await self.do(unit.attack(self.enemy_start_locations[0]))
