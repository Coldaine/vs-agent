# Game reference — Vampire Survivors (domain knowledge for all agents)

This is the shared encyclopedia. The labeler uses it to label frames,
the planner uses it for build decisions, the theorist uses it to form
causal claims, and the builder uses it to write sensible prompts.
When this file and a model's intuition disagree, this file wins.
(Scope: base game, Mad Forest, Antonio — the fixed eval conditions.
Re-verify numbers against current patch if behavior looks off.)

## 1. What the game is

- Top-down auto-battler. Attacks fire automatically on cooldowns.
  The ONLY moment-to-moment input is 8-direction movement.
- Kill enemies -> they drop XP gems -> collect gems -> level up ->
  pick 1 of 3-4 weapon/passive options (reroll/skip/banish available
  later). Level-up PAUSES the game: strategy decisions are free of
  reaction-time pressure. Movement decisions are not.
- A run lasts 30 minutes. Enemy waves escalate on a fixed timer.
  Death ends the run; reaching 30:00 spawns The Reaper (effectively
  run success). Score for this project: survived_s, then level.
- Damage is mostly contact-based: enemies hurt you by touching you.
  Therefore survival == distance management. Position is everything.

## 2. Mad Forest specifics (the eval stage)

- Open grass field with tree obstacles and wall-like edges in places.
  Trees block movement and LOS for some weapons; getting herded into
  tree pockets is a common death. Map edges and corners are death
  traps after minute ~10 — never drift toward them.
- Enemy timeline (approximate, minute marks):
  - 0:00-2:00 — bats: fast, weak, come in loose packs from one
    direction at a time. Easy to herd.
  - ~2:00-5:00 — skeletons/zombies join: slower, tougher, denser.
  - ~5:00 — first elite (larger, glowing, much more HP, drops a
    chest when killed). Elites do burst contact damage — respect them.
  - 5:00-10:00 — mixed waves, density climbs; ghosts (fast, weave)
    appear.
  - ~10:00 — major wave transition; screen density jumps.
  - 15:00+ — heavy elites and dense mixed swarms; wave bosses with
    projectiles appear in later minutes. 20:00+ is the chaos regime:
    hundreds of sprites, particles everywhere.
- Chests from elites/bosses: can upgrade or EVOLVE weapons. Standing
  near a chest is safe; open it when the area is clear.

## 3. Movement doctrine (the pilot's real curriculum)

1. Never stop moving. A stationary agent is a dying agent. HOLD is
   only for a genuine safe pocket with all exits threatened.
2. Orbit, don't flee in lines. Circle-kiting around the swarm's
   centroid keeps distance roughly constant while your AoE grinds
   the pack down. Fleeing straight herds you into the next wave or
   a wall.
3. Move PERPENDICULAR to the dominant threat axis when possible, not
   directly away — directly-away splits your clearance between two
   flanks and traps you between waves.
4. Antonio's Whip attacks horizontally (left/right). Early game:
   align so the pack is to your left or right, and strafe vertically
   while the whip clears the horizontal lane. This is the single
   highest-value early tactic.
5. Collect gems during lulls and after clearing a pack, not while
   encircled. Gem-greed is a top-3 cause of death: the correct_action
   when threats and gems coincide is AWAY from the threat, not toward
   the gem. Gems persist; HP does not.
6. Never reverse into your own trail: you just came through the
   enemies you cleared or provoked. Prefer smooth arcs.
7. Elites: keep >200px, let AoE grind them, never path between an
   elite and a wall.
8. If encirclement is forming (threats in 6+ octants), immediately
   move toward the emptiest adjacent octant PAIR, not just the
   emptiest single octant — a single-octant gap is often a closing
   jaw.

## 4. Build doctrine (the planner's curriculum)

Antonio starts with Whip. Rules of thumb for Mad Forest:

- Early (0-5 min): damage and clear speed. Priorities: Whip upgrades,
  Garlic (point-blank swarm clear), Magic Wand or Knife as second
  weapon, Spinach (damage), Attractorb (pickup range — quietly one of
  the best early picks; starves you less).
- Mid (5-15): assemble an evolution pair (see below), then
  survivability: Armor, Hollow Heart (max HP), Pummarola (regen),
  Wings (move speed) if kiting feels tight. Empty Tome (cooldown) and
  Candelabrador (area) are strong force multipliers.
- Late (15+): complete evolutions, Duplicator (projectile count),
  reroll junk, banish items that will never evolve.
- Evolutions (weapon at max level + paired passive owned, then chest):
  Whip + Hollow Heart -> Bloody Tear (lifesteal; excellent);
  Garlic + Pummarola -> Soul Eater; Magic Wand + Empty Tome -> Holy
  Wand; Knife + Bracer -> Thousand Edge; Axe + Candelabrador -> Death
  Spiral; Fire Wand + Spinach -> Hellfire. Bloody Tear or Soul Eater
  should be the default first-evolution target for this agent because
  sustain fixes attrition deaths.
- Max 6 weapons and 6 passives. Never take a 7th of either. Every
  pick should either be an upgrade, an evolution component, or
  survivability. If all options are junk: reroll > skip > banish.
- Level-up screen layout: options listed vertically, keyboard
  navigable; the controller reads options via OCR and clicks/selects.

## 5. Failure taxonomy (shared vocabulary for autopsy + theorist)

- cornered: herded into a wall/trees/jaw; set up 10-30s before death.
- elite_burst: elite contact within ~2s; usually a route error, not a
  reaction error.
- boss_projectile: late-run; dodging projectiles while swarmed.
- starvation: level deficit from uncollected gems -> DPS too low ->
  overwhelmed. The fix is upstream (Attractorb, gem discipline).
- attrition: slow HP bleed vs no sustain; the fix is build-side
  (Bloody Tear/Soul Eater/regen).
- unknown: use freely. A wrong label is worse than no label.

## 6. Frame-labeling rubric (for VLM-generated eval labels)

For each frame, label:
- player position (approx center) and facing context.
- threats_by_octant: count distinct enemy sprites per octant
  (N,NE,E,SE,S,SW,W,NW relative to player). Elites count x3.
- gems_by_octant: count visible gem clusters per octant.
- is_level_up_screen: bool (bright overlay, option cards, paused
  background).
- correct_action, by this decision procedure:
  1. If any enemy within ~90px: move away from the nearest-threat
     vector sum (perpendicular preferred over directly-away).
  2. Else if threats in 6+ octants: move toward the emptiest octant
     PAIR.
  3. Else: drift toward the nearest gem cluster, unless that octant
     holds a wall/map edge or an elite.
  4. Tiebreak: preserve current heading (no dithering); second
     tiebreak: clockwise orbit.
- Labels come from the rubric and this reference, not from the
  labeler's vibes. A senior-model label pass + a second model's
  audit pass; disagreements go to the human — expected to be a
  handful of frames, not a hundred.

