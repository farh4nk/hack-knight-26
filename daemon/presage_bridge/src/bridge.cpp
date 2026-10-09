#include <iostream>
#include <string>
#include <chrono>
#include <thread>
#include <atomic>
#include <csignal>
#include <cstdlib>
#include <memory>

#include <opencv2/opencv.hpp>
// TODO: Verify exact include path for SmartSpectra
#include <smartspectra/smartspectra.h>

using presage::smartspectra::Metrics;
using presage::smartspectra::SmartSpectraConfig;
using presage::smartspectra::SmartSpectraLogLevel;
using presage::smartspectra::CustomInput;

volatile std::sig_atomic_t g_running = 1;

void signal_handler(int signum) {
    g_running = 0;
}

int main(int argc, char** argv) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    const char* api_key = std::getenv("PRESAGE_API_KEY");
    if (!api_key) {
        std::cerr << "Error: PRESAGE_API_KEY environment variable not set." << std::endl;
        return 1;
    }

    const char* device_env = std::getenv("PRESAGE_VIDEO_DEVICE");
    std::string device_path = device_env ? device_env : "/dev/video11";

    SmartSpectraConfig config;
    config.api_key = api_key;
    
    // TODO(verify-in-container): Verify how to request multiple metrics in SDK API. Assuming bitwise OR and CardioMetrics().
    config.requested_metrics = SmartSpectraConfig::BreathingMetrics() | SmartSpectraConfig::CardioMetrics();

    presage::smartspectra::SmartSpectra sdk(config);

    sdk.SetOnError([](const std::string& error) {
        std::cerr << "SDK Error: " << error << std::endl;
    });

    sdk.SetOnMetrics([](const Metrics& m, int64_t ts) {
        auto now = std::chrono::system_clock::now();
        double epoch_seconds = std::chrono::duration<double>(now.time_since_epoch()).count();

        double brpm = 0.0;
        double bpm = 0.0;
        double confidence = 0.0;

        bool has_breathing = m.has_breathing();
        bool has_cardio = m.has_cardio();

        if (has_breathing && m.breathing().rate_size() > 0) {
            auto br_sample = m.breathing().rate(m.breathing().rate_size() - 1);
            brpm = br_sample.value();
            // TODO(verify-in-container): verify measurement confidence accessor. Assuming stable() fallback.
            confidence = br_sample.stable() ? 0.9 : 0.3;
        }

        if (has_cardio && m.cardio().pulse_rate_size() > 0) {
            auto cardio_sample = m.cardio().pulse_rate(m.cardio().pulse_rate_size() - 1);
            bpm = cardio_sample.value();
            if (!has_breathing || m.breathing().rate_size() == 0) {
                // TODO(verify-in-container): verify measurement confidence accessor. Assuming stable() fallback.
                confidence = cardio_sample.stable() ? 0.9 : 0.3; 
            }
        }

        if (!has_breathing && !has_cardio) {
            confidence = 0.0;
        }

        std::cout << "{\"t\": " << epoch_seconds 
                  << ", \"brpm\": " << brpm 
                  << ", \"bpm\": " << bpm 
                  << ", \"confidence\": " << confidence << "}\n";
        std::cout.flush();
    });

    std::shared_ptr<CustomInput> handle;
    // TODO(verify-in-container): Check if Build returns something with operator bool() or requires .ok()
    auto status = sdk.UseCustomInput().Build(handle);
    if (!status) {
        std::cerr << "Error: failed to build custom input." << std::endl;
        return 1;
    }

    cv::VideoCapture cap(device_path);
    if (!cap.isOpened()) {
        std::cerr << "Failed to open camera: " << device_path << std::endl;
        return 1;
    }

    sdk.Start();

    auto start_time = std::chrono::steady_clock::now();
    int64_t last_timestamp_us = -1;

    cv::Mat frame;
    while (g_running) {
        if (cap.read(frame)) {
            auto now = std::chrono::steady_clock::now();
            int64_t timestamp_us = std::chrono::duration_cast<std::chrono::microseconds>(now - start_time).count();
            
            if (timestamp_us <= last_timestamp_us) {
                timestamp_us = last_timestamp_us + 1;
            }
            last_timestamp_us = timestamp_us;

            handle->Send(frame, timestamp_us);
        } else {
            std::cerr << "Failed to read frame from camera." << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }

    sdk.Stop();
    cap.release();

    return 0;
}
