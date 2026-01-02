import FreeCAD as App
import FreeCADGui
import Part
import re

doc = App.ActiveDocument

# ----------------------------
# Get contents of Spreadsheet as list of data
# ----------------------------

def getSpreadsheetData(sheet):
    """Extracts the entire spreadsheet data as a list of lists."""

    # 1. Access the document and spreadsheet
    sheet = doc.getObject('Spreadsheet')

    # 2. Get the used range (e.g., ('A1', 'B15'))
    used_range = sheet.getUsedRange()

    if used_range:
        # used_range[1] is the bottom-right cell (e.g., 'B15')
        last_cell = used_range[1]
        
        # Use regex to extract the row number from the cell name (e.g., '15' from 'B15')
        match = re.search(r'\d+', last_cell)
        if match:
            max_row = int(match.group())
            
            # 3. Extract Column A based on the calculated range
            datA = [float(sheet.getContents(f'A{i}')) for i in range(1, max_row + 1)]
            datB = [float(sheet.getContents(f'B{i}')) for i in range(1, max_row + 1)]
            return list(zip(datA, datB))
    else:
        print("Spreadsheet is empty.")
        return None

# ----------------------------
# Get spreadsheet data
# ----------------------------
raw_data = getSpreadsheetData('Spreadsheet')
if raw_data is None:
    raise ValueError("Spreadsheet is empty or not found.")

# ----------------------------
# Get selected center path
# ----------------------------
selection = FreeCADGui.Selection.getSelection()
if not selection:
    raise ValueError("please select a center path sketch")
obj = selection[0]

# If it's a wire with multiple edges, unify it
if obj.Shape.Wires:
    wire = obj.Shape.Wires[0]

total_length = wire.Length

# make bspline curve from wire
pts = wire.discretize(Distance=1.0) # create points every 1 mm
bspline = Part.BSplineCurve()
bspline.interpolate(pts, False) # create bspline curve, 'False' means the curve is not closed. its parameter consists of the length of the curve

# ----------------------------
# Generate circle profiles
# ----------------------------
profiles = []

for s, d in raw_data:

    pos = bspline.value(s)
    T = bspline.tangent(s)[0] # first element of tangent tuple
    r = d / 2.0

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
    wire = Part.Wire(circle)

    profiles.append(wire)

# ----------------------------
# Loft horn
# ----------------------------
loft = Part.makeLoft(profiles, False) # surface loft
Part.show(loft)

doc.recompute()
