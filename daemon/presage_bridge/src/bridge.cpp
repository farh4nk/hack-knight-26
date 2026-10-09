// Presage (SmartSpectra) bridge: reads frames, emits vitals as NDJSON on stdout.
//
// Frame sources:
//   bridge --stdin WxH   raw BGR frames (W*H*3 bytes each) read from stdin; the
//                        daemon owns the camera and pipes frames in
//   bridge               cv::VideoCapture on $PRESAGE_VIDEO_DEVICE (default /dev/video11)
//
// Output: {"t": <epoch s>, "brpm": .., "bpm": .., "confidence": ..} per metrics update.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <signal.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <opencv2/opencv.hpp>
#include <smartspectra/smartspectra.h>

using namespace presage::smartspectra;

namespace {

volatile std::sig_atomic_t g_running = 1;
std::atomic<bool> g_fatal{false};  // set when the SDK reports an unrecoverable error

void signal_handler(int) { g_running = 0; }

void install_signal_handlers() {
    // No SA_RESTART: a blocking fread() on stdin must return EINTR so we can exit.
    struct sigaction sa {};
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, nullptr);
    sigaction(SIGTERM, &sa, nullptr);
}

// Latest known values across metric updates (breathing and cardio can arrive separately).
struct VitalsState {
    std::mutex mu;
    double brpm = 0.0, br_conf = 0.0;
    double bpm = 0.0, hr_conf = 0.0;
    bool has_br = false, has_hr = false;
};

bool parse_dims(const std::string& s, int& w, int& h) {
    return std::sscanf(s.c_str(), "%dx%d", &w, &h) == 2 && w > 0 && h > 0;
}

bool read_exact(std::FILE* f, uint8_t* buf, size_t n) {
    size_t got = 0;
    while (got < n) {
        size_t r = std::fread(buf + got, 1, n - got, f);
        if (r == 0) return false;  // EOF, error or EINTR on shutdown
        got += r;
    }
    return true;
}

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\b') out += "\\b";
        else if (c == '\f') out += "\\f";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (static_cast<unsigned char>(c) <= 0x1F) {
            char buf[8];
            std::snprintf(buf, sizeof(buf), "\\u%04x", c);
            out += buf;
        } else {
            out += c;
        }
    }
    return out;
}

std::mutex g_out_mu;

}  // namespace

int main(int argc, char** argv) {
    install_signal_handlers();

    const char* api_key = std::getenv("PRESAGE_API_KEY");
    if (!api_key || !*api_key) {
        std::cerr << "Error: PRESAGE_API_KEY environment variable not set." << std::endl;
        return 1;
    }

    int stdin_w = 0, stdin_h = 0;
    bool use_stdin = false;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--stdin") {
            if (i + 1 >= argc || !parse_dims(argv[i + 1], stdin_w, stdin_h)) {
                std::cerr << "Usage: bridge [--stdin WxH]" << std::endl;
                return 2;
            }
            use_stdin = true;
            ++i;
        }
    }

    SmartSpectraConfig config;
    config.api_key = api_key;
    config.requested_metrics = SmartSpectraConfig::BreathingMetrics();
    config.AddMetrics(SmartSpectraConfig::CardioMetrics());

    SmartSpectra sdk(config);
    VitalsState state;

    sdk.SetOnError([](const SmartSpectraError& e) {
        std::cerr << "SDK error: " << e.FullMessage() << std::endl;
        // The SDK stays in kError and rejects every Send(); exit so the daemon respawns us.
        g_fatal = true;
    });

    sdk.SetOnValidationStatusChanged([](const ValidationStatus& vs, int64_t) {
        std::cerr << "SDK validation: " << ToString(vs) << std::endl;
        double t = std::chrono::duration<double>(
                       std::chrono::system_clock::now().time_since_epoch())
                       .count();
        std::string escaped_hint = json_escape(vs.hint);
        std::string code_str = ToString(vs.code);
        {
            std::lock_guard<std::mutex> lock(g_out_mu);
            std::printf("{\"t\": %.3f, \"validation\": \"%s\", \"hint\": \"%s\"}\n",
                        t, code_str.c_str(), escaped_hint.c_str());
            std::fflush(stdout);
        }
    });

    sdk.SetOnMetrics([&state](const Metrics& m, int64_t) {
        std::lock_guard<std::mutex> lock(state.mu);

        if (m.has_breathing() && m.breathing().rate_size() > 0) {
            const auto& s = m.breathing().rate(m.breathing().rate_size() - 1);
            state.brpm = s.value();
            state.br_conf = s.confidence();
            state.has_br = true;
        }
        if (m.has_cardio() && m.cardio().pulse_rate_size() > 0) {
            const auto& s = m.cardio().pulse_rate(m.cardio().pulse_rate_size() - 1);
            state.bpm = s.value();
            state.hr_conf = s.confidence();
            state.has_hr = true;
        }
        if (!state.has_br && !state.has_hr) return;

        // Be conservative: overall confidence is the weakest signal we have.
        double conf = 1.0;
        if (state.has_br) conf = std::min(conf, state.br_conf);
        if (state.has_hr) conf = std::min(conf, state.hr_conf);

        double t = std::chrono::duration<double>(
                       std::chrono::system_clock::now().time_since_epoch())
                       .count();
        {
            std::lock_guard<std::mutex> out_lock(g_out_mu);
            std::printf("{\"t\": %.3f, \"brpm\": %.2f, \"bpm\": %.2f, \"confidence\": %.3f}\n",
                        t, state.brpm, state.bpm, conf);
            std::fflush(stdout);
        }
    });

    std::shared_ptr<CustomInput> input;
    if (auto err = sdk.UseCustomInput().Build(input); !err.ok()) {
        std::cerr << "Error: failed to build custom input: " << err.FullMessage() << std::endl;
        return 1;
    }

    cv::VideoCapture cap;
    if (!use_stdin) {
        const char* dev = std::getenv("PRESAGE_VIDEO_DEVICE");
        std::string device_path = dev ? dev : "/dev/video11";
        cap.open(device_path);
        if (!cap.isOpened()) {
            std::cerr << "Failed to open camera: " << device_path << std::endl;
            return 1;
        }
    }

    if (auto err = sdk.Start(); !err.ok()) {
        std::cerr << "Error: SDK start failed: " << err.FullMessage() << std::endl;
        return 1;
    }

    const auto start_time = std::chrono::steady_clock::now();
    int64_t last_ts_us = -1;
    std::vector<uint8_t> buf;
    if (use_stdin) buf.resize(static_cast<size_t>(stdin_w) * stdin_h * 3);
    cv::Mat frame;

    while (g_running && !g_fatal) {
        const uint8_t* data = nullptr;
        int w = 0, h = 0;

        if (use_stdin) {
            if (!read_exact(stdin, buf.data(), buf.size())) break;  // daemon closed the pipe
            data = buf.data();
            w = stdin_w;
            h = stdin_h;
        } else {
            if (!cap.read(frame) || frame.empty()) {
                std::cerr << "Failed to read frame from camera." << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                continue;
            }
            if (!frame.isContinuous()) frame = frame.clone();
            data = frame.data;
            w = frame.cols;
            h = frame.rows;
        }

        int64_t ts_us = std::chrono::duration_cast<std::chrono::microseconds>(
                            std::chrono::steady_clock::now() - start_time)
                            .count();
        if (ts_us <= last_ts_us) ts_us = last_ts_us + 1;
        last_ts_us = ts_us;

        FrameBuffer fb{data, w, h, w * 3, PixelFormat::kBGR};
        // Per-frame rejections (non-monotonic / gap) don't end the session; just log them.
        if (auto err = input->Send(fb, ts_us); !err.ok()) {
            std::cerr << "Send: " << err.FullMessage() << std::endl;
        }
    }

    (void)sdk.Stop();
    return g_fatal ? 3 : 0;
}
