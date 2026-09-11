cmake_minimum_required(VERSION 3.24)
project(VideoManageGB28181 VERSION 0.1.0 LANGUAGES C CXX)

include(FetchContent)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
set(FETCHCONTENT_BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/.deps" CACHE PATH "Dependency cache")

# SIP only: no SSL/TURN/media/database/tooling dependency is needed for this service.
foreach(flag WITH_SSL USE_NUGET USE_POPT USE_MAXMIND_GEOIP BUILD_REPRO BUILD_RETURN
    BUILD_REFLOW BUILD_MEDIA BUILD_REND BUILD_TFM BUILD_RECON BUILD_RECONSERVER
    BUILD_QPID_PROTON BUILD_TESTING BUILD_DSO_PLUGINS REGENERATE_MEDIA_SAMPLES
    BUILD_SHARED_LIBS WITH_C_ARES USE_DTLS ENABLE_LOG_REPOSITORY_DETAILS)
  set(${flag} OFF CACHE BOOL "Minimal reSIProcate build" FORCE)
endforeach()
set(USE_CONTRIB ON CACHE BOOL "Use bundled DNS implementation" FORCE)
set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
set(HTTPLIB_REQUIRE_OPENSSL OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_OPENSSL_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_ZLIB_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_BROTLI_IF_AVAILABLE OFF CACHE BOOL "" FORCE)

FetchContent_Declare(resiprocate
  URL https://codeload.github.com/resiprocate/resiprocate/tar.gz/632e215c2ca9aee5416bfe1808851ea6fa380044
  URL_HASH SHA256=b6323b0d8998bd1608412a684dc61809e2cd5b286c9b1c235ac9177297f25833
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(json
  URL https://codeload.github.com/nlohmann/json/tar.gz/refs/tags/v3.11.3
  URL_HASH SHA256=0d8ef5af7f9794e3263480193c491549b2ba6cc74bb018906202ada498a79406
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(httplib
  URL https://codeload.github.com/yhirose/cpp-httplib/tar.gz/refs/tags/v0.18.6
  URL_HASH SHA256=8900747bba3dda8007f1876175be699036e09e4a25ceeab51196d9365bf1993a
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(resiprocate json httplib)

add_executable(gb28181-sip src/main.cpp)
target_link_libraries(gb28181-sip PRIVATE resip nlohmann_json::nlohmann_json httplib::httplib)
target_include_directories(gb28181-sip PRIVATE "${resiprocate_BINARY_DIR}")
target_compile_definitions(gb28181-sip PRIVATE HAVE_CONFIG_H HAVE_VERSION_H USE_ARES)
if(MSVC)
  target_compile_options(gb28181-sip PRIVATE /utf-8 /W4)
  target_compile_definitions(gb28181-sip PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX _CRT_SECURE_NO_WARNINGS)
endif()
set_target_properties(gb28181-sip PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
install(TARGETS gb28181-sip RUNTIME DESTINATION gb28181)

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/licenses")
configure_file("${resiprocate_SOURCE_DIR}/LICENSE.md" "${CMAKE_BINARY_DIR}/licenses/reSIProcate-LICENSE.md" COPYONLY)
configure_file("${resiprocate_SOURCE_DIR}/resip/COPYING" "${CMAKE_BINARY_DIR}/licenses/reSIProcate-COPYING.txt" COPYONLY)
configure_file("${json_SOURCE_DIR}/LICENSE.MIT" "${CMAKE_BINARY_DIR}/licenses/nlohmann-json-LICENSE.txt" COPYONLY)
configure_file("${httplib_SOURCE_DIR}/LICENSE" "${CMAKE_BINARY_DIR}/licenses/cpp-httplib-LICENSE.txt" COPYONLY)
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/THIRD_PARTY_NOTICES.md" "${CMAKE_BINARY_DIR}/licenses/THIRD_PARTY_NOTICES.md" COPYONLY)
install(DIRECTORY "${CMAKE_BINARY_DIR}/licenses" DESTINATION gb28181)
