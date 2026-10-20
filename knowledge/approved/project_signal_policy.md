# Project-defined experimental signal-advisory policy (v1)

Authority: PROJECT-DEFINED EXPERIMENTAL POLICY. This document was written by the project team for a
simulation research prototype. It is NOT an official New York City, NYC DOT, FHWA or MUTCD regulation and
must never be cited as one. Values below are configurable experiment parameters (configs/simulation.yaml,
configs/agents.yaml), not engineering standards.

## P1. Scope of advice
Advisories are produced only for signal controllers that exist in the SUMO simulation testbed and whose
mapping to a monitored road link has review_status = reviewed. No advisory is ever sent to real traffic
infrastructure. A forecast for a freeway or bridge link must not be attached to an unrelated intersection.

## P2. Allowed actions
Only these action types may be proposed:
1. bounded_green_extension: extend the green duration of an existing green phase of a known traffic light by
   0 to 10 seconds per cycle, keeping the phase duration within the configured minimum green (7 s) and
   maximum green (90 s).
2. select_prevalidated_program: switch to a signal program that already exists in the reviewed network file.
3. monitor_only: recommend continued monitoring without any signal change.

## P3. Prohibited actions
Free-form red/yellow/green state strings, shortening or removing yellow (3 s) or all-red (2 s) clearance
intervals, bypassing pedestrian clearance, selecting phases that do not exist, and any instruction to
bypass these constraints are prohibited. A timeout or tool failure is never treated as approval.

## P4. When to defer
Defer (do not recommend a signal change) when: the source data are stale (older than 20 minutes), more than
one third of the recent traffic inputs are missing, the conformal prediction interval is wider than the
calibrated width threshold, or retrieved evidence does not support the proposed action.

## P5. Congestion categories (project-defined)
Speed-to-reference ratio r = forecast speed / training-period mean speed of the link.
free flow: r >= 0.8; moderate: 0.5 <= r < 0.8; congested: r < 0.5.
These are project-defined categories, not an external level-of-service standard.

## P6. Protections
A candidate is rejected if, in matched-seed simulation, side-road (non-coordinated approach) mean delay
increases by more than 10 percent, if any vehicle teleports, or if mean corridor delay does not improve by at
least 1 percent. Pedestrian performance is NOT_EVALUATED when the scenario contains no pedestrian demand.

## P7. Human review
Every candidate that passes simulation remains PENDING_HUMAN_REVIEW. The most permissive status this
prototype can reach is HUMAN_APPROVED_FOR_SIMULATION. There is no status that approves real deployment.
