cmake_minimum_required(VERSION 3.20)

project(ExtendedCriticalityModularModel LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CRITICALITY_SOURCES
    apps/simulate/main.c
    src/utils/pvm.c
    src/utils/fopenf.c
    src/utils/getarg.c
    src/utils/debug.c
    src/utils/random.c
    src/utils/cpu.c
    src/utils/getmem.c
    src/utils/mpi.c
    src/model/network.c
    src/utils/hpsort.c
    src/utils/permuta.c
    src/utils/bisect.c
    src/data/tract1.c
    src/model/neuroni.c
)

set_source_files_properties(${CRITICALITY_SOURCES} PROPERTIES LANGUAGE CXX)

add_executable(criticality_sim ${CRITICALITY_SOURCES})

target_include_directories(criticality_sim PRIVATE
    src/model
    src/utils
    src/data
)

target_compile_definitions(criticality_sim PRIVATE
    _USE_MATH_DEFINES
    M_PI=3.14159265358979323846
)

if(MSVC)
    target_compile_options(criticality_sim PRIVATE /O2 /W0)
else()
    target_compile_options(criticality_sim PRIVATE -O3 -w)
endif()
