#include "owl/PipeRobotController.hpp"

#include <iomanip>
#include <iostream>
#include <string>

namespace {

owl::SensorSample samplePipe(double meters, double seconds) {
    owl::SensorSample sample;

    sample.frontRangeMeters = 1.2;
    sample.rollDegrees = 4.0;
    sample.pitchDegrees = 2.0;
    sample.batteryPercent = 94.0 - seconds * 0.045;
    sample.waterFlowMetersPerSecond = 0.28;
    sample.turbidityNtu = 18.0;
    sample.acousticLeakScore = 0.12;

    if (meters > 2.8 && meters < 3.7) {
        sample.acousticLeakScore = 0.86;
        sample.waterFlowMetersPerSecond = 0.52;
        sample.turbidityNtu = 67.0;
    }

    if (meters > 5.7 && meters < 6.4) {
        sample.frontRangeMeters = 0.16;
        sample.rollDegrees = -9.0;
    }

    if (meters > 7.4) {
        sample.tetherTensionHigh = true;
    }

    return sample;
}

void printHeader() {
    std::cout << "time  mode     meters  left   right  light  flags       note\n";
    std::cout << "----  -------  ------  -----  -----  -----  ----------  ----------------\n";
}

std::string flags(const owl::Telemetry& telemetry) {
    std::string value;
    if (telemetry.possibleLeak) {
        value += "leak ";
    }
    if (telemetry.obstacleAhead) {
        value += "object ";
    }
    if (telemetry.unsafeTilt) {
        value += "tilt ";
    }
    if (telemetry.batteryLow) {
        value += "battery ";
    }
    if (value.empty()) {
        return "clear";
    }
    value.pop_back();
    return value;
}

}  // namespace

int main() {
    owl::PipeRobotController controller(0.30);
    constexpr double dtSeconds = 0.5;
    double seconds = 0.0;

    printHeader();

    for (int step = 0; step < 180; ++step) {
        const owl::Telemetry before = controller.telemetry();
        const owl::SensorSample sample = samplePipe(before.estimatedMetersTraveled, seconds);

        owl::OperatorIntent intent;
        intent.startSurvey = step == 0;

        const owl::MotorCommand command = controller.update(sample, intent, dtSeconds);
        const owl::Telemetry telemetry = controller.telemetry();

        if (step % 4 == 0 || telemetry.obstacleAhead || telemetry.possibleLeak ||
            telemetry.mode == owl::MissionMode::Recover) {
            std::cout << std::fixed << std::setprecision(1)
                      << std::setw(4) << seconds << "  "
                      << std::left << std::setw(7) << owl::toString(telemetry.mode)
                      << std::right << "  "
                      << std::setprecision(2)
                      << std::setw(6) << telemetry.estimatedMetersTraveled << "  "
                      << std::setw(5) << command.leftTrack << "  "
                      << std::setw(5) << command.rightTrack << "  "
                      << std::setw(5) << command.lightPower << "  "
                      << std::left << std::setw(10) << flags(telemetry) << "  "
                      << command.note << '\n';
        }

        if (telemetry.mode == owl::MissionMode::Recover &&
            telemetry.estimatedMetersTraveled < 6.8) {
            break;
        }

        seconds += dtSeconds;
    }

    return 0;
}
