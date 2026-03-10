# Technical Information

This document is the authoritative technical reference for the Tilting Cover integration.

It consolidates technical content previously spread across README and ALGORITHM.md.

## 1) Technical Scope

The integration wraps a basic `cover.*` entity and provides:
- independent cover position tracking,
- independent tilt position tracking,
- queue-based command execution,
- persistent state storage,
- synchronization with external/manual movements.

## 2) Core Principle

**Sequential blind behavior is enforced:**
1. Slats rotate first,
2. cover travel starts only after required slat work is completed.

Configured times are used for **ratio calculation only**, not for internal timing delays.

## 3) Architecture

The implementation uses decoupled responsibilities:

- `cover.py`:
  - core entity behavior,
  - position/tilt calculations,
  - command queue,
  - movement detection.

- `coordinator.py`:
  - integration coordinator,
  - storage handler management.

- `storage.py`:
  - persistent data abstraction,
  - atomic write operations,
  - load/save and recovery support.

## 4) Data Model

### Runtime state (entity)
- current cover position,
- current tilt position,
- underlying cover state,
- underlying cover position,
- queue state (`_command_queue`, `_current_command`, `_command_in_progress`),
- baseline values for independent tracking.

### Persistent storage
Stored per config entry/entity:
- cover position,
- tilt position,
- timestamp,
- additional entity state payload.

## 5) Ratio Model

Let:
- $T$ = `travel_time`,
- $S$ = `slat_rotation_time`,
- $A = T - S$ = effective travel part.

Ratios used by the algorithm:

$$
\text{underlying\_to\_tilt\_ratio} = \frac{T}{S}
$$

$$
\text{underlying\_to\_travel\_ratio} = \frac{T}{A}
$$

Interpretation:
- how much tilt progress is produced by 1% underlying movement,
- how much cover travel progress is produced by 1% underlying movement.

## 6) Independent Position Tracking

Tracking runs continuously on underlying entity state changes.

Algorithm baseline:
- `baseline_position`,
- `baseline_tilt`,
- `baseline_underlying`.

For each underlying movement:
1. determine direction (`opening`/`closing`),
2. determine natural tilt target (`100` for opening, `0` for closing),
3. compute required tilt work,
4. allocate underlying movement:
   - first to tilt work,
   - only remaining part to travel work,
5. clamp results to `0..100`.

This guarantees slats-first behavior in all movement sources.

## 7) Command Queue System

The queue executes commands in order and is independent from calculation logic.

### Stage 1
- performs position movement,
- includes natural directional tilt behavior,
- sends `cover.set_cover_position` to underlying entity.

### Stage 2
- fine-tunes tilt to user requested target,
- skips adjustment within tolerance.

### External movement handling
- detects movement not started by queue,
- clears pending queue,
- injects synthetic/external command context,
- keeps tracking consistent.

### Direction change handling
Direction change during movement is treated as:
1. intermediate stop + baseline store,
2. new movement start in opposite direction.

## 8) Synchronization Rules

Definitive positions from underlying entity are synchronized:
- underlying `0%` forces closed synchronization,
- underlying `100%` forces open synchronization.

Warnings are logged when calculated values disagree significantly with definitive states.

## 9) Persistent State Behavior

Storage operations support:
- atomic pair write (`cover_position`, `tilt_position`, `timestamp`),
- per-entity isolation,
- startup restoration,
- crash/restart recovery.

State is saved:
- on movement stop,
- during lifecycle cleanup,
- on explicit updates.

## 10) Validation and Safety

Safety checks include:
- clamping all computed values to `0..100`,
- tilt movement validation against theoretical maximum,
- exception-safe persistence and fallback behavior,
- queue cleanup on interruption.

Theoretical max validation:

$$
\text{max\_underlying\_for\_full\_tilt} = \frac{100}{\text{underlying\_to\_tilt\_ratio}}
$$

If computed requirement exceeds the maximum, it is logged as critical and clamped.

## 11) Configuration Parameters

- `travel_time` (5–120)
- `slat_rotation_time` (1–10)

These values define work-distribution ratios and affect:
- sensitivity of tilt progress,
- sensitivity of travel progress,
- where tilt-to-travel phase transition happens.

## 12) Services and Features

Supported cover services include:
- open / close / stop,
- set cover position,
- open tilt / close tilt / stop tilt,
- set cover tilt position.

## 13) Internationalization

Translations are provided in:
- English (`en`),
- Czech (`cs`),
- German (`de`),
- French (`fr`).

## 14) Debugging Notes

Recommended debug logger:

```yaml
logger:
  logs:
    custom_components.tilting_cover: debug
```

Useful diagnostics:
- baseline values,
- underlying movement deltas,
- stage transitions,
- queue state transitions,
- storage load/save outcomes.

## 15) Status

Implemented in codebase:
- decoupled architecture,
- independent tracking,
- two-stage command handling,
- external movement detection,
- direction change handling,
- persistent storage with timestamping,
- HACS-compatible integration structure,
- multilingual config flow.
