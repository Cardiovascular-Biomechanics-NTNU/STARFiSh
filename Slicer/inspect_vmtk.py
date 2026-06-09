import slicer
import qt

# Get the widget
widget = slicer.modules.extractcenterline.widgetRepresentation()

# Print all QCheckBoxes and their names
print("CHECKBOXES:")
for cb in widget.findChildren(qt.QCheckBox):
    print(cb.name, cb.text)

# Print all CollapsibleButtons and their names
print("\nCOLLAPSIBLE BUTTONS:")
for cb in widget.findChildren("ctkCollapsibleButton"):
    print(cb.name, cb.text)

slicer.app.quit()
