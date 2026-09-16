"""Isolated PokerKit 0.7.5 NLHE reopening corrections.

Keep PokerKit's betting, settlement and ranking machinery. These narrow State
overrides fix the opening full-raise increment and check each player's own
amount faced. TDA 2024 rule 47 / examples 1-A and 3-A are independent fixtures:
https://www.pokertda.com/view-poker-tda-rules/

The state-construction argument forwarding follows PokerKit's Poker.__call__.
PokerKit is MIT licensed; its notice is in research/patches/pokerkit-LICENSE.
Historical unpatched replays use the original State and remain unchanged.
"""
from importlib.metadata import version

from pokerkit import NoLimitTexasHoldem, State

ENGINE_ID = "pokerkit-0.7.5-reopening-v1"


class ReopeningState(State):
    def _begin_betting(self):
        super()._begin_betting()
        if self.actor_index is not None:
            # Upstream starts at zero: the first short all-in then incorrectly
            # clears prior action, including players who limped or checked.
            self.completion_betting_or_raising_amount = max(
                self.completion_betting_or_raising_amount,
                self.street.min_completion_betting_or_raising_amount)

    def _verify_completion_betting_or_raising(self):
        actor = self.actor_index
        if (actor is not None and actor in self.acted_player_indices
                and max(self.bets)-self.bets[actor]
                < self.completion_betting_or_raising_amount):
            # Upstream sums all consecutive short raises globally, including
            # increments a later caller has already matched.
            raise ValueError("This player's raising rights have not reopened")
        super()._verify_completion_betting_or_raising()

    def _update_betting(self, operation=None, status=False):
        active = [p for p in self.player_indices if self.statuses[p] and self.stacks[p]]
        if len(active) <= 1 and (not active or self.bets[active[0]] >= max(self.bets)):
            # No call is owed and no second player can contest further chips.
            # Upstream sometimes leaves a forced check in the action queue.
            status = True
        super()._update_betting(operation, status)


class ReopeningNoLimitTexasHoldem(NoLimitTexasHoldem):
    def __call__(self, raw_starting_stacks, player_count):
        if version("pokerkit") != "0.7.5":
            raise RuntimeError("Revalidate reopening hooks before changing PokerKit version")
        return ReopeningState(
            self.automations, self.deck, self.hand_types, self.streets,
            self.betting_structure, self.ante_trimming_status, self.raw_antes,
            self.raw_blinds_or_straddles, self.bring_in,
            raw_starting_stacks, player_count, mode=self.mode,
            starting_board_count=self.starting_board_count,
            divmod=self.divmod, rake=self.rake)
