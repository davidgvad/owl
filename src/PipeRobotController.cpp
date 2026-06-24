#include "owl/PipeRobotController.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace owl {
namespace {

constexpr double kDeadband = 0.05;
constexpr double kNominalTrackSpeedMetersPerSecond = 0.32;

double clampValue(double value, double lower, double upper) {
    return std::max(lower, std::min(value, upper));
}

MotorCommand makeCommand(double left, double right, double light, std::string note) {
    return {
        clampValue(left, -1.0, 1.0),
        clampValue(right, -1.0, 1.0),
        clampValue(light, 0.0, 1.0),
        std::move(note)
    };
}

}  // namespace

PipeRobotController::PipeRobotController(double pipeDiameterMeters)
    : pipeDiameterMeters_(pipeDiameterMeters) {
    if (pipeDiameterMeters_ <= 0.0) {
        throw std::invalid_argument("pipe diameter must be positive");
    }
}

MotorCommand PipeRobotController::update(const SensorSample& sample,
                                         const OperatorIntent& intent,
                                         double dtSeconds) {
    if (dtSeconds < 0.0) {
        throw std::invalid_argument("dtSeconds must not be negative");
    }

    updateFlags(sample);
    updateMode(sample, intent);

    MotorCommand command = commandForMode(sample, intent);
    integrateDistance(command, dtSeconds);
    return command;
}

Telemetry PipeRobotController::telemetry() const {
    return {
        mode_,
        estimatedMetersTraveled_,
        obstacleAhead_,
        possibleLeak_,
        unsafeTilt_,
        batteryLow_,
        status_
    };
}

void PipeRobotController::reset() {
    mode_ = MissionMode::Idle;
    estimatedMetersTraveled_ = 0.0;
    obstacleAhead_ = false;
    possibleLeak_ = false;
    unsafeTilt_ = false;
    batteryLow_ = false;
    status_ = "idle";
}

void PipeRobotController::updateMode(const SensorSample& sample,
                                     const OperatorIntent& intent) {
    if (intent.stop) {
        mode_ = MissionMode::Idle;
        status_ = "operator stop";
        return;
    }

    if (intent.recover || sample.tetherTensionHigh || batteryLow_ || unsafeTilt_) {
        mode_ = MissionMode::Recover;
        status_ = "recovering";
        return;
    }

    if (intent.startSurvey) {
        mode_ = MissionMode::Survey;
        status_ = "surveying";
        return;
    }

    if (std::abs(intent.throttle) > kDeadband || std::abs(intent.steering) > kDeadband) {
        mode_ = MissionMode::Manual;
        status_ = "manual control";
        return;
    }

    if (mode_ == MissionMode::Manual) {
        mode_ = MissionMode::Idle;
        status_ = "manual idle";
    }
}

void PipeRobotController::updateFlags(const SensorSample& sample) {
    const double cautionRange = std::max(0.18, pipeDiameterMeters_ * 0.75);
    obstacleAhead_ = sample.frontRangeMeters < cautionRange;

    unsafeTilt_ = std::abs(sample.rollDegrees) > 38.0 ||
                  std::abs(sample.pitchDegrees) > 32.0;

    batteryLow_ = sample.batteryPercent < 18.0;

    const bool acousticHit = sample.acousticLeakScore > 0.72;
    const bool cloudyAndFast = sample.turbidityNtu > 55.0 &&
                               sample.waterFlowMetersPerSecond > 0.45;
    possibleLeak_ = acousticHit || cloudyAndFast;
}

MotorCommand PipeRobotController::commandForMode(const SensorSample& sample,
                                                 const OperatorIntent& intent) const {
    switch (mode_) {
    case MissionMode::Idle:
        return makeCommand(0.0, 0.0, 0.20, "standing by");

    case MissionMode::Manual: {
        const double throttle = clamp(intent.throttle, -1.0, 1.0);
        const double steering = clamp(intent.steering, -1.0, 1.0);
        const double left = throttle - steering * 0.55;
        const double right = throttle + steering * 0.55;
        return makeCommand(left, right, 0.75, "operator drive");
    }

    case MissionMode::Survey: {
        if (unsafeTilt_ || batteryLow_) {
            return makeCommand(0.0, 0.0, 1.0, "survey hold");
        }

        if (obstacleAhead_) {
            const double turnBias = sample.rollDegrees >= 0.0 ? -0.35 : 0.35;
            return makeCommand(0.10 - turnBias, 0.10 + turnBias, 1.0, "obstacle scan");
        }

        const double inspectionSpeed = possibleLeak_ ? 0.22 : 0.42;
        const double light = possibleLeak_ ? 1.0 : 0.82;
        return makeCommand(inspectionSpeed, inspectionSpeed, light, "forward survey");
    }

    case MissionMode::Recover:
        return makeCommand(-0.30, -0.30, 1.0, "reverse recovery");
    }

    return makeCommand(0.0, 0.0, 0.0, "unknown mode");
}

void PipeRobotController::integrateDistance(const MotorCommand& command,
                                            double dtSeconds) {
    const double averageTrackCommand = (command.leftTrack + command.rightTrack) * 0.5;
    const double speedMetersPerSecond = averageTrackCommand *
                                        kNominalTrackSpeedMetersPerSecond;
    estimatedMetersTraveled_ += speedMetersPerSecond * dtSeconds;
}

double PipeRobotController::clamp(double value, double lower, double upper) {
    return clampValue(value, lower, upper);
}

std::string toString(MissionMode mode) {
    switch (mode) {
    case MissionMode::Idle:
        return "idle";
    case MissionMode::Manual:
        return "manual";
    case MissionMode::Survey:
        return "survey";
    case MissionMode::Recover:
        return "recover";
    }

    return "unknown";
}

}  // namespace owl
