"""VARIABLE CIRCLE SWEEP MACRO

Sweep varying circle profiles along a center path sketch.

Usage:
1. Create or Import a Spreadsheet object with two columns:
    - Column A: path length positions (s) along the center path (in mm)
    - Column B: diameters (d) of the horn at those positions (in mm)
2. Create a sketch representing the center path of the horn.
5. Select the 'Sketch' , then 'Spreadsheet' in the FreeCAD GUI.
6. Run this macro to generate a variable circle sweep shape with given thickness.

Notes:
- Created sweep will be extended when the center path is longer than the data in the spreadsheet.
- If sweep fails with 'Geom_BSplineSurface: Weights values too small', try decreasing the number of points in the spreadsheet.

"""

import re

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtGui


# ----------------------------
# Function to get contents of Spreadsheet as list of data
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
        raise ValueError("Spreadsheet is empty.")

# ----------------------------
# Variable Circle Sweep Function
# ----------------------------
def variableCircleSweep(thickness, is_reversed):

    doc = App.ActiveDocument

    # ----------------------------
    # Get sketch and sheet
    # ----------------------------
    sketch, sheet = Gui.Selection.getSelection()
    # Check class types
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

    # maximum length value in data
    max_s = raw_data[-1][0]

    # ----------------------------
    # Get selected center path
    # ----------------------------
    if not sketch:
        raise ValueError("please select a center path sketch")

    # reverse wire if specified
    if sketch.Shape.Wires:
        wire = sketch.Shape.Wires[0]
        if is_reversed:
            wire.reverse()

    # if wire.Length > max_s:
    #     raise ValueError("length of center path sketch must shorter than data in spreadsheet.")

    # make bspline curve from wire
    pts = wire.discretize(Distance=1.0)  # create points every 1 mm
    bspline = Part.BSplineCurve()
    bspline.interpolate(pts, False)  # create bspline curve, 'False' means the curve is not closed. its parameter consists of the length of the curve

    # ----------------------------
    # Generate circle profiles
    # ----------------------------
    profiles = []

    for s,d in raw_data:
        r = d / 2.0

        # stop if s exceeds total length
        if s > wire.Length:
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
    offset_shape = pipeshell.makeOffsetShape(thickness, 1e-6, offsetMode=0, fill=True)
    offset_obj = doc.addObject('Part::Feature', 'Offset_Pipe')
    offset_obj.Shape = offset_shape

    doc.recompute()

    return

# ----------------------------
# open task dialog first
# ----------------------------

class VariableCircleSweepPanel:
    def __init__(self):
        # Create the main widget
        self.form = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(self.form)
        layout.addWidget(QtGui.QLabel("Variable Circle Sweep Settings"))

        # Thickness Input (SpinBox)
        layout.addWidget(QtGui.QLabel("Thickness:"))
        self.thickness_input = QtGui.QDoubleSpinBox()
        self.thickness_input.setRange(0.0, 1000.0)
        self.thickness_input.setValue(1.0)
        self.thickness_input.setSuffix(" mm")
        layout.addWidget(self.thickness_input)

        # Reverse Checkbox
        self.reverse_input = QtGui.QCheckBox("Reverse Direction (show end point)")
        layout.addWidget(self.reverse_input)
        self.reverse_input.stateChanged.connect(self.on_reverse_changed)

        self.sg_node = None
        self.form.setLayout(layout)

        # Show marker preview if possible
        self.show_marker()

    def on_reverse_changed(self, state):
        self.update_marker()

    def update_marker(self):
        # Remove old marker if exists
        import FreeCADGui as Gui
        view = Gui.ActiveDocument.ActiveView
        sg = view.getSceneGraph()
        if self.sg_node:
            sg.removeChild(self.sg_node)
        self.show_marker()

    def show_marker(self):
        import FreeCADGui as Gui
        import pivy.coin as coin
        try:
            sketch, sheet = Gui.Selection.getSelection()
            if sketch.__class__.__name__ != 'SketchObject':
                return
        except Exception:
            return
        if not sketch.Shape.Edges:
            return
        # Determine which edge and parameter to use
        if self.reverse_input.isChecked():
            e = sketch.Shape.Edges[-1]
            pos = e.valueAt(e.LastParameter)
        else:
            e = sketch.Shape.Edges[0]
            pos = e.valueAt(e.FirstParameter)
        # Create marker
        view = Gui.ActiveDocument.ActiveView
        sg = view.getSceneGraph()
        self.sg_node = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor = (1.0, 0.0, 0.0)
        self.sg_node.addChild(mat)
        translation = coin.SoTranslation()
        translation.translation.setValue(tuple(pos))
        self.sg_node.addChild(translation)
        sphere = coin.SoSphere()
        sphere.radius = 0.5
        self.sg_node.addChild(sphere)
        sg.addChild(self.sg_node)

    def accept(self):
        """Action when 'OK' is clicked."""
        thickness = self.thickness_input.value()
        is_reversed = self.reverse_input.isChecked()
        variableCircleSweep(thickness, is_reversed)
        # Remove marker
        view = Gui.ActiveDocument.ActiveView
        sg = view.getSceneGraph()
        if self.sg_node:
            sg.removeChild(self.sg_node)
        Gui.Control.closeDialog()
        return True

    def reject(self):
        """Action when 'Cancel' is clicked."""
        view = Gui.ActiveDocument.ActiveView
        sg = view.getSceneGraph()
        if self.sg_node:
            sg.removeChild(self.sg_node)
        Gui.Control.closeDialog()
        return True

# ---------------------------
# main excecution
# ---------------------------

# To launch the panel
panel = VariableCircleSweepPanel()
Gui.Control.showDialog(panel)

