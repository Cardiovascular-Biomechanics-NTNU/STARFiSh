import re

with open("ext/CrimsonNetlistWorker.cpp", "r") as f:
    content = f.read()

new_commands = """                else if (command == "START_AND_STATUS") {
                    requireRuntime(runtime);
                    // format: START_AND_STATUS timestep time num_surfaces <surf_id> ...
                    if (arguments.size() < 4) {
                        throw std::runtime_error("START_AND_STATUS expects timestep, time, num_surfaces, and surface IDs.");
                    }
                    int timestep = parseValue<int>(arguments[1], "timestep");
                    double time = parseValue<double>(arguments[2], "time");
                    int num_surfaces = parseValue<int>(arguments[3], "num_surfaces");
                    if (arguments.size() != 4 + num_surfaces) {
                        throw std::runtime_error("START_AND_STATUS arguments mismatch with num_surfaces.");
                    }
                    runtime->startTimestep(timestep, time);
                    std::cout << "STARFISH_START_STATUS";
                    for (int i = 0; i < num_surfaces; ++i) {
                        int surfaceId = parseValue<int>(arguments[4 + i], "surface ID");
                        bool flowPermitted = runtime->flowPermitted(surfaceId);
                        bool typeChanged = runtime->boundaryConditionTypeChanged(surfaceId);
                        std::cout << " " << (flowPermitted ? 1 : 0) << " " << (typeChanged ? 1 : 0);
                    }
                    std::cout << std::endl;
                }
"""

content = content.replace("                else if (command == \"START\") {", new_commands + "                else if (command == \"START\") {")

with open("ext/CrimsonNetlistWorker.cpp", "w") as f:
    f.write(content)
