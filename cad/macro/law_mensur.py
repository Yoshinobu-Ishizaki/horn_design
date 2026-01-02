"""Create a horn shape by lofting circle profiles along a center path sketch.

Usage:
1. Create or Import a Spreadsheet object with two columns:
    - Column A: path length positions (s) along the center path (in mm)
    - Column B: diameters (d) of the horn at those positions (in mm)
2. Create a sketch representing the center path of the horn.
3. Create VarSet variable "thickness" to add outer wall thickness.
4. Also create VarSet variable "reverse" (boolean) to reverse the center path direction if needed.
5. Select the sketch , then Spreadsheet in the FreeCAD GUI.
6. Run this macro to generate the horn shape.
"""

import FreeCAD as App
import FreeCADGui as Gui
import Part
import re
import math

doc = App.ActiveDocument

# ----------------------------
# Get contents of Spreadsheet as list of data
# ----------------------------
def getSpreadsheetData(sheet):
    """Extracts the entire spreadsheet data as a list of lists."""
    # 2. Get the used range (e.g., ('A1', 'B15'))
    used_range = sheet.getUsedRange()

    if used_range:
        # used_range[1] is the bottom-right cell (e.g., 'B15')
        last_cell = used_range[1]

        # Use regex to extract the row number from the cell name (e.g., '15' from 'B15')
        match = re.search(r"\d+", last_cell)
        if match:
            max_row = int(match.group())

            # 3. Extract Column A based on the calculated range
            datA = [float(sheet.getContents(f"A{i}")) for i in range(1, max_row + 1)]
            datB = [float(sheet.getContents(f"B{i}")) for i in range(1, max_row + 1)]
            return list(zip(datA, datB))
    else:
        print("Spreadsheet is empty.")
        return None

# ----------------------------
# Get sketch and sheet
# ----------------------------

sketch, sheet = Gui.Selection.getSelection()
# Check class types
expected_sketch_class = 'Sketcher.SketchObject'
expected_sheet_class = 'Spreadsheet.Sheet'
if sketch.__class__.__name__ != 'SketchObject':
    raise TypeError(f"Selected sketch is not a SketchObject, got {sketch.__class__.__name__}")
if sheet.__class__.__name__ != 'Sheet':
    raise TypeError(f"Selected sheet is not a Sheet, got {sheet.__class__.__name__}")

# ----------------------------
# Get spreadsheet data
# ----------------------------
raw_data = getSpreadsheetData(sheet)
if raw_data is None:
    raise ValueError("Spreadsheet is empty or not found.")

# ----------------------------
# Get selected center path
# ----------------------------
if not sketch:
    raise ValueError("please select a center path sketch")

if sketch.Shape.Wires:
    wire = sketch.Shape.Wires[0]
    if doc.getObject('VarSet').reverse:
        wire.reverse()

total_length = wire.Length

# make bspline curve from wire
pts = wire.discretize(Distance=1.0)  # create points every 1 mm
bspline = Part.BSplineCurve()
bspline.interpolate(
    pts, False
)  # create bspline curve, 'False' means the curve is not closed. its parameter consists of the length of the curve

# ----------------------------
# Generate circle profiles
# ----------------------------
profiles = []

# create section wires
for i in range(len(raw_data)):
    s = raw_data[i][0]
    d = raw_data[i][1]
    r = d / 2.0

    if s > total_length:
        break

    pos = bspline.value(s) # position on the bspline at parameter s
    T = bspline.tangent(s)[0]  # first element of tangent tuple

    # Construct orthonormal frame
    Z = T
    X = App.Vector(0, 0, 1).cross(Z)
    if X.Length < 1e-6:
        X = App.Vector(1, 0, 0)
    X.normalize()
    Y = Z.cross(X).normalize()

    placement = App.Placement(pos, App.Rotation(X, Y, Z))

    # Circle profile
    circle = Part.makeCircle(r)
    circle = circle.transformGeometry(placement.toMatrix())
    cw = Part.Wire(circle)
    profiles.append(cw)

# create pipeshell
pipe_obj = doc.addObject('Part::Feature', 'Face_Pipe')
makeSolid = False
isFrenet = False
pipeshell = wire.makePipeShell(profiles, makeSolid, isFrenet)
pipe_obj.Shape = pipeshell

# create offset shape with fill (call on pipeshell, not pipe_obj)
th = doc.getObject('VarSet').thickness
offset_shape = pipeshell.makeOffsetShape(th, 0.001, offsetMode=0, fill=True)
offset_obj = doc.addObject('Part::Feature', 'Offset_Pipe')
offset_obj.Shape = offset_shape

doc.recompute()
