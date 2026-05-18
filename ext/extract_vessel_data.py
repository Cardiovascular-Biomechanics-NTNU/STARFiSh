#!/usr/bin/env python
import os
import numpy as np
from vmtk import vmtkscripts

# --- 1. SET FILE PATHS ---
input_surface = "Venous Blended.brep.vtp"

if not os.path.exists(input_surface):
    raise FileNotFoundError(f"Could not find the file '{input_surface}'")

# --- 2. EXPLICITLY READ THE SURFACE ---
print("Reading input surface file...")
reader = vmtkscripts.vmtkSurfaceReader()
reader.InputFileName = input_surface
reader.Execute()

# --- 3. INTERACTIVE CORNER / SEED SELECTION ---
print("\n" + "="*60)
print(" INTERACTIVE WINDOW INSTRUCTIONS:")
print(" 1. Press 'p' on your keyboard to activate the picking tool.")
print(" 2. Left-click at the center of your INLET (Source Point).")
print(" 3. Left-click at the center of each OUTLET (Target Points).")
print("    (Red handles will appear where you click)")
print(" 4. Press 'q' on your keyboard to close the window and calculate.")
print("="*60 + "\n")

centerlines = vmtkscripts.vmtkCenterlines()
centerlines.Surface = reader.Surface
centerlines.SeedSelectorName = "pickpoint"  # Opens a controlled interactive picker
centerlines.Execute()

# Check if the user selected points or just closed the window
if centerlines.Centerlines is None or centerlines.Centerlines.GetNumberOfPoints() == 0:
    print("[ERROR] Centerline extraction aborted or no points selected.")
    exit(1)

print("Splitting Centerlines into Vessel Branches...")
# --- 4. SEGMENT & EXTRACT BRANCHES ---
extractor = vmtkscripts.vmtkBranchExtractor()
extractor.Centerlines = centerlines.Centerlines
extractor.RadiusArrayName = "MaximumInscribedSphereRadius"
extractor.Execute()
split_centerlines = extractor.Centerlines

print("Calculating Branch Geometries...")
# --- 5. CALCULATE LENGTH & GEOMETRY ---
geometry = vmtkscripts.vmtkBranchGeometry()
geometry.Centerlines = split_centerlines
geometry.RadiusArrayName = "MaximumInscribedSphereRadius"
geometry.Execute()

# --- 6. EXTRACT AND ORGANIZE DATA VIA VTK ---
poly_data = split_centerlines

group_ids = poly_data.GetPointData().GetArray("GroupIds")
radii = poly_data.GetPointData().GetArray("MaximumInscribedSphereRadius")
abscissas = poly_data.GetPointData().GetArray("Abscissas")

vessel_branches = {}

num_points = poly_data.GetNumberOfPoints()
for i in range(num_points):
    g_id = int(group_ids.GetComponent(i, 0))
    r = radii.GetComponent(i, 0)
    length_pos = abscissas.GetComponent(i, 0)
    
    area = np.pi * (r ** 2)
    
    if g_id not in vessel_branches:
        vessel_branches[g_id] = {'length_profile': [], 'area_profile': []}
        
    vessel_branches[g_id]['length_profile'].append(length_pos)
    vessel_branches[g_id]['area_profile'].append(area)

# --- 7. DISPLAY RESULTS ---
print("\n" + "="*50)
print(f"VESSEL GEOMETRY REPORT ({len(vessel_branches)} Branches Found)")
print("="*50)

for g_id, data in vessel_branches.items():
    sort_idx = np.argsort(data['length_profile'])
    lengths = np.array(data['length_profile'])[sort_idx]
    areas = np.array(data['area_profile'])[sort_idx]
    
    total_branch_length = lengths[-1] - lengths[0]
    mean_area = np.mean(areas)
    
    print(f"\n▶ Branch ID: {g_id}")
    print(f"  Total Segment Length: {total_branch_length:.2f}")
    print(f"  Mean Cross-Section Area: {mean_area:.2f}")
    print("  Area Profile Over Length (Sample points):")
    
    samples = np.linspace(0, len(lengths) - 1, 5, dtype=int)
    for idx in samples:
        relative_dist = lengths[idx] - lengths[0]
        print(f"    At distance {relative_dist:6.2f} -> Area = {areas[idx]:6.2f}")

print("\nProcessing complete.")
