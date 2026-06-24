#pragma once

#include <string>

namespace owl {

enum class MissionMode {
    Idle,
    Manual,
    Survey,
    Recover
};

struct SensorSample {
    double frontRangeMeters = 1.0;
    double rollDegrees = 0.0;
    double pitchDegrees = 0.0;
    double batteryPercent = 100.0;
    double waterFlowMetersPerSecond = 0.0;
    double turbidityNtu = 0.0;
    double acousticLeakScore = 0.0;
    bool tetherTensionHigh = false;
};

struct OperatorIntent {
    double throttle = 0.0;
    double steering = 0.0;
    bool startSurvey = false;
    bool stop = false;
    bool recover = false;
};

struct MotorCommand {
    double leftTrack = 0.0;
    double rightTrack = 0.0;
    double lightPower = 0.0;
    std::string note;
};

struct Telemetry {
    MissionMode mode = MissionMode::Idle;
    double estimatedMetersTraveled = 0.0;
    bool obstacleAhead = false;
    bool possibleLeak = false;
    bool unsafeTilt = false;
    bool batteryLow = false;
    std::string status = "idle";
};

class PipeRobotController {
public:
    explicit PipeRobotController(double pipeDiameterMeters = 0.30);

    MotorCommand update(const SensorSample& sample,
                        const OperatorIntent& intent,
                        double dtSeconds);

    Telemetry telemetry() const;
    void reset();

private:
    double pipeDiameterMeters_;
    MissionMode mode_ = MissionMode::Idle;
    double estimatedMetersTraveled_ = 0.0;
    bool obstacleAhead_ = false;
    bool possibleLeak_ = false;
    bool unsafeTilt_ = false;
    bool batteryLow_ = false;
    std::string status_ = "idle";

    void updateMode(const SensorSample& sample, const OperatorIntent& intent);
    void updateFlags(const SensorSample& sample);
    MotorCommand commandForMode(const SensorSample& sample,
                                const OperatorIntent& intent) const;
    void integrateDistance(const MotorCommand& command, double dtSeconds);

    static double clamp(double value, double lower, double upper);
};

std::string toString(MissionMode mode);

}  // namespace owl
