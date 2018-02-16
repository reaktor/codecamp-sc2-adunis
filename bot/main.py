import json
from pathlib import Path

import sc2
from sc2.constants import *


class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    @property
    def nexus_count(self):
        return self.units(UnitTypeId.NEXUS).amount

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"Name: {self.NAME}")
        if self.units(UnitTypeId.PROBE).amount < 16 * self.nexus_count:
            await self.build_probes()
        if self.supply_left <= 2 and not self.already_pending(UnitTypeId.PYLON):
            await self.build_pylons()
        if self.units(UnitTypeId.GATEWAY).amount < 1 and not self.already_pending(UnitTypeId.GATEWAY):
            await self.build_gateway()
        if self.nexus_count < 2:
            await self.build_expansion()
        await self.build_army()
        await self.distribute_workers()

    async def build_probes(self):
        for nexus in self.units(UnitTypeId.NEXUS).ready.noqueue:
            if self.can_afford(UnitTypeId.PROBE):
                await self.do(nexus.train(UnitTypeId.PROBE))

    async def build_pylons(self):
        nexus = self.units(UnitTypeId.NEXUS).first
        if self.can_afford(UnitTypeId.PYLON):
            await self.build(UnitTypeId.PYLON, nexus.position.towards(self.game_info.map_center, 10))

    async def build_gateway(self):
        nexus = self.units(UnitTypeId.NEXUS).first
        if self.can_afford(UnitTypeId.GATEWAY):
            await self.build(UnitTypeId.GATEWAY, nexus, max_distance=50)

    async def build_army(self):
        if self.units(UnitTypeId.NEXUS).amount < 2:
            pass
        for gateway in self.units(UnitTypeId.GATEWAY):
            if self.can_afford(UnitTypeId.ZEALOT) and gateway.noqueue:
                await self.do(gateway.train(UnitTypeId.ZEALOT))

    async def build_expansion(self):
        if self.can_afford(NEXUS):
            location = await self.get_next_expansion()
            await self.build(NEXUS, near=location)
