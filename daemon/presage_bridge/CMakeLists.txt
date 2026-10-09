cmake_minimum_required(VERSION 3.22)
project(presage_bridge)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_package(SmartSpectra CONFIG REQUIRED)
find_package(OpenCV REQUIRED)

add_executable(bridge src/bridge.cpp)
target_link_libraries(bridge SmartSpectra::SDK ${OpenCV_LIBS})
