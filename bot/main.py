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

    @property
    def nexus_count(self):
        return self.units(NEXUS).amount

    @property
    def production_building_count(self):
        return self.units(GATEWAY).amount + self.units(WARPGATE).amount

    @property
    def staging_point(self):
        return self.units(NEXUS).first.position.towards(self.game_info.map_center, 10)

    @property
    def attack_staging_point(self):
        return self.enemy_start_locations[0].towards(self.game_info.map_center, 30)

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"Name: {self.NAME}")
        if self.units(PROBE).amount < 16 * self.nexus_count:
            await self.build_probes()
        if self.supply_left <= 2 * self.production_building_count and not self.already_pending(PYLON):
            await self.build_pylons()
        if self.nexus_count < 2:
            await self.build_expansion()
        await self.build_warpgate_tech()
        await self.build_army()
        await self.distribute_workers()
        await self.build_economy()
        await self.attack()

    async def build_warpgate_tech(self):
        need_ccore = not self.units(CYBERNETICSCORE).ready.exists and not self.already_pending(CYBERNETICSCORE)
        ccore_reqs = self.units(PYLON).ready.exists and self.units(GATEWAY).ready.exists
        if need_ccore and ccore_reqs and self.can_afford(CYBERNETICSCORE):
            nexus = self.units(NEXUS).first
            await self.build(CYBERNETICSCORE, nexus, max_distance=20)

        ccore = self.units(CYBERNETICSCORE).ready
        if ccore.exists and self.can_afford(RESEARCH_WARPGATE) and not self.warpgate_started:
            c = ccore.first
            await self.do(c(RESEARCH_WARPGATE))
            self.warpgate_started = True

        for gateway in self.units(GATEWAY).ready:
            abilities = await self.get_available_abilities(gateway)
            if AbilityId.MORPH_WARPGATE in abilities and self.can_afford(AbilityId.MORPH_WARPGATE):
                await self.do(gateway(MORPH_WARPGATE))

    async def build_forge(self):
        if not self.units(FORGE).exists and self.can_afford(FORGE):
            pylons = self.units(PYLON).ready
            await self.build(FORGE, near=pylons.closest_to(nexus))

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

    async def build_economy(self):
        if not self.units(ASSIMILATOR).exists and not self.already_pending(ASSIMILATOR) and self.can_afford(ASSIMILATOR):
            nexus = self.units(NEXUS).first
            await self.build_assimilator(nexus)
        if self.units(GATEWAY).amount < 4 and not self.already_pending(GATEWAY):
            await self.build_gateway()

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
            units_at_base = self.units(ZEALOT).idle.closer_than(10, b)  | self.units(STALKER).idle.closer_than(10, b)
            for unit in units_at_base:
                await self.do(unit.move(self.staging_point))


    async def select_unit_to_warp(self, warpgate):
        prios = [
            { "unit": STALKER, "ability": WARPGATETRAIN_STALKER },
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
        if self.can_afford(NEXUS):
            location = await self.get_next_expansion()
            await self.build(NEXUS, near=location)

    async def attack(self):
        if self.units(ZEALOT).amount > 30:
            for unit in self.units(ZEALOT) | self.units(STALKER):
                await self.do(unit.attack(self.enemy_start_locations[0]))
