# Tilting Cover Algorithm Documentation

This document describes the internal logic and algorithms used by the Tilting Cover integration to calculate cover positions, tilt angles, and manage movement states.

## Overview

The Tilting Cover integration **enhances basic cover entities** that only support open/close operations by adding **tilt functionality**. It transforms simple covers into sophisticated blind controllers with position and tilt control.

### Why This Integration is Needed

**Problem**: Many motorized blinds and covers provide only basic open/close functionality through their underlying entities:
- Basic covers report only: `STATE_OPENING`, `STATE_CLOSING`, `STATE_OPEN`, `STATE_CLOSED`
- No tilt control: Cannot adjust slat orientation independently  
- Limited positioning: Only full open or full close, no intermediate positions
- No blind-specific behavior: Don't understand the relationship between cover position and slat tilt

**Solution**: The Tilting Cover integration:
- **Wraps** the basic cover entity as an underlying control mechanism
- **Adds** tilt functionality (0-100% slat orientation)
- **Enhances** position control with intermediate positioning
- **Models** real blind behavior: sequential slat-first movement
- **Provides** both position and tilt as independent, controllable attributes

### Entity Relationship

```
[Basic Cover Entity]           [Enhanced Tilting Cover Entity]
- open()                  →    - open() + set_cover_position()
- close()                 →    - close() + set_cover_tilt_position()
- position: 0-100%        →    - position: 0-100% (enhanced)
- No tilt control         →    - tilt: 0-100% (NEW)
- Basic state reporting   →    - Rich state attributes + tracking
```

**Key Enhancement**: The integration **interprets** the underlying entity's position changes and **distributes** them between cover movement and slat rotation based on real blind mechanics.

## Architecture Overview

The Tilting Cover integration uses a **decoupled architecture** with two independent systems:

### 1. Independent Position Tracking System
**Responsibility**: Always maintain accurate position/tilt regardless of movement source
- **Monitors**: Underlying entity state changes continuously
- **Calculates**: Position and tilt using core algorithm (Stage 1 logic)
- **Baseline**: Always uses last stored position + underlying entity changes
- **Triggers**: Movement stops, direction changes, or entity state changes
- **Direction Changes**: Treated as intermediate STOP (position storage) + START sequence
- **Storage**: Saves calculated results as basis for future calculations

### 2. Command Queue System  
**Responsibility**: Execute user commands (Stage 1/Stage 2 operations)
- **Queue Management**: Maintains ordered list of pending commands
- **External Handling**: Clears queue and injects "fake commands" for external movements
- **Decoupled**: Commands do NOT calculate positions - they only control underlying entity
- **Position Source**: Uses results from Independent Position Tracking System

**CRITICAL SEPARATION**: Position calculation is completely independent of command execution. This ensures accurate tracking regardless of movement trigger source.

## Core Concepts

### FUNDAMENTAL MOVEMENT PRINCIPLE

**CRITICAL SEQUENCE: SLATS ALWAYS ROTATE FIRST, THEN COVER MOVES**

The Tilting Cover integration models the **sequential two-phase movement behavior** of real blinds:

1. **Tilt phase FIRST**: Slat rotation occurs while cover position remains completely static
2. **Travel phase SECOND**: Cover movement begins only after slat rotation is complete

This sequence is **fundamental to blind operation** - the cover mechanism cannot move until slats are properly oriented. The algorithm enforces this sequence by prioritizing all position changes to tilt completion before any cover movement begins.

**IMPORTANT: The algorithm does NOT use internal timing**. User-configured times are used ONLY to calculate work distribution ratios between tilt and travel phases.

### Position vs Tilt
- **Cover Position** (0-100%): Physical height/position of the cover
- **Tilt Position** (0-100%): Orientation of the slats (0% = closed/no light, 100% = open/max light)

### Entity Relationship
- **Underlying Entity**: The basic cover entity being enhanced (only reports position)
- **Tilting Entity**: The enhanced entity that provides both position and tilt

### Time Configuration (For Ratio Calculation Only)

**CRITICAL**: These times are NOT used for internal timing or delays. They serve ONE PURPOSE ONLY:
**Calculate work distribution ratios between tilt and travel phases.**

- `travel_time`: Total time for complete 0→100% underlying entity cycle
- `slat_rotation_time`: Time portion dedicated to slat rotation
- `actual_travel_time`: Time portion for cover travel = `travel_time - slat_rotation_time`

**Ratio Calculation:**
```python
# These ratios determine how much tilt/travel we get from underlying entity movement
# INVERSE ratios - how efficient each phase is
underlying_to_tilt_ratio = travel_time / slat_rotation_time    # How much tilt per underlying %
underlying_to_travel_ratio = travel_time / actual_travel_time  # How much travel per underlying %

# Phase allocation ratios - what % of underlying movement each phase needs
tilt_phase_ratio = slat_rotation_time / travel_time           # % of underlying needed for tilt
travel_phase_ratio = actual_travel_time / travel_time         # % of underlying needed for travel
```

**Example:**
- `travel_time`: 20s
- `slat_rotation_time`: 3s  
- `actual_travel_time`: 17s
- **Efficiency**: 1% underlying movement → 6.67% tilt progress (20/3)
- **Efficiency**: 1% underlying movement → 1.18% travel progress (20/17)
- **Allocation**: 15% underlying movement completes 100% tilt (3/20)
- **Allocation**: 85% underlying movement completes 100% travel (17/20)

**The algorithm then uses these ratios for position-based calculations - NO timing occurs.**

## Independent Position Tracking System

### Continuous Monitoring Strategy

**FUNDAMENTAL PRINCIPLE**: Position tracking runs independently and continuously, regardless of command source.

```python
# Position tracking state (persistent baseline)
_last_stored_position           # Tilting entity position from last storage event
_last_stored_tilt              # Tilt position from last storage event  
_last_stored_underlying_position # Underlying entity position from last storage event
_last_storage_timestamp        # When positions were last stored

# Current tracking state (runtime)
_current_cover_position        # Current calculated tilting entity position
_current_tilt_position        # Current calculated tilt position
_underlying_cover_position    # Current underlying entity position (from state changes)

# Movement detection
_underlying_state             # Current underlying entity state
_previous_underlying_state    # Previous state for change detection
_is_movement_detected         # Movement currently in progress
_movement_direction          # Detected movement direction
```

### Core Position Calculation Algorithm

**ALWAYS uses this algorithm regardless of movement source (commands, external, etc.)**

```python
async def _calculate_position_from_underlying_change(self):
    """Core algorithm - calculate position/tilt from underlying entity changes."""
    
    # Get baseline positions (last stored state) 
    baseline_position = self._last_stored_position or 0
    baseline_tilt = self._last_stored_tilt or 0
    baseline_underlying = self._last_stored_underlying_position or 0
    
    # Get current underlying position
    current_underlying = self._underlying_cover_position
    if current_underlying is None:
        return  # Cannot calculate without underlying position
    
    # Calculate underlying movement difference
    underlying_diff = abs(current_underlying - baseline_underlying)
    
    # Determine movement direction and natural tilt target
    if current_underlying > baseline_underlying:
        # Opening movement - natural tilt goes toward 100%
        direction = "opening"
        natural_target_tilt = 100
    elif current_underlying < baseline_underlying:
        # Closing movement - natural tilt goes toward 0%
        direction = "closing" 
        natural_target_tilt = 0
    else:
        # No underlying movement
        return
    
    # Calculate work ratios (from time configuration)
    total_time = self._travel_time
    tilt_time = self._slat_rotation_time
    actual_travel_time = max(total_time - tilt_time, 0.1)
    
    underlying_to_tilt_ratio = total_time / tilt_time if tilt_time > 0 else 1.0
    underlying_to_travel_ratio = total_time / actual_travel_time if actual_travel_time > 0 else 1.0
    
    # Calculate required tilt change
    total_tilt_change = abs(natural_target_tilt - baseline_tilt)
    
    # CORE SEQUENTIAL ALGORITHM: Tilt first, then travel
    # CRITICAL: This enforces the fundamental blind behavior
    if total_tilt_change > 0:
        underlying_needed_for_tilt = total_tilt_change / underlying_to_tilt_ratio
        
        if underlying_diff <= underlying_needed_for_tilt:
            # Phase 1: ALL underlying movement converts to tilt - cover CANNOT move yet
            tilt_progress = underlying_diff * underlying_to_tilt_ratio
            travel_progress = 0  # Cover stays at baseline position
        else:
            # Phase 2: Tilt complete - remaining underlying converts to travel
            tilt_progress = total_tilt_change  # Slats locked in final position
            remaining_underlying = underlying_diff - underlying_needed_for_tilt
            travel_progress = remaining_underlying * underlying_to_travel_ratio
    else:
        # No tilt change needed - all goes to travel
        tilt_progress = 0
        travel_progress = underlying_diff * underlying_to_travel_ratio
    
    # Apply progress from baseline positions
    if direction == "opening":
        self._current_tilt_position = baseline_tilt + tilt_progress
        self._current_cover_position = baseline_position + travel_progress
    else:  # closing
        self._current_tilt_position = baseline_tilt - tilt_progress
        self._current_cover_position = baseline_position - travel_progress
    
    # Clamp to valid ranges
    self._current_cover_position = max(0, min(100, self._current_cover_position))
    self._current_tilt_position = max(0, min(100, self._current_tilt_position))
```

### Independent Monitoring Loop

**Continuously monitors underlying entity regardless of command activity**

```python
async def _monitor_underlying_entity(self, new_state: State, old_state: State | None):
    """Independent monitoring - runs for ALL underlying entity changes."""
    
    # Update underlying position if available
    position_attr = new_state.attributes.get(ATTR_POSITION)
    if position_attr is not None:
        self._underlying_cover_position = int(position_attr)
        
        # Calculate position/tilt from underlying change (ALWAYS)
        await self._calculate_position_from_underlying_change()
    
    # Update underlying state tracking
    self._previous_underlying_state = self._underlying_state
    self._underlying_state = new_state.state
    
    # Handle movement detection and storage triggers
    if new_state.state in (STATE_OPENING, STATE_CLOSING):
        await self._handle_movement_start_detected(new_state.state)
    elif new_state.state in (STATE_OPEN, STATE_CLOSED):
        await self._handle_movement_stop_detected(new_state.state)
    
    # Update HA state with calculated positions
    self.async_write_ha_state()
```

### Storage Trigger Points

**Storage happens independently when movement events occur**

```python
async def _handle_movement_stop_detected(self, final_state: str):
    """Independent storage when movement stops - regardless of source."""
    
    # Apply definitive state corrections if needed
    if final_state == STATE_OPEN:
        self._current_cover_position = 100
        self._current_tilt_position = 100
    elif final_state == STATE_CLOSED:
        self._current_cover_position = 0
        self._current_tilt_position = 0
    
    # Store calculated positions as new baseline
    await self._store_current_positions_as_baseline()
    
    # Clear movement detection flags
    self._is_movement_detected = False
    self._movement_direction = None
    
    # Handle command queue (external movement clears queue)
    if not self._was_movement_commanded():
        # External movement detected - clear command queue
        self._command_queue.clear()
        _LOGGER.debug("External movement detected - command queue cleared")
    
    _LOGGER.debug("Position tracking: movement stopped, positions stored as baseline")

async def _store_current_positions_as_baseline(self):
    """Store current calculated positions as baseline for future calculations."""
    
    # Update baseline positions
    self._last_stored_position = self._current_cover_position
    self._last_stored_tilt = self._current_tilt_position
    self._last_stored_underlying_position = self._underlying_cover_position
    self._last_storage_timestamp = datetime.now(timezone.utc)
    
    # Persist to storage
    await self._save_current_state()
    
    _LOGGER.debug("Stored new baseline: pos=%s%%, tilt=%s%%, underlying=%s%%",
                  self._last_stored_position, self._last_stored_tilt, self._last_stored_underlying_position)
```

**Movement Scenario (Opening) - Position-Based Calculation:**
- Start: position 20%, tilt 30%
- Underlying entity moves: 45% → 67% (22% movement)
- Algorithm applies work ratios and slats-first principle
- Result: Calculated position/tilt using core algorithm
- End: Independent storage when underlying entity stops
- Target: position 100%, tilt 100%
- Required tilt change: 70%
- **Ratios**: underlying_to_tilt = 6.67, underlying_to_travel = 1.18
- **Phase allocation**: 15% underlying for tilt, 85% for travel

**Progress Tracking (Opening Example):**

**Notice: Cover position STAYS AT 20% until tilt work allocation is completed!**

| Underlying Progress | Underlying Diff | Tilt Calculation | Travel Calculation | Result Position | Result Tilt | Phase |
|---------------------|------------------|------------------|-------------------|-----------------|-------------|-------|
| 20% → 25% | 5% | 5% × 6.67 = 33.35% tilt progress | 0% (**tilt not complete**) | **20%** | 30% + 33.35% = **63.35%** | TILT ONLY |
| 20% → 30% | 10% | 10% × 6.67 = 66.7% tilt progress | 0% (**tilt not complete**) | **20%** | 30% + 66.7% = **96.7%** | TILT ONLY |
| 20% → 32% | 12% | Need 70% ÷ 6.67 = 10.5% underlying<br>10.5% × 6.67 = 70% tilt progress | 0% (**tilt just completed**) | **20%** | 30% + 70% = **100%** | TILT DONE |
| 20% → 40% | 20% | ✓ **First 10.5% completes tilt**<br>Remaining 9.5% for travel | 9.5% × 1.18 = 11.2% | 20% + 11.2% = **31.2%** | **100%** | TRAVEL |

**Key Mathematical Observations:**
- **Baseline**: Starting position=20%, tilt=30% 
- **10.5% underlying movement** completes 70% tilt change (70 ÷ 6.67 efficiency)
- **Any underlying diff ≤ 10.5%** converts entirely to tilt progress at 6.67× efficiency
- **CRITICAL**: Cover position CANNOT change until tilt work is satisfied
- **Step 4**: After 10.5% threshold, remaining 9.5% converts to travel at 1.18× efficiency  
**This demonstrates the mandatory slats-first sequence in pure position mathematics.**

## Command Queue System

### Queue Management

**Commands are queued and executed independently of position tracking**

```python
# Command queue state
_command_queue = []           # List of pending commands
_current_command = None       # Currently executing command
_command_in_progress = False  # Command execution flag

# Command types
class Command:
    def __init__(self, type, target_position=None, target_tilt=None, stage=None):
        self.type = type              # "position_tilt", "position_only", "tilt_only", "external_fake"
        self.target_position = target_position
        self.target_tilt = target_tilt  
        self.stage = stage            # "stage_1", "stage_2"
        self.timestamp = datetime.now()
```

### Command Execution (Decoupled from Position Calculation)

```python
async def async_set_cover_position(self, **kwargs):
    """Queue position command - does NOT calculate positions."""
    
    position = kwargs.get(ATTR_POSITION)
    tilt = kwargs.get(ATTR_TILT_POSITION)
    
    # Clear any pending commands and add new command to queue
    self._command_queue.clear()
    
    if position is not None and tilt is not None:
        # Position + tilt: requires two-stage operation
        current_pos = self._current_cover_position or 0
        current_tilt = self._current_tilt_position or 0
        
        if abs(position - current_pos) > 1 or abs(tilt - current_tilt) > 1:
            # Add Stage 1 command
            self._command_queue.append(Command(
                type="position_tilt_stage1",
                target_position=position,
                target_tilt=tilt,
                stage="stage_1"
            ))
            # Add Stage 2 command  
            self._command_queue.append(Command(
                type="position_tilt_stage2", 
                target_position=position,
                target_tilt=tilt,
                stage="stage_2"
            ))
    
    elif position is not None:
        # Position only: preserve current tilt
        target_tilt = self._current_tilt_position or 50
        # Add two-stage commands to restore tilt
        self._command_queue.append(Command(
            type="position_only_stage1",
            target_position=position,
            target_tilt=target_tilt,
            stage="stage_1"
        ))
        self._command_queue.append(Command(
            type="position_only_stage2",
            target_position=position, 
            target_tilt=target_tilt,
            stage="stage_2"
        ))
    
    # Start command execution
    await self._process_command_queue()

async def async_set_cover_tilt_position(self, **kwargs):
    """Queue tilt-only command."""
    
    tilt = kwargs.get(ATTR_TILT_POSITION)
    if tilt is None:
        return
    
    # Clear queue and add tilt-only command (Stage 2 directly)
    self._command_queue.clear()
    self._command_queue.append(Command(
        type="tilt_only",
        target_tilt=tilt,
        stage="stage_2"
    ))
    
    await self._process_command_queue()
```

### External Movement Handling

**External movements clear queue and inject fake commands**
**Direction changes are treated as STOP + START with position storage**

```python
async def _handle_movement_start_detected(self, movement_direction: str):
    """Handle movement start - inject fake command if external."""
    
    # Check for direction change - treat as intermediate stop + new start
    if self._is_movement_detected and self._movement_direction != movement_direction:
        _LOGGER.debug("Direction change detected: %s -> %s - performing intermediate stop+start", 
                      self._movement_direction, movement_direction)
        
        # First perform intermediate stop with position storage
        await self._handle_movement_stop_intermediate()
        
        # Position has been saved, now continue with new movement start
    
    self._is_movement_detected = True 
    self._movement_direction = movement_direction
    
    # Check if this movement was commanded
    if not self._was_movement_commanded():
        # External movement detected
        _LOGGER.debug("External movement detected: %s - clearing queue", movement_direction)
        
        # Clear command queue
        self._command_queue.clear()
        self._current_command = None
        self._command_in_progress = False
        
        # Inject fake command representing external movement
        if movement_direction == STATE_OPENING:
            fake_command = Command(
                type="external_fake",
                target_position=100,
                target_tilt=100,
                stage="external"
            )
        else:  # STATE_CLOSING
            fake_command = Command(
                type="external_fake", 
                target_position=0,
                target_tilt=0,
                stage="external"
            )
        
        self._current_command = fake_command
        _LOGGER.debug("Fake command injected: %s -> pos=%s%%, tilt=%s%%", 
                      movement_direction, fake_command.target_position, fake_command.target_tilt)

async def _handle_movement_stop_intermediate(self):
    """Handle intermediate stop during direction changes."""
    
    # Calculate current position/tilt based on progress so far
    await self._calculate_position_from_underlying_change()
    
    # Store positions as baseline
    await self._store_current_positions_as_baseline()
    
    # Clear current movement flags
    self._is_movement_detected = False
    self._movement_direction = None
    
    _LOGGER.debug("Intermediate stop completed: pos=%s%%, tilt=%s%% - stored as baseline",
                  self._current_cover_position, self._current_tilt_position)

def _was_movement_commanded(self) -> bool:
    """Check if current movement was triggered by a queued command."""
    return (self._command_in_progress and 
            self._current_command is not None and
            self._current_command.type != "external_fake")

async def async_stop_cover(self, **kwargs):
    """Stop command - clear queue and stop underlying entity."""
    
    # Clear command queue
    self._command_queue.clear()
    self._current_command = None
    self._command_in_progress = False
    
    # Stop underlying entity
    await self.hass.services.async_call(
        "cover", "stop_cover", {"entity_id": self._cover_entity_id}
    )
    
    _LOGGER.debug("Stop command: queue cleared, underlying entity stopped")
```

## Two-Stage Command Execution (Decoupled)

### Stage 1: Position Movement Command

**Commands underlying entity - position tracking calculates results independently**

```python
async def _execute_stage_1_command(self, command: Command):
    """Execute Stage 1 command - does NOT calculate positions."""
    
    # Get current positions from independent tracking system
    current_position = self._current_cover_position or 0
    current_tilt = self._current_tilt_position or 0
    
    # Calculate underlying movement needed
    position_diff = command.target_position - current_position
    
    # Calculate natural tilt target based on movement direction
    if position_diff > 0:  # Opening
        natural_target_tilt = 100
    elif position_diff < 0:  # Closing
        natural_target_tilt = 0
    else:
        natural_target_tilt = current_tilt
    
    natural_tilt_diff = natural_target_tilt - current_tilt
    
    # Calculate required underlying movement
    underlying_to_tilt_ratio = self._travel_time / self._slat_rotation_time if self._slat_rotation_time > 0 else 1.0
    
    underlying_needed_for_position = abs(position_diff)
    underlying_needed_for_tilt = abs(natural_tilt_diff) / underlying_to_tilt_ratio if abs(natural_tilt_diff) > 0 else 0
    total_underlying_movement = underlying_needed_for_position + underlying_needed_for_tilt
    
    # Calculate target underlying position
    baseline_underlying = self._last_stored_underlying_position or 0
    if position_diff > 0:  # Opening
        target_underlying = baseline_underlying + total_underlying_movement
    else:  # Closing
        target_underlying = baseline_underlying - total_underlying_movement
    
    target_underlying = max(0, min(100, target_underlying))
    
    # Command underlying entity (position tracking will calculate results)
    self._command_in_progress = True
    await self.hass.services.async_call(
        "cover", "set_cover_position",
        {"entity_id": self._cover_entity_id, "position": target_underlying}
    )
    
    _LOGGER.debug("Stage 1 command executed: underlying target=%s%% (position tracking will calculate results)",
                  target_underlying)

async def _execute_stage_2_command(self, command: Command):
    """Execute Stage 2 command - tilt adjustment only."""
    
    # Get current tilt from independent tracking system
    current_tilt = self._current_tilt_position or 0
    tilt_diff = command.target_tilt - current_tilt
    
    if abs(tilt_diff) <= 2:  # 2% tolerance
        _LOGGER.debug("Stage 2 skipped: tilt already at target (%s%%)", current_tilt)
        return
    
    # Calculate underlying movement needed for tilt adjustment
    underlying_to_tilt_ratio = self._travel_time / self._slat_rotation_time if self._slat_rotation_time > 0 else 1.0
    underlying_needed = abs(tilt_diff) / underlying_to_tilt_ratio
    
    baseline_underlying = self._last_stored_underlying_position or 0
    if tilt_diff > 0:  # Need more tilt
        target_underlying = baseline_underlying + underlying_needed
    else:  # Need less tilt  
        target_underlying = baseline_underlying - underlying_needed
    
    target_underlying = max(0, min(100, target_underlying))
    
    # Command underlying entity (position tracking will calculate results)
    self._command_in_progress = True
    await self.hass.services.async_call(
        "cover", "set_cover_position",
        {"entity_id": self._cover_entity_id, "position": target_underlying}
    )
    
    _LOGGER.debug("Stage 2 command executed: underlying target=%s%% (position tracking will calculate results)",
                  target_underlying)
```

### Stage 1: Position Movement with Integrated Tilt Handling

**Goal**: Move cover to target position while handling directional slat rotation during travel

1. **Calculate Required Movement**:
   ```python
   current_position = self._current_cover_position or 0
   current_tilt = self._current_tilt_position or 0
   
   position_diff = target_position - current_position
   
   # Calculate natural tilt change based on movement direction
   if position_diff > 0:  # Opening movement
       # During opening, slats naturally tilt toward open (100%)
       natural_target_tilt = 100
   elif position_diff < 0:  # Closing movement  
       # During closing, slats naturally tilt toward closed (0%)
       natural_target_tilt = 0
   else:
       # No position movement - natural tilt stays current
       natural_target_tilt = current_tilt
   
   # Calculate natural tilt change during position movement
   natural_tilt_diff = natural_target_tilt - current_tilt
   
   # Calculate how much underlying movement needed
   underlying_needed_for_position = abs(position_diff)
   
   # Additional underlying movement for natural tilt change
   if abs(natural_tilt_diff) > 0:
       underlying_needed_for_tilt = abs(natural_tilt_diff) / underlying_to_tilt_ratio
       total_underlying_movement = underlying_needed_for_position + underlying_needed_for_tilt
   else:
       total_underlying_movement = underlying_needed_for_position
   
   # Calculate target underlying position for Stage 1
   baseline_underlying = self._last_stopped_underlying_position or 0
   if position_diff > 0:  # Opening
       target_underlying_stage1 = baseline_underlying + total_underlying_movement
   else:  # Closing  
       target_underlying_stage1 = baseline_underlying - total_underlying_movement
   
   target_underlying_stage1 = max(0, min(100, target_underlying_stage1))
   ```

2. **Start Movement**:
   ```python
   # Command underlying entity to move to calculated position
   await self.hass.services.async_call(
       "cover", "set_cover_position", 
       {"entity_id": self._cover_entity_id, "position": target_underlying_stage1}
   )
   
   # Set movement tracking flags
   self._is_two_stage_operation = True
   self._stage_1_active = True
   self._stage_1_target_position = target_position
   self._stage_1_natural_target_tilt = natural_target_tilt  # Natural tilt after position movement
   self._user_requested_tilt = target_tilt  # User's actual desired tilt
   ```

3. **Wait for STOP State and Store**:
   - Monitor underlying entity state changes
   - When underlying entity stops (STATE_OPEN or STATE_CLOSED), Stage 1 is complete
   - Calculate achieved position and natural tilt based on underlying movement
   - **CRITICAL**: Store achieved state to persistent storage immediately:
   ```python
   # Calculate final achieved state from underlying movement
   achieved_position, achieved_natural_tilt = self._calculate_movement_result()
   
   # Update current state
   self._current_cover_position = achieved_position
   self._current_tilt_position = achieved_natural_tilt
   
   # Store to persistent storage BEFORE starting Stage 2
   await self._save_current_state()
   
   # Clear Stage 1 flags
   self._stage_1_active = False
   
   _LOGGER.debug("Stage 1 complete: pos=%s%%, tilt=%s%% - SAVED to storage", 
                 achieved_position, achieved_natural_tilt)
   ```
   - **Stage 1 Result**: Position at target, tilt at natural directional value, **STATE SAVED**

### Stage 2: Independent Tilt Fine-Tuning

**Goal**: Adjust slat rotation to user's requested tilt position (works independently)

**Stage 2 can be triggered by:**
- **After Stage 1**: Fine-tune from natural directional tilt to user's requested tilt
- **Tilt-Only Request**: Direct tilt change without position movement
- **Recovery**: After restart, if persistent storage shows incomplete tilt target

1. **Load Current State and Evaluate**:
   ```python
   # Load current state from persistent storage (Stage 2 is independent)
   await self._load_stored_state()
   current_position = self._current_cover_position or 0
   current_tilt = self._current_tilt_position or 0
   
   # Get target tilt (from Stage 1 continuation OR direct tilt request)
   if self._is_two_stage_operation:
       # Continuing from Stage 1
       user_requested_tilt = self._user_requested_tilt
   else:
       # Direct tilt-only request
       user_requested_tilt = target_tilt  # From service call parameter
   
   # Calculate tilt difference
   remaining_tilt_diff = user_requested_tilt - current_tilt
   
   # Only proceed if significant tilt adjustment needed
   if abs(remaining_tilt_diff) > 2:  # 2% tolerance
       # Calculate underlying movement needed for precise tilt adjustment
       underlying_needed_for_tilt_adjustment = abs(remaining_tilt_diff) / underlying_to_tilt_ratio
       
   baseline_underlying = self._last_stopped_underlying_position or 0
   if remaining_tilt_diff > 0:  # Need more tilt (toward 100%)
       target_underlying_stage2 = baseline_underlying + underlying_needed_for_tilt_adjustment
   else:  # Need less tilt (toward 0%)
       target_underlying_stage2 = baseline_underlying - underlying_needed_for_tilt_adjustment
       # Tilt is accurate enough - skip Stage 2
       target_underlying_stage2 = None
   ```

2. **Start Independent Tilt Adjustment**:
   ```python
   if target_underlying_stage2 is not None:
       # Command underlying entity for tilt adjustment
       await self.hass.services.async_call(
           "cover", "set_cover_position", 
           {"entity_id": self._cover_entity_id, "position": target_underlying_stage2}
       )
       
       # Set independent Stage 2 tracking flags
       self._stage_1_active = False  # Always false in Stage 2
       self._stage_2_active = True
       self._stage_2_target_tilt = user_requested_tilt
       self._stage_2_start_position = current_position  # Should remain constant
       
       _LOGGER.debug("Stage 2 started: tilt %s%% -> %s%%, position locked at %s%%",
                     current_tilt, user_requested_tilt, current_position)
   else:
       # No adjustment needed - operation complete
       self._complete_two_stage_operation()
   ```

3. **Final STOP and Independent Storage**:
   ```python
   # When underlying entity stops, Stage 2 is complete
   final_position, final_tilt = self._calculate_movement_result()
   
   # Position should remain constant in Stage 2 (validate)
   if abs(final_position - self._stage_2_start_position) > 3:  # 3% tolerance
       _LOGGER.warning("Stage 2 position drift: %s%% -> %s%%", 
                       self._stage_2_start_position, final_position)
       # Use locked position, not calculated position
       final_position = self._stage_2_start_position
   
   # Update and store final state
   self._current_cover_position = final_position
   self._current_tilt_position = final_tilt
   
   # INDEPENDENT STORAGE - Stage 2 saves final state
   await self._save_current_state()
   
   # Clear all tracking flags
   self._complete_two_stage_operation()
   
   _LOGGER.debug("Stage 2 complete: final_tilt=%s%% - SAVED to storage", final_tilt)
   ```

## Error Handling in Decoupled System

### Position Tracking Errors
- **No underlying position**: Independent system continues with last known baseline
- **Invalid position values**: Clamped to 0-100% range with warning logged
- **Storage failures**: Position tracking continues, storage retried on next stop event
- **Calculation errors**: Fallback to underlying position directly

### Tilt Movement Validation Safeguard
- **Theoretical Maximum Check**: All tilt calculations are validated against theoretical maximum
- **Maximum Calculation**: `max_underlying_for_full_tilt = 100 / underlying_to_tilt_ratio`
- **Safety Validation**: Any calculated tilt movement > theoretical maximum triggers critical error
- **Error Recovery**: Invalid calculations are clamped to maximum to prevent system damage
- **Logging**: Critical errors logged with full context (ratios, times, calculations) for debugging

**Implementation Example**:
```python
# Calculate theoretical maximum for safety validation
max_underlying_for_full_tilt = 100 / underlying_to_tilt_ratio

# Validate tilt calculation doesn't exceed physics
if underlying_needed_for_tilt > max_underlying_for_full_tilt:
    _LOGGER.error("CRITICAL ERROR - Tilt calculation exceeds maximum!")
    # Clamp to maximum to prevent invalid calculations
    underlying_needed_for_tilt = min(underlying_needed_for_tilt, max_underlying_for_full_tilt)
```

**Rationale**: This safeguard prevents algorithmic errors that could request impossible tilt movements. Since the entire theoretical range should be usable (no tolerance), any calculation exceeding the maximum indicates a bug in the algorithm logic that must be caught and corrected.

### Command Queue Errors  
- **Underlying entity unavailable**: Commands remain queued until entity available
- **Movement timeout**: Command marked failed, queue continues with next command
- **External interruption**: Queue cleared, fake command injected automatically
- **Invalid command parameters**: Command skipped with warning, queue continues

### Recovery Mechanisms
- **Independent tracking**: Continues regardless of command system state
- **Queue cleanup**: External movements and stops clear conflicting commands
- **Baseline restoration**: Positions calculated from last reliable stored state
- **State synchronization**: Definitive positions (0%, 100%) trigger corrections

## Configuration Impact

**Time configuration affects ONLY the calculation ratios - not command timing**

### Work Distribution Effects
- **High `slat_rotation_time`**: More underlying movement allocated to tilt progress
- **Low `slat_rotation_time`**: More underlying movement allocated to position progress
- **Balanced ratios**: Even distribution between tilt and position changes

### Recommended Configuration

```python
# Fast tilt adjustment (modern blinds) - matches examples throughout document
travel_time = 20.0
slat_rotation_time = 3.0  # 15% allocation to tilt (3/20)

# Slow tilt adjustment (traditional blinds)  
travel_time = 20.0
slat_rotation_time = 8.0  # 40% allocation to tilt (8/20)

# Balanced operation
travel_time = 20.0
slat_rotation_time = 5.0  # 25% allocation to tilt (5/20)
```

## Debugging and Monitoring

### Position Tracking Logs
```
[Position Tracking] Underlying change detected: 45% -> 67% (diff=22%)
[Position Tracking] Calculation: baseline(pos=30%, tilt=60%) + progress(pos=8%, tilt=14%) = result(pos=38%, tilt=74%)
[Position Tracking] Movement stopped: storing baseline pos=38%, tilt=74%, underlying=67%
```

### Command Queue Logs
```
[Command Queue] Added: position_tilt_stage1 (target: pos=80%, tilt=45%)
[Command Queue] Added: position_tilt_stage2 (target: pos=80%, tilt=45%)
[Command Queue] Executing: position_tilt_stage1 -> underlying target=73%
[Command Queue] External movement detected - clearing queue
[Command Queue] Injected fake command: external_opening -> pos=100%, tilt=100%
```

## Architecture Benefits Summary

### Reliability
- **Position accuracy**: Always calculated from reliable baseline using proven algorithm
- **External movement handling**: Identical treatment regardless of movement source
- **State consistency**: Atomic storage ensures position/tilt always match
- **Error resilience**: Independent systems continue operating if one fails

### Maintainability  
- **Separation of concerns**: Position calculation separate from command execution
- **Clear interfaces**: Well-defined boundaries between tracking and command systems
- **Testability**: Each system can be tested independently
- **Extensibility**: Easy to add new command types or tracking features

### User Experience
- **Consistent behavior**: Same response whether movement is internal or external
- **Predictable results**: Position always calculated using same reliable algorithm
- **Robust operation**: System continues working despite various error conditions
- **Real-time feedback**: Positions updated immediately as underlying entity moves

## Algorithm Summary

The **Decoupled Architecture** provides:

### Independent Position Tracking
- **Core Algorithm**: Always uses Stage 1 calculation logic for position/tilt tracking
- **Baseline Reference**: Last stored positions provide reliable calculation foundation  
- **Continuous Monitoring**: Tracks all underlying entity changes, regardless of source
- **Atomic Storage**: Positions stored together when movement stops, ensuring consistency

### Command Queue Management
- **Queue Processing**: Commands executed in order with independent position tracking
- **External Integration**: External movements clear queue and inject fake commands
- **Error Recovery**: Queue cleanup and timeout handling maintain system reliability
- **Decoupled Control**: Commands control underlying entity, tracking calculates positions

This architecture ensures **reliable position accuracy** and **robust operation** regardless of movement trigger source.

## Movement Flow Diagram

**SLATS-FIRST POSITION-BASED FLOW (NO TIMING OPERATIONS)**

```
[Movement Start] → [Get Underlying Position Diff] → [SLAT WORK FIRST?]
                                                              ↓
                    [Tilt Work Incomplete] ←────────────────┘
                           ↓                         ↑ Tilt Work Complete
                    [ALL to Tilt Progress]       [Remainder to Cover Travel]
                    [Cover STAYS STATIC]         [Slats LOCKED in Position]
                      (position unchanged)        (tilt unchanged)
                           ↓                              ↓
                    [Update Tilt Only]           [Update Position Only]  
                           ↓                              ↓
                    [Check Movement End] → [Movement Stop] → [Save State]
```

**Why This Slats-First Sequence Matters:**

**Real-world blind mechanics translated to math:**
- **Slat work allocation happens first** - This is not configurable behavior
- **Cover travel allocation happens second** - Only after slat work is satisfied
- **Cover position mathematically CANNOT change** until tilt work threshold is met
- **The underlying entity may report 50% progress, but if tilt needs 60% work allocation, ALL 50% gets assigned to tilt and cover position remains unchanged**
- **Only EXCESS underlying progress beyond tilt work requirements gets assigned to cover travel**
- **Manual blinds exhibit this** - adjust slats fully, then pull cord

**Algorithm enforcement through work allocation:**
- Position changes are **always** calculated for tilt satisfaction first
- Cover movement calculation **cannot** begin until `tilt_work_satisfied = true`
- **Work ratios determine how much underlying progress is "consumed" by tilt work**
- **Configuration impact**: High `slat_rotation_time` = More underlying progress needed for tilt = Cover stays motionless longer