# Click-to-Measure Mode - Plan 2 (Simplified)

## Problem Statement
Current measurement workflow is clunky:
- Draw line -> see measurement -> click "Add Segment" -> repeat
- Too many steps for each wall
- Easy to lose track of what's measured
- No way to account for doors (unpainted areas)

## Goal
**Streamlined click-to-click measurement mode + door tracking:**
1. Calibrate once (existing feature works fine)
2. Enter "Measure Mode" → click-to-click walls
3. Enter "Door Finder" → click-to-click doors (stored separately)
4. Toggle "Minus Doors" → sqft calculation excludes door areas
5. Get accurate paintable sqft

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      MEASUREMENT WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. CALIBRATE (existing)                                        │
│     Draw line over known dimension → set scale                  │
│                                                                  │
│  2. MEASURE MODE (walls)                                        │
│     Click → Click → Click... → ESC                              │
│     Result: Wall segments list + total linear ft                │
│                                                                  │
│  3. DOOR FINDER (doors)                                         │
│     Click → Click → Click... → ESC                              │
│     Result: Door count + door widths stored internally          │
│                                                                  │
│  4. CALCULATE                                                   │
│     Wall Height × Total Wall Linear Ft = Gross Sqft             │
│                                                                  │
│     IF "Minus Doors" ON:                                        │
│        Door Height (default 6'8") × Total Door Width = Door Sqft│
│        Net Sqft = Gross Sqft - Door Sqft                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Toolbar:                                                         │
│ [Ruler] [Calibrate] [📐 Measure Mode] [🚪 Door Finder]          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                        PDF Canvas                                │
│         (walls = blue lines, doors = orange lines)              │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Tools Panel:                                                     │
│ ┌─────────────────────────────────────────┐                     │
│ │ Wall Sqft                               │                     │
│ │ Wall height: [8ft    ] [ft ▼]           │                     │
│ │                                         │                     │
│ │ Total linear: 47.5 ft (12 segments)     │                     │
│ │ Gross area: 380.0 sqft                  │                     │
│ │                                         │                     │
│ │ ☑ Minus Doors                           │                     │
│ │ Door height: [6'8"   ] [ft ▼]           │                     │
│ │ Doors: 4 (total width: 12.0 ft)         │                     │
│ │ Door area: -80.0 sqft                   │                     │
│ │                                         │                     │
│ │ ═══════════════════════════════════     │                     │
│ │ NET PAINTABLE: 300.0 sqft               │                     │
│ └─────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

## Current vs Proposed UX

### Current (5+ actions per wall)
```
1. Select Ruler tool
2. Click and drag to draw line
3. Release mouse
4. Read measurement
5. Click "Add Segment" button
6. Repeat...
(No door accounting at all)
```

### Proposed (2 clicks per wall/door)
```
1. Click "Measure Mode" (once)
2. Click-click-click walls → ESC
3. Click "Door Finder" (once)  
4. Click-click doors → ESC
5. Check "Minus Doors" → see net sqft
```

## Data Model

```python
# Walls (existing _segments list)
_segments: list[Segment]  # Each has length_pdf_inches

# Doors (NEW)
_doors: list[Door]  # NEW dataclass
@dataclass
class Door:
    page_index: int
    x0_pt: float
    y0_pt: float
    x1_pt: float
    y1_pt: float
    width_pdf_inches: float  # horizontal span

# Settings
_minus_doors: BooleanVar  # Toggle checkbox
_door_height_entry: Entry  # Default "6'8""
```

## Implementation

### Phase 1: Core Measure Mode (Walls)
- [ ] Add `_measure_mode` boolean state
- [ ] Add `_measure_start` point tracker
- [ ] Add "Measure Mode" toggle button
- [ ] Click handler: first click sets start, second click creates segment
- [ ] Chain mode: new segment starts where last ended
- [ ] ESC exits mode
- [ ] Blue lines + dots for walls
- [ ] Status: "Measure Mode: X segments, Y ft"

### Phase 2: Door Finder Mode
- [ ] Add `_door_mode` boolean state  
- [ ] Add `_doors: list[Door]` storage
- [ ] Add `Door` dataclass (similar to Segment)
- [ ] Add "Door Finder" toggle button
- [ ] Same click-to-click behavior as measure mode
- [ ] Orange lines + dots for doors (visually distinct)
- [ ] Status: "Door Finder: X doors marked"
- [ ] Door list in panel showing count + total width

### Phase 3: Minus Doors Calculation
- [ ] Add `_minus_doors` checkbox to panel
- [ ] Add `_door_height_entry` field (default "6'8"")
- [ ] Modify `_update_totals()` to calculate:
  ```
  gross_sqft = wall_linear_ft × wall_height_ft
  door_sqft = total_door_width_ft × door_height_ft
  net_sqft = gross_sqft - door_sqft (if minus_doors checked)
  ```
- [ ] Display door count, total door width, door sqft deduction
- [ ] Display NET PAINTABLE sqft prominently

### Phase 4: Visual Polish
- [ ] Persistent dots at click points (green=wall, orange=door)
- [ ] Length labels on segments
- [ ] Different colors: walls=blue, doors=orange
- [ ] "Done" button when in either mode
- [ ] Clear Doors button (separate from Clear Walls)

### Phase 5: Convenience (Optional)
- [ ] Undo last click (Ctrl+Z)
- [ ] Snap to horizontal/vertical (Shift+click)
- [ ] Standard door width presets (2'6", 2'8", 3'0")

## Technical Details

### State Machine
```
IDLE 
  ├─[Measure Mode]──► MEASURING
  │                    ├─[Click]──► add wall point/segment
  │                    └─[ESC]────► IDLE
  │
  └─[Door Finder]───► DOOR_FINDING  
                       ├─[Click]──► add door point/segment
                       └─[ESC]────► IDLE
```

### Click Handler
```python
def _on_mouse_down(self, event):
    if self._measure_mode:
        self._handle_measure_click(event, mode="wall")
        return
    if self._door_mode:
        self._handle_measure_click(event, mode="door")
        return
    # ... existing ruler/calibrate logic

def _handle_measure_click(self, event, mode: str):
    x = self.canvas.canvasx(event.x)
    y = self.canvas.canvasy(event.y)
    
    start_var = "_measure_start" if mode == "wall" else "_door_start"
    start = getattr(self, start_var)
    
    if start is None:
        setattr(self, start_var, (x, y))
        self._draw_point_marker(x, y, color="green" if mode == "wall" else "orange")
    else:
        x0, y0 = start
        if mode == "wall":
            self._create_segment_from_points(x0, y0, x, y)
        else:
            self._create_door_from_points(x0, y0, x, y)
        setattr(self, start_var, (x, y))  # Chain
        self._draw_point_marker(x, y, color="green" if mode == "wall" else "orange")
    
    self._update_totals()
```

### Updated Totals Calculation
```python
def _update_totals(self):
    cal = self._cal_factor if self._has_cal else 1.0
    
    # Walls
    wall_inches = sum(s.length_pdf_inches * cal for s in self._segments)
    wall_ft = wall_inches / 12.0
    wall_height_ft = parse_length_to_inches(self.height_entry.get()) / 12.0
    gross_sqft = wall_ft * wall_height_ft
    
    # Doors
    door_inches = sum(d.width_pdf_inches * cal for d in self._doors)
    door_ft = door_inches / 12.0
    door_height_ft = parse_length_to_inches(self.door_height_entry.get()) / 12.0
    door_sqft = door_ft * door_height_ft
    door_count = len(self._doors)
    
    # Net
    if self._minus_doors.get():
        net_sqft = gross_sqft - door_sqft
    else:
        net_sqft = gross_sqft
    
    # Update labels
    self.total_lin_lbl.configure(text=f"Total linear: {wall_ft:.2f} ft ({len(self._segments)} segments)")
    self.gross_sqft_lbl.configure(text=f"Gross area: {gross_sqft:.2f} sqft")
    self.door_lbl.configure(text=f"Doors: {door_count} (total width: {door_ft:.2f} ft)")
    self.door_sqft_lbl.configure(text=f"Door area: -{door_sqft:.2f} sqft")
    self.net_sqft_lbl.configure(text=f"NET PAINTABLE: {net_sqft:.2f} sqft")
```

## Files to Modify

| File | Changes |
|------|---------|
| `pdf_viewer.py` | Add measure mode, door finder, minus doors logic |

## No New Dependencies
Uses existing Tkinter + PyMuPDF. No new packages needed.

## Success Criteria
- [ ] Can measure 10 walls in under 30 seconds
- [ ] Can mark 4 doors in under 15 seconds
- [ ] Door deduction shows correct sqft reduction
- [ ] Visual distinction between walls (blue) and doors (orange)
- [ ] Toggling "Minus Doors" instantly updates total
- [ ] Existing ruler/calibrate still work

## Estimated Effort
- Phase 1: ~30 min (measure mode for walls)
- Phase 2: ~25 min (door finder mode)
- Phase 3: ~15 min (minus doors calculation)
- Phase 4: ~20 min (visual polish)
- Phase 5: ~15 min (optional conveniences)

**Total: ~1.5-2 hours**

---

*Plan created: 2026-02-04*
*Status: Ready for implementation*
