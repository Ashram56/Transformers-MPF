"""Credits and pricing as the ROM's OS does them (MPF's credits mode cannot: it has no pricing units, ladders
or the ROM's coin task). The credit record is kept in MPF's data file "tf_credits" like the ROM's NVRAM.

Coin task FUN_00004a50, one per coin switch closure [0x00004cb4]:
- waits adj 62 COIN INPUT DELAY ticks (61 = OFF: no wait) and drops the coin when the coin is refused during
  the wait (FUN_000049f8: the service menu runs, gf_state 0x100);
- audits the slot's coin counter (left 2, right 4, center 3, 4th 5, 5th 6);
- the pricing entry of adj 28 GAME PRICING (FUN_0000498c) gives the slot's units; the meter and audit 7
  METER CLICKS count the units;
- each unit steps the unit counter (it wraps at the ladder length; -1 after a reset) and adds the credits of
  the ladder at that step (FUN_00004890: never above adj 33 CREDIT LIMIT): audit 1 TOTAL PAID CREDITS by the
  ladder's credits, event 0x19 (a sound, flag 47); deff 10 per unit; event 0x1a (a sound) when no
  unit gave a credit.
- The credit text (FUN_00004ff4): "FREE PLAY" on adj 34, else "CREDITS n", "CREDITS a/b" or
  "CREDITS n a/b" (units since the last credit over the units of the ladder step that gives the next one;
  attract capture: "CREDITS 1/3" after one coin).
This is the Tron 1.74 OS model (github.com/Ashram56/Tron-Legacy-MPF game/tron/credits.py, the same SAM OS; the
addresses are Tron's; the same algorithm on tf_180, rom/rom_data/settings/pricing.json "algorithm"). The 68
pricing presets come from pricing.json; CUSTOM (68) uses the operator's SET CUSTOM PRICING values (machine vars
custom_coin_units, custom_units_per_credit; interim, the ROM's custom ladder editor is not modelled).
"""
import json
import os

# coin switch -> (ROM slot 0-4, slot audit counter): pricing.json coin_slots (observed, keys 3-6 of PinMAME)
SLOTS = {"s_left_coin_slot": (0, 2), "s_center_coin_slot": (1, 3), "s_right_coin_slot": (2, 4),
         "s_fourth_coin_slot": (3, 5), "s_fifth_coin_slot": (4, 6)}
CREDIT_SOUND, COIN_SOUND = 0x043, 0x042   # observed (traces/sounds.jsonl): 0x043 on the coin that completes a credit, 0x042 on the others
METER_AUDIT, PAID_CREDITS_AUDIT, SERVICE_CREDITS_AUDIT = 7, 1, 0x24
# The 68 pricing presets (rom/rom_data/settings/pricing.json, by adj 28 value; code, checked in the emulator
# for USA 10): units per slot of the preset's coin door and the credit ladder. Factory default 66 = USA 10.
PRICING_JSON = os.path.join(os.path.dirname(__file__), "..", "..", "rom", "rom_data", "settings", "pricing.json")
USA_10 = {"units": {0: 1, 1: 4, 2: 1, 3: 1}, "ladder": (0, 0, 1, 0, 0, 1, 0, 1)}
CUSTOM = 68
_PRESETS = None


def presets():
    """adj 28 value -> (units per slot, ladder), from pricing.json (USA 10 alone without the extraction)."""
    global _PRESETS
    if _PRESETS is None:
        _PRESETS = {66: (USA_10["units"], USA_10["ladder"])}
        if os.path.exists(PRICING_JSON):
            with open(PRICING_JSON, encoding="utf-8") as f:
                for p in json.load(f)["presets"]:
                    units = {i: n for i, n in enumerate(p["slot_units"]) if n}
                    _PRESETS[int(p["adj_value"])] = (units, tuple(p["ladder"]))
    return _PRESETS


FREE_GAME_UNLIMITED = 10              # adj 25 FREE GAME LIMIT: 10 = UNLIMITED, 0 = NO FREE GAMES
DELAY_OFF = 61                        # adj 62 COIN INPUT DELAY: 61 = OFF


class Credits:

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        self.store = self.machine.create_data_manager("tf_credits")
        data = self.store.get_data() or {}
        self.credits = int(data.get("credits", 0))
        self.counter = int(data.get("counter", -1))
        self.free_games = 0           # credits awarded in the running game (adj 25)

    def save(self):
        self.store.save_all(data={"credits": self.credits, "counter": self.counter})

    # ------------------------------------------------------------------ pricing

    def pricing(self):
        """(units per slot, credit ladder) of adj 28."""
        if self.os.adj[28] == CUSTOM:
            var = self.machine.variables.get_machine_var
            per_credit = max(1, int(var("custom_units_per_credit") or 3))
            return {1: max(1, int(var("custom_coin_units") or 1))}, (0,) * (per_credit - 1) + (1,)
        return presets().get(self.os.adj[28], presets()[66])

    def slots(self):
        """The coin switches this machine has."""
        return [name for name in SLOTS if name in self.machine.switches]

    def free_play(self):
        return self.os.adj[34] == 1

    def can_start(self, needed=1):
        """FUN_000202a8 / start_button_handler: free play or enough credits."""
        return self.free_play() or self.credits >= needed

    # ------------------------------------------------------------------ coins

    def coin(self, switch):
        slot = SLOTS[switch]
        delay = self.os.adj[62]
        if delay == DELAY_OFF:
            self._accept(*slot)
            return
        self.os.after(delay, lambda: None if self.os.in_service else self._accept(*slot))

    def _accept(self, slot, audit):
        os_ = self.os
        os_.audit(audit)
        units_table, ladder = self.pricing()
        units = units_table.get(slot, 0)
        if not units:                               # coin_task 0x3f00: a slot without units counts nothing more
            return
        os_.audit(METER_AUDIT, units)
        credited = False
        for _ in range(units):
            self.counter = self.counter + 1 if self.counter + 1 < len(ladder) else 0
            credits = ladder[self.counter]
            if credits:
                self.add(credits)
                os_.audit(PAID_CREDITS_AUDIT, credits)
                credited = True
                os_.sound(CREDIT_SOUND)             # event 0x19 (credit added) handler
                os_.flag_set(47)
            self.save()
            os_.deff_start(10, credits=self.text())
        if not credited:
            os_.sound(COIN_SOUND)                  # event 0x1a (coin without a credit) handler

    # ------------------------------------------------------------------ credits

    def add(self, n):
        """FUN_00004890: add up to adj 33 CREDIT LIMIT; returns the credits added."""
        n = max(0, min(n, self.os.adj[33] - self.credits))
        if n:
            self.credits += n
            self.save()
            self.changed()
        return n

    def take(self, n=1):
        """FUN_00004e9c: take up to n credits (also on free play while credits remain)."""
        n = min(n, self.credits)
        if n:
            self.credits -= n
            self.save()
            self.changed()
        return n

    def award(self, n=1):
        """A free game (replay, special, match or high-score credit, FUN_00004cf0) within adj 25 FREE GAME
        LIMIT per game (inferred: the decompile has no reader of adj 25). Returns the credits added."""
        limit = self.os.adj[25]
        if limit != FREE_GAME_UNLIMITED:
            n = max(0, min(n, limit - self.free_games))
        n = self.add(n) if n else 0
        self.free_games += n
        return n

    def service_credit(self):
        """BACK outside the service menu [0x0000fc20 case 1]: one service credit, audit 0x24 SERVICE
        CREDITS when it was added, deff 17."""
        if self.add(1):
            self.os.audit(SERVICE_CREDITS_AUDIT)
        self.os.deff_start(17, credits=self.text())

    def reset(self):
        """RESET CREDITS (FUN_00004e88): no credits, unit counter -1."""
        self.credits, self.counter = 0, -1
        self.save()
        self.changed()

    def changed(self):
        """FUN_00020448 after every credit change: the start button lamp."""
        self.machine.events.post("tf_credits_changed", credits=self.credits)
        self.os.start_button_lamp()

    def fraction(self):
        """FUN_00004d48: (units since the last credit, units of the step that gives the next credit), or None."""
        ladder = self.pricing()[1]
        p = self.counter
        if p < 0 or p >= len(ladder) or ladder[p]:
            return None
        nxt = p
        while nxt + 1 < len(ladder) and not ladder[nxt + 1]:
            nxt += 1
        nxt += 1
        last = p
        while last >= 0 and not ladder[last]:
            last -= 1
        a, b = p - last, nxt - last
        for d in range(min(a, b), 1, -1):
            if a % d == 0 and b % d == 0:
                a, b = a // d, b // d
        return a, b

    def text(self):
        """FUN_00004ff4: the credit text of the attract page and of deffs 10, 15 and 17."""
        if self.free_play():
            return "FREE PLAY"
        frac = self.fraction()
        if not frac:
            return "CREDITS {}".format(self.credits)
        if not self.credits:
            return "CREDITS {}/{}".format(*frac)
        return "CREDITS {} {}/{}".format(self.credits, *frac)
