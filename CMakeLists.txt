cmake_minimum_required(VERSION 3.16)

project(owl_pipe_robot VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(owl_controller
    src/PipeRobotController.cpp
)

target_include_directories(owl_controller
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)

target_compile_options(owl_controller
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
)

add_executable(owl_sim
    src/main.cpp
)

target_link_libraries(owl_sim PRIVATE owl_controller)

enable_testing()

add_executable(controller_tests
    tests/controller_tests.cpp
)

target_link_libraries(controller_tests PRIVATE owl_controller)

add_test(NAME controller_tests COMMAND controller_tests)
