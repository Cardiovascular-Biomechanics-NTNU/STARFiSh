#include "CrimsonNetlistRuntime.hxx"
#include "CrimsonPythonRuntime.hxx"

#include "NetlistXmlReader.hxx"

#include <petscsys.h>

#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{

const int defaultStartingTimestep = 0;
const int defaultRestartInterval = 1000;
const bool defaultMasterControlScriptPresent = false;

std::vector<std::string> tokenize(const std::string& line)
{
    std::vector<std::string> tokens;
    std::string token;
    char quote = '\0';
    bool escaped = false;
    bool tokenStarted = false;

    for (std::string::const_iterator character = line.begin();
         character != line.end();
         ++character) {
        if (escaped) {
            token.push_back(*character);
            tokenStarted = true;
            escaped = false;
            continue;
        }

        if (*character == '\\') {
            escaped = true;
            tokenStarted = true;
            continue;
        }

        if (quote != '\0') {
            if (*character == quote) {
                quote = '\0';
            }
            else {
                token.push_back(*character);
            }
            tokenStarted = true;
            continue;
        }

        if (*character == '\'' || *character == '"') {
            quote = *character;
            tokenStarted = true;
        }
        else if (std::isspace(static_cast<unsigned char>(*character))) {
            if (tokenStarted) {
                tokens.push_back(token);
                token.clear();
                tokenStarted = false;
            }
        }
        else {
            token.push_back(*character);
            tokenStarted = true;
        }
    }

    if (escaped) {
        throw std::runtime_error(
            "Command line ends with an incomplete escape sequence.");
    }
    if (quote != '\0') {
        throw std::runtime_error(
            "Command line contains an unterminated quoted value.");
    }
    if (tokenStarted) {
        tokens.push_back(token);
    }

    return tokens;
}

template <typename ValueType>
ValueType parseValue(const std::string& text, const char* name)
{
    std::istringstream stream(text);
    ValueType value;
    stream >> value;
    if (!stream || !stream.eof()) {
        throw std::runtime_error(
            std::string("Invalid value for ") + name + ": " + text);
    }
    return value;
}

bool parseBool(const std::string& text, const char* name)
{
    if (text == "1" || text == "true" || text == "TRUE") {
        return true;
    }
    if (text == "0" || text == "false" || text == "FALSE") {
        return false;
    }
    throw std::runtime_error(
        std::string("Invalid boolean value for ") + name + ": " + text);
}

std::vector<int> parseSurfaceIds(const std::string& text)
{
    std::vector<int> surfaceIds;
    std::istringstream stream(text);
    std::string surfaceId;

    while (std::getline(stream, surfaceId, ',')) {
        if (surfaceId.empty()) {
            throw std::runtime_error(
                "Surface ID list contains an empty entry.");
        }
        surfaceIds.push_back(parseValue<int>(surfaceId, "surface ID"));
    }

    if (surfaceIds.empty()) {
        throw std::runtime_error(
            "At least one netlist surface ID is required.");
    }
    return surfaceIds;
}

std::string sanitizeError(const std::string& message)
{
    std::string sanitized = message;
    std::replace(sanitized.begin(), sanitized.end(), '\n', ' ');
    std::replace(sanitized.begin(), sanitized.end(), '\r', ' ');
    return sanitized;
}

void requireRuntime(
    const std::unique_ptr<CrimsonNetlistRuntime>& runtime)
{
    if (!runtime) {
        throw std::runtime_error(
            "LOAD must complete before this command is used.");
    }
}

void cleanup(
    std::unique_ptr<CrimsonNetlistRuntime>& runtime,
    bool terminateXmlReader)
{
    // Controller and circuit objects must be destroyed while Python and PETSc
    // are still alive because they retain objects owned by both runtimes.
    runtime.reset();

    if (terminateXmlReader) {
        NetlistXmlReader::Term();
    }

    if (Py_IsInitialized()) {
        Py_Finalize();
    }

    PetscBool petscInitialized;
    PetscBool petscFinalized;
    PetscInitialized(&petscInitialized);
    PetscFinalized(&petscFinalized);
    if (petscInitialized && !petscFinalized) {
        PetscFinalize();
    }
}

void printOk()
{
    std::cout << "STARFISH_OK" << std::endl;
}

} // namespace

int main()
{
    std::unique_ptr<CrimsonNetlistRuntime> runtime;
    bool xmlReaderUsed = false;

    try {
        PetscBool petscInitialized;
        PetscInitialized(&petscInitialized);
        if (!petscInitialized) {
            PetscInitialize(NULL, NULL, NULL, NULL);
        }
        initialisePython();

        std::cout << std::setprecision(17);
        std::cout << "STARFISH_READY" << std::endl;

        std::string line;
        while (std::getline(std::cin, line)) {
            if (line.empty()) {
                continue;
            }

            try {
                const std::vector<std::string> arguments = tokenize(line);
                if (arguments.empty()) {
                    continue;
                }

                const std::string& command = arguments[0];

                if (command == "QUIT") {
                    if (arguments.size() != 1) {
                        throw std::runtime_error(
                            "QUIT does not accept arguments.");
                    }
                    if (runtime) {
                        runtime->flush();
                    }
                    printOk();
                    break;
                }

                if (command == "LOAD") {
                    if (runtime) {
                        throw std::runtime_error(
                            "This worker already owns a loaded runtime.");
                    }
                    if (arguments.size() != 7 && arguments.size() != 10) {
                        throw std::runtime_error(
                            "LOAD expects either 6 or 9 arguments.");
                    }

                    const std::string& netlistXml = arguments[1];
                    const std::string& outputDirectory = arguments[2];
                    const int hstep = parseValue<int>(arguments[3], "hstep");
                    const double alfi =
                        parseValue<double>(arguments[4], "alfi");
                    const double dt = parseValue<double>(arguments[5], "dt");

                    int startingTimestep = defaultStartingTimestep;
                    int restartInterval = defaultRestartInterval;
                    bool masterControlScriptPresent =
                        defaultMasterControlScriptPresent;
                    std::string surfaceIdText;

                    if (arguments.size() == 7) {
                        surfaceIdText = arguments[6];
                    }
                    else {
                        startingTimestep = parseValue<int>(
                            arguments[6],
                            "starting timestep");
                        restartInterval = parseValue<int>(
                            arguments[7],
                            "restart interval");
                        masterControlScriptPresent = parseBool(
                            arguments[8],
                            "master control script flag");
                        surfaceIdText = arguments[9];
                    }

                    runtime.reset(new CrimsonNetlistRuntime(
                        hstep,
                        alfi,
                        dt,
                        startingTimestep,
                        restartInterval,
                        masterControlScriptPresent));

                    if (outputDirectory != "-") {
                        runtime->setOutputDirectory(outputDirectory);
                    }
                    // A failed load may still instantiate CRIMSON's XML
                    // singleton, so cleanup must terminate it on every path.
                    xmlReaderUsed = true;
                    runtime->load(
                        netlistXml,
                        parseSurfaceIds(surfaceIdText));

                    std::cout << "STARFISH_OK LOAD "
                              << runtime->controllerCount()
                              << std::endl;
                }
                else if (command == "START_AND_STATUS") {
                    requireRuntime(runtime);
                    // format: START_AND_STATUS timestep time num_surfaces <surf_id> ...
                    if (arguments.size() < 4) {
                        throw std::runtime_error("START_AND_STATUS expects timestep, time, num_surfaces, and surface IDs.");
                    }
                    int timestep = parseValue<int>(arguments[1], "timestep");
                    double time = parseValue<double>(arguments[2], "time");
                    int num_surfaces = parseValue<int>(arguments[3], "num_surfaces");
                    if (num_surfaces <= 0) {
                        throw std::runtime_error(
                            "START_AND_STATUS requires at least one surface.");
                    }
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
                else if (command == "START") {
                    requireRuntime(runtime);
                    if (arguments.size() != 3) {
                        throw std::runtime_error(
                            "START expects timestep and time.");
                    }
                    runtime->startTimestep(
                        parseValue<int>(arguments[1], "timestep"),
                        parseValue<double>(arguments[2], "time"));
                    printOk();
                }
                else if (command == "COEFFICIENTS") {
                    requireRuntime(runtime);
                    if (arguments.size() != 5) {
                        throw std::runtime_error(
                            "COEFFICIENTS expects surface, timestep, time, and flow.");
                    }
                    const std::pair<double, double> coefficients =
                        runtime->computeCoefficients(
                            parseValue<int>(arguments[1], "surface ID"),
                            parseValue<int>(arguments[2], "timestep"),
                            parseValue<double>(arguments[3], "time"),
                            parseValue<double>(arguments[4], "flow"));
                    std::cout << "STARFISH_COEFFICIENTS "
                              << coefficients.first
                              << " "
                              << coefficients.second
                              << std::endl;
                }
                else if (command == "INTERFACE_DATA") {
                    requireRuntime(runtime);
                    if (arguments.size() != 5) {
                        throw std::runtime_error(
                            "INTERFACE_DATA expects surface, timestep, time, and flow.");
                    }
                    const CrimsonNetlistRuntime::InterfaceData data =
                        runtime->computeInterfaceData(
                            parseValue<int>(arguments[1], "surface ID"),
                            parseValue<int>(arguments[2], "timestep"),
                            parseValue<double>(arguments[3], "time"),
                            parseValue<double>(arguments[4], "flow"));
                    std::cout << "STARFISH_INTERFACE_DATA "
                              << (data.flowPermitted ? 1 : 0)
                              << " "
                              << (data.boundaryConditionTypeChanged ? 1 : 0)
                              << " "
                              << data.dp_dq
                              << " "
                              << data.hop
                              << std::endl;
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
                    if (num_surfaces <= 0) {
                        throw std::runtime_error(
                            "UPDATE_ALL_AND_FINALIZE requires at least one surface.");
                    }
                    if (arguments.size() != 4 + 3 * num_surfaces) {
                        throw std::runtime_error("UPDATE_ALL_AND_FINALIZE arguments mismatch with num_surfaces.");
                    }
                    for (int i = 0; i < num_surfaces; ++i) {
                        int surface_id = parseValue<int>(arguments[4 + 3*i], "surface ID");
                        double pressure = parseValue<double>(arguments[5 + 3*i], "pressure");
                        double flow = parseValue<double>(arguments[6 + 3*i], "flow");
                        runtime->updateState(surface_id, timestep, pressure, flow);
                    }
                    runtime->finalizeTimestep(timestep);
                    printOk();
                }
                else if (command == "UPDATE_COEFFICIENTS") {
                    requireRuntime(runtime);
                    if (arguments.size() != 5) {
                        throw std::runtime_error(
                            "UPDATE_COEFFICIENTS expects surface, timestep, time, and flow.");
                    }
                    const std::pair<double, double> coefficients =
                        runtime->computeUpdateCoefficients(
                            parseValue<int>(arguments[1], "surface ID"),
                            parseValue<int>(arguments[2], "timestep"),
                            parseValue<double>(arguments[3], "time"),
                            parseValue<double>(arguments[4], "flow"));
                    std::cout << "STARFISH_UPDATE_COEFFICIENTS "
                              << coefficients.first
                              << " "
                              << coefficients.second
                              << std::endl;
                }
                else if (command == "INTERFACE_STATUS") {
                    requireRuntime(runtime);
                    if (arguments.size() != 2) {
                        throw std::runtime_error(
                            "INTERFACE_STATUS expects a surface ID.");
                    }

                    const int surfaceId =
                        parseValue<int>(arguments[1], "surface ID");
                    const bool flowPermitted =
                        runtime->flowPermitted(surfaceId);
                    const bool typeChanged =
                        runtime->boundaryConditionTypeChanged(surfaceId);

                    std::cout << "STARFISH_INTERFACE_STATUS "
                              << (flowPermitted ? 1 : 0)
                              << " "
                              << (typeChanged ? 1 : 0)
                              << std::endl;
                }
                else if (command == "SET_OUTPUT_DIRECTORY") {
                    requireRuntime(runtime);
                    if (arguments.size() != 2) {
                        throw std::runtime_error(
                            "SET_OUTPUT_DIRECTORY expects one path.");
                    }
                    runtime->setOutputDirectory(arguments[1]);
                    printOk();
                }
                else if (command == "UPDATE") {
                    requireRuntime(runtime);
                    if (arguments.size() != 5) {
                        throw std::runtime_error(
                            "UPDATE expects surface, timestep, pressure, and flow.");
                    }
                    runtime->updateState(
                        parseValue<int>(arguments[1], "surface ID"),
                        parseValue<int>(arguments[2], "timestep"),
                        parseValue<double>(arguments[3], "pressure"),
                        parseValue<double>(arguments[4], "flow"));
                    printOk();
                }
                else if (command == "FINALIZE") {
                    requireRuntime(runtime);
                    if (arguments.size() != 2) {
                        throw std::runtime_error(
                            "FINALIZE expects a timestep.");
                    }
                    runtime->finalizeTimestep(
                        parseValue<int>(arguments[1], "timestep"));
                    printOk();
                }
                else {
                    throw std::runtime_error(
                        "Unknown worker command: " + command);
                }
            }
            catch (const std::exception& error) {
                if (Py_IsInitialized() && PyErr_Occurred()) {
                    PyErr_Print();
                }
                std::cout << "STARFISH_ERROR "
                          << sanitizeError(error.what())
                          << std::endl;
            }
        }

        cleanup(runtime, xmlReaderUsed);
        return 0;
    }
    catch (const std::exception& error) {
        if (Py_IsInitialized() && PyErr_Occurred()) {
            PyErr_Print();
        }
        std::cout << "STARFISH_FATAL "
                  << sanitizeError(error.what())
                  << std::endl;
        cleanup(runtime, xmlReaderUsed);
        return 1;
    }
}
