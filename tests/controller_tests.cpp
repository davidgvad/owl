#include "owl/PipeRobotController.hpp"

#include <cassert>
#include <cmath>
#include <iostream>

namespace {

void surveyMovesForward() {
    owl::PipeRobotController controller;
    owl::SensorSample sample;
    owl::OperatorIntent intent;
    intent.startSurvey = true;

    const owl::MotorCommand command = controller.update(sample, intent, 1.0);
    const owl::Telemetry telemetry = controller.telemetry();

    assert(telemetry.mode == owl::MissionMode::Survey);
    assert(command.leftTrack > 0.0);
    assert(command.rightTrack > 0.0);
    assert(telemetry.estimatedMetersTraveled > 0.0);
}

void leakSlowsSurveyAndRaisesFlag() {
    owl::PipeRobotController controller;
    owl::SensorSample sample;
    owl::OperatorIntent intent;
    intent.startSurvey = true;

    controller.update(sample, intent, 1.0);
    sample.acousticLeakScore = 0.9;
    intent.startSurvey = false;

    const owl::MotorCommand command = controller.update(sample, intent, 1.0);
    const owl::Telemetry telemetry = controller.telemetry();

    assert(telemetry.possibleLeak);
    assert(std::abs(command.leftTrack - 0.22) < 0.001);
    assert(std::abs(command.rightTrack - 0.22) < 0.001);
}

void obstacleTriggersScanCommand() {
    owl::PipeRobotController controller;
    owl::SensorSample sample;
    owl::OperatorIntent intent;
    intent.startSurvey = true;

    controller.update(sample, intent, 1.0);
    sample.frontRangeMeters = 0.10;
    intent.startSurvey = false;

    const owl::MotorCommand command = controller.update(sample, intent, 1.0);
    const owl::Telemetry telemetry = controller.telemetry();

    assert(telemetry.obstacleAhead);
    assert(command.leftTrack != command.rightTrack);
}

void tetherTensionForcesRecovery() {
    owl::PipeRobotController controller;
    owl::SensorSample sample;
    owl::OperatorIntent intent;
    intent.startSurvey = true;

    controller.update(sample, intent, 1.0);
    sample.tetherTensionHigh = true;
    intent.startSurvey = false;

    const owl::MotorCommand command = controller.update(sample, intent, 1.0);
    const owl::Telemetry telemetry = controller.telemetry();

    assert(telemetry.mode == owl::MissionMode::Recover);
    assert(command.leftTrack < 0.0);
    assert(command.rightTrack < 0.0);
}

}  // namespace

int main() {
    surveyMovesForward();
    leakSlowsSurveyAndRaisesFlag();
    obstacleTriggersScanCommand();
    tetherTensionForcesRecovery();

    std::cout << "controller tests passed\n";
    return 0;
}
