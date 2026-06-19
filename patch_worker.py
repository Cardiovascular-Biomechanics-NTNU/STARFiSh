import re

with open("ext/CrimsonNetlistWorker.cpp", "r") as f:
    content = f.read()

new_commands = """                else if (command == "COEFFICIENTS_ALL") {
                    requireRuntime(runtime);
                    // format: COEFFICIENTS_ALL timestep time num_surfaces <surf_id flow> ...
                    if (arguments.size() < 4) {
                        throw std::runtime_error("COEFFICIENTS_ALL expects timestep, time, num_surfaces, and pairs of surface ID and flow.");
                    }
                    int timestep = parseValue<int>(arguments[1], "timestep");
                    double time = parseValue<double>(arguments[2], "time");
                    int num_surfaces = parseValue<int>(arguments[3], "num_surfaces");
                    if (arguments.size() != 4 + 2 * num_surfaces) {
                        throw std::runtime_error("COEFFICIENTS_ALL arguments mismatch with num_surfaces.");
                    }
                    std::cout << "STARFISH_COEFFICIENTS_ALL";
                    for (int i = 0; i < num_surfaces; ++i) {
                        int surface_id = parseValue<int>(arguments[4 + 2*i], "surface ID");
                        double flow = parseValue<double>(arguments[5 + 2*i], "flow");
                        const std::pair<double, double> coefficients = 
                            runtime->computeCoefficients(surface_id, timestep, time, flow);
                        std::cout << " " << coefficients.first << " " << coefficients.second;
                    }
                    std::cout << std::endl;
                }
                else if (command == "UPDATE_ALL_AND_FINALIZE") {
                    requireRuntime(runtime);
                    // format: UPDATE_ALL_AND_FINALIZE timestep time num_surfaces <surf_id pressure flow> ...
                    if (arguments.size() < 4) {
                        throw std::runtime_error("UPDATE_ALL_AND_FINALIZE expects timestep, time, num_surfaces, and triplets of surface ID, pressure, flow.");
                    }
                    int timestep = parseValue<int>(arguments[1], "timestep");
                    double time = parseValue<double>(arguments[2], "time");
                    int num_surfaces = parseValue<int>(arguments[3], "num_surfaces");
                    if (arguments.size() != 4 + 3 * num_surfaces) {
                        throw std::runtime_error("UPDATE_ALL_AND_FINALIZE arguments mismatch with num_surfaces.");
                    }
                    for (int i = 0; i < num_surfaces; ++i) {
                        int surface_id = parseValue<int>(arguments[4 + 3*i], "surface ID");
                        double pressure = parseValue<double>(arguments[5 + 3*i], "pressure");
                        double flow = parseValue<double>(arguments[6 + 3*i], "flow");
                        runtime->computeUpdateCoefficients(surface_id, timestep, time, flow);
                        runtime->updateState(surface_id, timestep, pressure, flow);
                    }
                    runtime->finalizeTimestep(timestep);
                    printOk();
                }
"""

content = content.replace("                else if (command == \"UPDATE_COEFFICIENTS\") {", new_commands + "                else if (command == \"UPDATE_COEFFICIENTS\") {")

with open("ext/CrimsonNetlistWorker.cpp", "w") as f:
    f.write(content)
