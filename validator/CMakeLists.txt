cmake_minimum_required(VERSION 3.18)
project(step_eval CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Exact IEEE arithmetic: no fast-math, and no contraction into fused multiply-add, so x64 and
# arm64 builds evaluate the same expressions the same way.
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -ffp-contract=off -Wno-deprecated-declarations")
find_package(OpenCASCADE REQUIRED)
add_executable(step_eval src/step_eval.cpp)
target_include_directories(step_eval PRIVATE ${OpenCASCADE_INCLUDE_DIR})
target_link_libraries(step_eval PRIVATE TKSTEP TKSTEPBase TKSTEPAttr TKSTEP209 TKXSBase TKTopAlgo TKShHealing TKBRep TKGeomAlgo TKGeomBase TKG3d TKG2d TKMath TKernel)
