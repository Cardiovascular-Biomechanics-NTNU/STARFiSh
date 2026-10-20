# CRIMSON STARFiSh (CRIMSON-1D)
This is a custom version of STARFiSh with a new GUI and the ability to use the CRIMSON Netlist boundary condition manager.

Link to original STARFiSh: <http://www.ntnu.no/starfish>
(Copyright 2012-2016 Vinzenz Eck)

## Installation and Documentation
For installation and documentation on this version please refer to the `docs/` folder.

Netlist boundaries now use the standalone CRIMSON **NumPy/reference** solver.
Set its checkout location in [netlist_config.py](netlist_config.py).
See [integration and C++ comparison results](docs/netlist_py_integration.md)
for configuration, supported cases, controller migration, and validation commands.
The previous C++ integration is retained for reference and comparison.
